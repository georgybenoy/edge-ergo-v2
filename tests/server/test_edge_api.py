"""
Unit and integration tests for Phase 11: Central Server Core (PRD §11, §48, §89).

Verifies:
  1. Central database schema creation, sequential node ID issuance, and atomic writes.
  2. Data access layer privacy compliance (zero raw frames/landmarks stored).
  3. Pydantic request validators (numeric bounds, chronology, ISO timestamps).
  4. All Edge-facing endpoints (/register, /heartbeat, /assessment, /config).
  5. Duplicate telemetry window rejection (HTTP 409).
  6. End-to-end integration: Phase 10 ServerSync syncing to Phase 11 Central Server.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from central_server.database.database import CentralDatabase
from central_server.main import create_app
from central_server.validation.validators import (
    ErgonomicsMetricsPayload,
    FacialExpressionPayload,
    HeartbeatRequest,
    RegisterDeviceRequest,
    TelemetryWindowPayload,
)
from edge_agent.config.config_manager import ConfigManager
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import ServerSync


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def central_db() -> CentralDatabase:
    db = CentralDatabase(":memory:")
    yield db
    db.close()


@pytest.fixture
def client(central_db: CentralDatabase) -> TestClient:
    app = create_app(database=central_db)
    with TestClient(app) as c:
        yield c


# ── 1. Central Database Repository Tests ──────────────────────────────────────

class TestCentralDatabase:

    def test_schema_creation_and_tables(self, central_db: CentralDatabase) -> None:
        with central_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = {row["name"] for row in cursor.fetchall()}

        expected = {
            "devices",
            "sessions",
            "telemetry_windows",
            "posture_metrics",
            "expression_metrics",
            "events",
            "reports",
        }
        assert expected.issubset(tables)

    def test_sequential_node_id_generation(self, central_db: CentralDatabase) -> None:
        id1 = central_db.get_next_node_id()
        assert id1 == "NODE-001"

        d1 = central_db.register_device("Desk-1", "0.1.0")
        assert d1["device_id"] == "NODE-001"

        id2 = central_db.get_next_node_id()
        assert id2 == "NODE-002"

        d2 = central_db.register_device("Desk-2", "0.1.0")
        assert d2["device_id"] == "NODE-002"

    def test_heartbeat_updates_last_seen(self, central_db: CentralDatabase) -> None:
        central_db.register_device("Desk-1", "0.1.0")
        ok = central_db.update_heartbeat("NODE-001", "0.1.1", "monitoring", "2026-09-19T12:00:00Z")
        assert ok is True

        dev = central_db.get_device("NODE-001")
        assert dev["last_seen"] == "2026-09-19T12:00:00Z"
        assert dev["status"] == "monitoring"
        assert dev["software_version"] == "0.1.1"

    def test_telemetry_window_atomic_persistence(self, central_db: CentralDatabase) -> None:
        payload = {
            "device_id": "NODE-001",
            "session_id": "S-20260919-01",
            "window_start": "2026-09-19T10:00:00Z",
            "window_end": "2026-09-19T10:05:00Z",
            "ergonomics": {
                "average_rula": 4.5,
                "maximum_rula": 6,
                "average_reba": 5.0,
                "maximum_reba": 7,
                "high_risk_percentage": 25.0,
                "dominant_posture": "NECK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 80.0,
                "positive_percentage": 10.0,
                "negative_percentage": 5.0,
                "reduced_expression_percentage": 5.0,
            },
            "breaks": {
                "breaks_recommended": 1,
                "breaks_acknowledged": 0,
            },
        }

        is_new, window_id = central_db.save_telemetry_window(payload)
        assert is_new is True

        # Verify window can be retrieved with metrics
        window = central_db.get_telemetry_window(window_id)
        assert window is not None
        assert window["device_id"] == "NODE-001"
        assert window["breaks_recommended"] == 1
        assert window["posture"]["average_rula"] == 4.5
        assert window["posture"]["dominant_posture"] == "NECK_FLEXION"
        assert window["expression"]["neutral_percentage"] == 80.0

    def test_duplicate_window_rejection_in_db(self, central_db: CentralDatabase) -> None:
        payload = {
            "device_id": "NODE-001",
            "session_id": "S-DUP-01",
            "window_start": "2026-09-19T10:00:00Z",
            "window_end": "2026-09-19T10:05:00Z",
            "ergonomics": {
                "average_rula": 3.0, "maximum_rula": 3,
                "average_reba": 3.0, "maximum_reba": 3,
                "high_risk_percentage": 0.0, "dominant_posture": "NEUTRAL",
            },
        }

        is_new1, wid1 = central_db.save_telemetry_window(payload)
        assert is_new1 is True

        # Second save must detect duplicate
        is_new2, wid2 = central_db.save_telemetry_window(payload)
        assert is_new2 is False
        assert wid1 == wid2

    def test_privacy_compliance_zero_raw_columns(self, central_db: CentralDatabase) -> None:
        forbidden = {"image", "frame", "crop", "video", "jpeg", "png", "bitmap", "landmark", "raw"}
        with central_db.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r["name"] for r in cursor.fetchall()]

            for t in tables:
                col_cursor = conn.execute(f"PRAGMA table_info({t})")
                cols = [c["name"].lower() for c in col_cursor.fetchall()]
                for col in cols:
                    for f in forbidden:
                        assert f not in col, f"Forbidden column '{col}' found in central table '{t}'"


# ── 2. Inbound Validation Tests ───────────────────────────────────────────────

class TestValidators:

    def test_valid_telemetry_payload_passes(self) -> None:
        payload = TelemetryWindowPayload(
            device_id="NODE-001",
            session_id="S-001",
            window_start="2026-09-19T10:00:00Z",
            window_end="2026-09-19T10:05:00Z",
            ergonomics=ErgonomicsMetricsPayload(
                average_rula=4.0,
                maximum_rula=5,
                average_reba=5.0,
                maximum_reba=6,
                high_risk_percentage=20.0,
                dominant_posture="NECK_FLEXION",
            ),
            facial_expression=FacialExpressionPayload(
                neutral_percentage=100.0,
                positive_percentage=0.0,
                negative_percentage=0.0,
                reduced_expression_percentage=0.0,
            ),
        )
        assert payload.device_id == "NODE-001"

    def test_invalid_rula_out_of_bounds_raises(self) -> None:
        with pytest.raises(ValueError):
            ErgonomicsMetricsPayload(
                average_rula=8.5,  # Out of [1, 7]
                maximum_rula=9,
                average_reba=5.0,
                maximum_reba=5,
                high_risk_percentage=0.0,
                dominant_posture="NEUTRAL",
            )

    def test_invalid_timestamp_format_raises(self) -> None:
        with pytest.raises(ValueError, match="ISO 8601"):
            TelemetryWindowPayload(
                device_id="NODE-001",
                session_id="S-001",
                window_start="not-a-timestamp",
                window_end="2026-09-19T10:05:00Z",
                ergonomics=ErgonomicsMetricsPayload(
                    average_rula=3.0, maximum_rula=3,
                    average_reba=3.0, maximum_reba=3,
                    high_risk_percentage=0.0, dominant_posture="NEUTRAL",
                ),
                facial_expression=FacialExpressionPayload(
                    neutral_percentage=100.0, positive_percentage=0.0,
                    negative_percentage=0.0, reduced_expression_percentage=0.0,
                ),
            )

    def test_inverted_chronology_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot precede"):
            TelemetryWindowPayload(
                device_id="NODE-001",
                session_id="S-001",
                window_start="2026-09-19T10:10:00Z",
                window_end="2026-09-19T10:05:00Z",  # Earlier than start!
                ergonomics=ErgonomicsMetricsPayload(
                    average_rula=3.0, maximum_rula=3,
                    average_reba=3.0, maximum_reba=3,
                    high_risk_percentage=0.0, dominant_posture="NEUTRAL",
                ),
                facial_expression=FacialExpressionPayload(
                    neutral_percentage=100.0, positive_percentage=0.0,
                    negative_percentage=0.0, reduced_expression_percentage=0.0,
                ),
            )


# ── 3. FastAPI Edge Endpoints Tests ───────────────────────────────────────────

class TestEdgeApiEndpoints:

    def test_health_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "server" in data

    def test_register_edge_node(self, client: TestClient) -> None:
        payload = {
            "device_name": "Workstation-A",
            "software_version": "0.1.0",
            "camera_detected": True,
            "camera_index": 0,
        }
        resp = client.post("/api/v1/edge/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_id"] == "NODE-001"
        assert data["device_name"] == "Workstation-A"
        assert data["status"] == "active"

    def test_heartbeat_endpoint(self, client: TestClient) -> None:
        payload = {
            "device_id": "NODE-001",
            "software_version": "0.1.0",
            "status": "monitoring",
        }
        resp = client.post("/api/v1/edge/heartbeat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] is True
        assert data["device_id"] == "NODE-001"

    def test_upload_telemetry_window_and_duplicate_rejection(self, client: TestClient) -> None:
        payload = {
            "device_id": "NODE-001",
            "session_id": "S-TEST-001",
            "window_start": "2026-09-19T10:00:00Z",
            "window_end": "2026-09-19T10:05:00Z",
            "ergonomics": {
                "average_rula": 4.2,
                "maximum_rula": 6,
                "average_reba": 5.1,
                "maximum_reba": 7,
                "high_risk_percentage": 32.5,
                "dominant_posture": "NECK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 72.0,
                "positive_percentage": 15.0,
                "negative_percentage": 8.0,
                "reduced_expression_percentage": 5.0,
            },
            "breaks": {
                "breaks_recommended": 1,
                "breaks_acknowledged": 0,
            },
        }

        # 1. First upload -> 201 Created
        resp1 = client.post("/api/v1/edge/assessment", json=payload)
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["status"] == "accepted"
        assert data1["device_id"] == "NODE-001"

        # 2. Duplicate upload -> 409 Conflict with status='duplicate'
        resp2 = client.post("/api/v1/edge/assessment", json=payload)
        assert resp2.status_code == 409
        data2 = resp2.json()
        assert data2["status"] == "duplicate"
        assert data2["window_id"] == data1["window_id"]

    def test_get_edge_config(self, client: TestClient) -> None:
        resp = client.get("/api/v1/edge/config?device_id=NODE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_interval_min"] == 30.0
        assert data["monitoring_start_time"] == "09:00"

    def test_malformed_telemetry_rejected_with_422(self, client: TestClient) -> None:
        bad_payload = {
            "device_id": "NODE-001",
            # missing session_id and ergonomics
            "window_start": "2026-09-19T10:00:00Z",
        }
        resp = client.post("/api/v1/edge/assessment", json=bad_payload)
        assert resp.status_code == 422


# ── 4. End-to-End Integration (Phase 10 Edge Agent to Phase 11 Server) ────────

class TestEndToEndEdgeWithServer:

    def test_edge_sync_client_talks_to_central_server(
        self,
        central_db: CentralDatabase,
        tmp_path: Path,
    ) -> None:
        """Connect real Phase 10 ServerSync client directly to Phase 11 FastAPI app."""
        app = create_app(database=central_db)
        edge_db = LocalDatabase(tmp_path / "local_agent.db")
        config_mgr = ConfigManager(config_path=tmp_path / "edge_cfg.json", auto_load=False)
        config_mgr.config.server_url = "http://testserver"

        test_client = TestClient(app)

        # Mock httpx.Client in ServerSync to redirect requests to FastAPI TestClient
        class MockHttpClientContext:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def get(self, url, **kwargs):
                path = url.replace("http://testserver", "")
                return test_client.get(path, **kwargs)
            def post(self, url, **kwargs):
                path = url.replace("http://testserver", "")
                return test_client.post(path, **kwargs)

        with patch("httpx.Client", side_effect=MockHttpClientContext):
            sync = ServerSync(config_manager=config_mgr, local_db=edge_db)

            # 1. Register Edge Node
            ok, node_id = sync.register_node(device_name="QA-Workstation")
            assert ok is True
            assert node_id == "NODE-001"
            assert config_mgr.config.device_id == "NODE-001"

            # 2. Record local session in edge SQLite
            edge_db.register_device(node_id)
            edge_db.record_session("sess-e2e-100", node_id, "2026-09-19T11:00:00Z", "2026-09-19T11:05:00Z", 300.0)
            edge_db.record_assessment("assess-e2e-100", "sess-e2e-100", "2026-09-19T11:05:00Z", 4, 5, "MODERATE", "NECK_FLEXION", "Neutral")
            edge_db.enqueue_sync(record_id="sess-e2e-100")

            # 3. Drain and upload pending telemetry
            count = sync.sync_pending_telemetry(limit=5)
            assert count == 1

            # 4. Verify central server received and stored the telemetry window
            central_windows = central_db.list_telemetry_windows(device_id="NODE-001")
            assert len(central_windows) == 1
            assert central_windows[0]["session_id"] == "sess-e2e-100"
            assert central_windows[0]["dominant_posture"] == "NECK_FLEXION"

        edge_db.close()
