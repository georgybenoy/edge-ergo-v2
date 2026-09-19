"""
Unit and integration tests for Phase 10: Edge-to-Server Communication.

Verifies:
  1. ConfigManager disk serialization, field validation, and range checks.
  2. HeartbeatClient payload structure, network failure tolerance, and background thread.
  3. Edge node registration flow (POST /api/v1/edge/register) and NODE-xxx persistence.
  4. Exact telemetry window JSON schema structure matching PRD specifications.
  5. Exponential backoff calculation and skip behavior during backoff window.
  6. Telemetry queue draining with idempotency, state transitions, and failure handling.
  7. Remote config pull (GET /api/v1/edge/config) and local merging.
  8. Background SyncWorker non-blocking execution.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from edge_agent.config.config_manager import ConfigManager, EdgeConfig
from edge_agent.health.heartbeat import HeartbeatClient
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import (
    ServerSync,
    SyncWorker,
    build_telemetry_window_payload,
    compute_backoff_delay,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_config(tmp_path: Path) -> ConfigManager:
    cfg_file = tmp_path / "test_config.json"
    mgr = ConfigManager(config_path=cfg_file, auto_load=False)
    mgr.config.server_url = "http://testserver:8000"
    mgr.config.device_id = "NODE-TEST-001"
    mgr.config.software_version = "0.1.0"
    return mgr


@pytest.fixture
def mem_db() -> LocalDatabase:
    db = LocalDatabase(":memory:")
    yield db
    db.close()


# ── 1. ConfigManager Tests ───────────────────────────────────────────────────

class TestConfigManager:

    def test_save_and_load_disk_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "custom_config.json"
        mgr = ConfigManager(config_path=cfg_file, auto_load=False)
        mgr.update({
            "device_id": "NODE-999",
            "monitoring_start_time": "08:15",
            "capture_fps": 15,
            "session_interval_min": 25.0,
        }, save_to_disk=True)

        assert cfg_file.exists()

        # Load fresh manager from same file
        mgr2 = ConfigManager(config_path=cfg_file, auto_load=True)
        assert mgr2.config.device_id == "NODE-999"
        assert mgr2.config.monitoring_start_time == "08:15"
        assert mgr2.config.capture_fps == 15
        assert mgr2.config.session_interval_min == 25.0

    def test_validation_rejects_invalid_values(self, temp_config: ConfigManager) -> None:
        with pytest.raises(ValueError, match="capture_fps"):
            temp_config.validate({"capture_fps": 120})

        with pytest.raises(ValueError, match="capture_fps"):
            temp_config.validate({"capture_fps": 0})

        with pytest.raises(ValueError, match="HH:MM"):
            temp_config.validate({"monitoring_start_time": "8am"})

        with pytest.raises(ValueError, match="server_url"):
            temp_config.validate({"server_url": "ftp://invalid"})

        with pytest.raises(ValueError, match="rula_alert_threshold"):
            temp_config.validate({"rula_alert_threshold": 9})


# ── 2. Heartbeat Client Tests ─────────────────────────────────────────────────

class TestHeartbeatClient:

    @patch("httpx.Client")
    def test_send_heartbeat_payload_and_success(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        client = HeartbeatClient(
            server_url="http://testserver:8000",
            device_id="NODE-TEST-001",
            software_version="0.1.0",
            status_provider=lambda: "monitoring",
        )

        ok = client.send_heartbeat()
        assert ok is True
        assert client.last_success is True

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        assert args[0] == "http://testserver:8000/api/v1/edge/heartbeat"
        assert kwargs["json"] == {
            "device_id": "NODE-TEST-001",
            "software_version": "0.1.0",
            "status": "monitoring",
        }

    @patch("httpx.Client")
    def test_heartbeat_server_unreachable_returns_false_without_raising(
        self, mock_client_cls: MagicMock
    ) -> None:
        import httpx
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")
        mock_client_cls.return_value.__enter__.return_value = mock_client

        client = HeartbeatClient(
            server_url="http://offline-server:8000",
            device_id="NODE-TEST-001",
        )

        ok = client.send_heartbeat()
        assert ok is False
        assert client.last_success is False

    @patch("httpx.Client")
    def test_heartbeat_background_thread_start_stop(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock(status_code=204)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        client = HeartbeatClient(
            server_url="http://testserver:8000",
            device_id="NODE-001",
            interval_sec=0.05,
        )

        assert not client.is_running
        client.start()
        assert client.is_running
        time.sleep(0.1)
        client.stop()
        assert not client.is_running


# ── 3. Edge Node Registration Tests ───────────────────────────────────────────

class TestServerRegistration:

    @patch("edge_agent.sync.server_sync.list_available_cameras", return_value=[0])
    @patch("httpx.Client")
    def test_register_node_success(
        self,
        mock_client_cls: MagicMock,
        mock_cam: MagicMock,
        temp_config: ConfigManager,
        mem_db: LocalDatabase,
    ) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "device_id": "NODE-042",
            "registered_at": "2026-09-19T10:00:00Z",
        }
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        sync = ServerSync(config_manager=temp_config, local_db=mem_db)
        success, node_id = sync.register_node(device_name="Floor-2-Desk-11")

        assert success is True
        assert node_id == "NODE-042"
        # Verify persisted in config
        assert temp_config.config.device_id == "NODE-042"
        # Verify persisted in local DB
        dev = mem_db.get_device("NODE-042")
        assert dev is not None
        assert dev["device_name"] == "Floor-2-Desk-11"

    @patch("httpx.Client")
    def test_register_node_failure_handled_cleanly(
        self,
        mock_client_cls: MagicMock,
        temp_config: ConfigManager,
        mem_db: LocalDatabase,
    ) -> None:
        import httpx
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.RequestError("Host unreachable")
        mock_client_cls.return_value.__enter__.return_value = mock_client

        sync = ServerSync(config_manager=temp_config, local_db=mem_db)
        success, error_msg = sync.register_node(device_name="Desk-A")

        assert success is False
        assert "Host unreachable" in error_msg


# ── 4. Telemetry Window Payload & Schema Tests ────────────────────────────────

class TestTelemetryWindowPayload:

    def test_exact_json_shape_matching_prd(self) -> None:
        session = {
            "session_id": "S-20260914-001",
            "start_time": "2026-09-14T10:00:00",
            "end_time": "2026-09-14T10:05:00",
            "duration": 300.0,
        }
        assessment = {
            "rula_score": 4,
            "reba_score": 5,
            "risk_level": "MODERATE",
            "dominant_posture": "NECK_FLEXION",
            "expression_category": "Neutral",
        }
        events = [
            {"event_type": "BREAK_REMINDER", "event_value": "Stand up and stretch"},
        ]

        payload = build_telemetry_window_payload(
            session=session,
            assessment=assessment,
            events=events,
            device_id="NODE-004",
        )

        assert payload["device_id"] == "NODE-004"
        assert payload["session_id"] == "S-20260914-001"
        assert payload["window_start"] == "2026-09-14T10:00:00"
        assert payload["window_end"] == "2026-09-14T10:05:00"
        assert "window_id" in payload

        # Ergonomics section
        ergo = payload["ergonomics"]
        assert ergo["average_rula"] == 4.0
        assert ergo["maximum_rula"] == 4
        assert ergo["average_reba"] == 5.0
        assert ergo["maximum_reba"] == 5
        assert ergo["dominant_posture"] == "NECK_FLEXION"
        assert ergo["high_risk_percentage"] == 0.0

        # Facial expression section
        expr = payload["facial_expression"]
        assert expr["neutral_percentage"] == 100
        assert expr["positive_percentage"] == 0

        # Breaks section
        brk = payload["breaks"]
        assert brk["breaks_recommended"] == 1
        assert brk["breaks_acknowledged"] == 0


# ── 5. Exponential Backoff Tests ──────────────────────────────────────────────

class TestExponentialBackoff:

    def test_backoff_progression_and_capping(self) -> None:
        assert compute_backoff_delay(0) == 0.0
        assert compute_backoff_delay(1, base_sec=2.0) == 2.0
        assert compute_backoff_delay(2, base_sec=2.0) == 4.0
        assert compute_backoff_delay(3, base_sec=2.0) == 8.0
        assert compute_backoff_delay(4, base_sec=2.0) == 16.0
        assert compute_backoff_delay(10, base_sec=2.0, max_sec=120.0) == 120.0


# ── 6. Telemetry Upload & Queue Sync Tests ───────────────────────────────────

class TestTelemetryUploadFlow:

    def _setup_session_in_db(self, db: LocalDatabase, session_id: str = "sess-synctest-1") -> str:
        db.register_device("NODE-TEST-001")
        db.record_session(
            session_id=session_id,
            device_id="NODE-TEST-001",
            start_time="2026-09-19T10:00:00Z",
            end_time="2026-09-19T10:05:00Z",
            duration=300.0,
        )
        db.record_assessment(
            assessment_id=f"assess-{session_id}",
            session_id=session_id,
            timestamp="2026-09-19T10:05:00Z",
            rula_score=5,
            reba_score=4,
            risk_level="HIGH",
            dominant_posture="TRUNK_FLEXION",
            expression_category="Neutral",
        )
        return db.enqueue_sync(record_id=session_id)

    @patch("httpx.Client")
    def test_sync_pending_telemetry_success_and_idempotency(
        self,
        mock_client_cls: MagicMock,
        temp_config: ConfigManager,
        mem_db: LocalDatabase,
    ) -> None:
        sync_id = self._setup_session_in_db(mem_db, "sess-success-01")

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        sync = ServerSync(config_manager=temp_config, local_db=mem_db)
        count = sync.sync_pending_telemetry(limit=5)

        assert count == 1

        # Verify idempotency key header was provided
        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        assert "X-Idempotency-Key" in kwargs["headers"]
        assert "sess-success-01" in kwargs["headers"]["X-Idempotency-Key"]

        # Verify status changed to SYNCED in local DB
        summary = mem_db.get_sync_status_summary()
        assert summary["SYNCED"] == 1
        assert summary["PENDING"] == 0

    @patch("httpx.Client")
    def test_sync_failure_increments_retry_and_applies_backoff(
        self,
        mock_client_cls: MagicMock,
        temp_config: ConfigManager,
        mem_db: LocalDatabase,
    ) -> None:
        sync_id = self._setup_session_in_db(mem_db, "sess-fail-01")

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 503  # Service unavailable
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        sync = ServerSync(config_manager=temp_config, local_db=mem_db)
        count = sync.sync_pending_telemetry(limit=5)

        assert count == 0
        # Item stays PENDING with retry_count incremented
        summary = mem_db.get_sync_status_summary()
        assert summary["PENDING"] == 1

        pending = mem_db.get_pending_sync_records()
        assert len(pending) == 1
        assert pending[0]["retry_count"] == 1
        assert pending[0]["last_attempt"] is not None

        # Immediate next sync must skip because it is within backoff window
        count2 = sync.sync_pending_telemetry(limit=5)
        assert count2 == 0
        # post was called only once from the first try
        assert mock_client.post.call_count == 1


# ── 7. Server Config Pull Tests ───────────────────────────────────────────────

class TestRemoteConfigSync:

    @patch("httpx.Client")
    def test_sync_remote_config_merges_overrides(
        self,
        mock_client_cls: MagicMock,
        temp_config: ConfigManager,
        mem_db: LocalDatabase,
    ) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "session_interval_min": 45.0,
            "persistence_threshold_sec": 25.0,
            "rula_alert_threshold": 6,
        }
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        sync = ServerSync(config_manager=temp_config, local_db=mem_db)
        success = sync.sync_remote_config()

        assert success is True
        assert temp_config.config.session_interval_min == 45.0
        assert temp_config.config.persistence_threshold_sec == 25.0
        assert temp_config.config.rula_alert_threshold == 6
        assert mem_db.get_config("session_interval_min") == 45.0


# ── 8. SyncWorker Non-Blocking Tests ──────────────────────────────────────────

class TestSyncWorker:

    def test_sync_worker_start_stop_cleanly(
        self,
        temp_config: ConfigManager,
        mem_db: LocalDatabase,
    ) -> None:
        sync = ServerSync(config_manager=temp_config, local_db=mem_db)
        worker = SyncWorker(server_sync=sync, interval_sec=0.05)

        assert not worker.is_running
        worker.start()
        assert worker.is_running
        time.sleep(0.1)
        worker.stop()
        assert not worker.is_running
