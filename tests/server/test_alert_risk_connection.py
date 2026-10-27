"""
Tests for Alert-to-Risk Integration.

Verifies:
  1. High-risk telemetry window automatically creates an ALERT event in the central database.
  2. GET /api/v1/dashboard/alerts returns risk-connected alerts with appropriate severity (Critical, High Risk).
  3. Low-risk telemetry window does NOT create alert events.
  4. Telemetry windows without event rows still surface as alerts via GET /api/v1/dashboard/alerts.
  5. LocalDatabase automatically creates alert events when saving high-risk sessions.
  6. ServerSync packages events in the telemetry window payload.
  7. Summary KPIs correctly report active_alerts count based on elevated ergonomic risk.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from central_server.database.database import CentralDatabase
from central_server.main import create_app
from edge_agent.config.config_manager import ConfigManager
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import ServerSync, build_telemetry_window_payload


@pytest.fixture
def central_db() -> CentralDatabase:
    db = CentralDatabase(":memory:")
    db.register_device(device_name="Workstation HR", software_version="0.1.0", assigned_id="NODE-101")
    db.register_device(device_name="Workstation Safe", software_version="0.1.0", assigned_id="NODE-102")
    yield db
    db.close()


@pytest.fixture
def client(central_db: CentralDatabase) -> TestClient:
    app = create_app(database=central_db)
    with TestClient(app) as c:
        yield c


class TestAlertRiskConnection:

    def test_high_risk_window_auto_generates_alert_event(self, client: TestClient, central_db: CentralDatabase) -> None:
        """Uploading a telemetry window with RULA >= 5.0 without events must create an ALERT event."""
        payload = {
            "device_id": "NODE-101",
            "session_id": "S-RISK-01",
            "window_start": "2026-10-27T10:00:00Z",
            "window_end": "2026-10-27T10:05:00Z",
            "ergonomics": {
                "average_rula": 5.8,
                "maximum_rula": 7,
                "average_reba": 8.5,
                "maximum_reba": 10,
                "high_risk_percentage": 65.0,
                "dominant_posture": "FORWARD_HEAD",
            },
            "facial_expression": {
                "neutral_percentage": 50.0,
                "positive_percentage": 0.0,
                "negative_percentage": 30.0,
                "reduced_expression_percentage": 20.0,
            },
            "breaks": {
                "breaks_recommended": 1,
                "breaks_acknowledged": 0,
            },
        }

        resp = client.post("/api/v1/edge/assessment", json=payload)
        assert resp.status_code in (200, 201)

        # Check events table in central DB
        with central_db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM events WHERE device_id = 'NODE-101' AND event_type = 'ALERT'")
            alerts = [dict(r) for r in cursor.fetchall()]

        assert len(alerts) >= 1
        val = json.loads(alerts[0]["event_value"])
        assert val["risk_level"] in ("HIGH", "VERY_HIGH")
        assert val["rula_score"] == 5.8

    def test_low_risk_window_does_not_generate_alert(self, client: TestClient, central_db: CentralDatabase) -> None:
        """Uploading safe posture (RULA 2.0) must not generate an alert."""
        payload = {
            "device_id": "NODE-102",
            "session_id": "S-SAFE-01",
            "window_start": "2026-10-27T11:00:00Z",
            "window_end": "2026-10-27T11:05:00Z",
            "ergonomics": {
                "average_rula": 2.0,
                "maximum_rula": 2,
                "average_reba": 2.0,
                "maximum_reba": 2,
                "high_risk_percentage": 0.0,
                "dominant_posture": "NEUTRAL",
            },
            "facial_expression": {
                "neutral_percentage": 90.0,
                "positive_percentage": 10.0,
                "negative_percentage": 0.0,
                "reduced_expression_percentage": 0.0,
            },
            "breaks": {
                "breaks_recommended": 0,
                "breaks_acknowledged": 0,
            },
        }

        resp = client.post("/api/v1/edge/assessment", json=payload)
        assert resp.status_code in (200, 201)

        with central_db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM events WHERE device_id = 'NODE-102' AND event_type = 'ALERT'")
            alerts = [dict(r) for r in cursor.fetchall()]

        assert len(alerts) == 0

    def test_alerts_endpoint_surfaces_connected_risk_alerts(self, client: TestClient) -> None:
        """GET /api/v1/dashboard/alerts returns alerts connected to high-risk workstations."""
        # Ingest high risk window
        payload = {
            "device_id": "NODE-101",
            "session_id": "S-RISK-02",
            "window_start": "2026-10-27T12:00:00Z",
            "window_end": "2026-10-27T12:05:00Z",
            "ergonomics": {
                "average_rula": 6.2,
                "maximum_rula": 7,
                "average_reba": 9.0,
                "maximum_reba": 11,
                "high_risk_percentage": 70.0,
                "dominant_posture": "TRUNK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 60.0,
                "positive_percentage": 10.0,
                "negative_percentage": 15.0,
                "reduced_expression_percentage": 15.0,
            },
            "breaks": {
                "breaks_recommended": 1,
                "breaks_acknowledged": 0,
            },
        }
        client.post("/api/v1/edge/assessment", json=payload)

        # Query all alerts
        resp = client.get("/api/v1/dashboard/alerts")
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) >= 1

        alert = next(a for a in alerts if a["device_id"] == "NODE-101")
        assert alert["device_name"] == "Workstation HR"
        assert alert["severity"] in ("High Risk", "Critical")
        assert alert["rula_score"] == 6.2
        assert alert["status"] == "Active"

        # Query severity=Critical
        resp_crit = client.get("/api/v1/dashboard/alerts?severity=Critical")
        assert resp_crit.status_code == 200
        assert len(resp_crit.json()) >= 1

        # Summary KPIs reflect active alerts
        summary_resp = client.get("/api/v1/dashboard/summary")
        assert summary_resp.status_code == 200
        kpis = summary_resp.json()["kpis"]
        assert kpis["active_alerts"] >= 1
        assert kpis["at_risk_workers"] >= 1

    def test_dynamic_fallback_synthesizes_alerts_from_risk_windows(self, client: TestClient, central_db: CentralDatabase) -> None:
        """If risk telemetry window exists without an events row, GET /alerts synthesizes the alert."""
        # Manually insert telemetry window & posture metrics directly without events
        now_ts = datetime.now(timezone.utc).isoformat()
        with central_db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, device_id, start_time, end_time, duration, created_at)
                VALUES ('sess-legacy-01', 'NODE-101', '2026-10-27T08:00:00Z', '2026-10-27T08:05:00Z', 300.0, ?)
                """,
                (now_ts,),
            )
            conn.execute(
                """
                INSERT INTO telemetry_windows (
                    window_id, device_id, session_id, window_start, window_end,
                    created_at, breaks_recommended, breaks_acknowledged
                ) VALUES ('win-legacy-01', 'NODE-101', 'sess-legacy-01', '2026-10-27T08:00:00Z', '2026-10-27T08:05:00Z', ?, 0, 0)
                """,
                (now_ts,),
            )
            conn.execute(
                """
                INSERT INTO posture_metrics (
                    metric_id, window_id, average_rula, maximum_rula,
                    average_reba, maximum_reba, high_risk_percentage, dominant_posture
                ) VALUES ('pm-legacy-01', 'win-legacy-01', 5.5, 6, 6.0, 7, 40.0, 'SLOUCHING')
                """
            )

        resp = client.get("/api/v1/dashboard/alerts")
        assert resp.status_code == 200
        alerts = resp.json()
        assert any(a["alert_id"] == "RISK-win-legacy-01" for a in alerts)

    def test_edge_payload_builder_includes_events(self) -> None:
        """build_telemetry_window_payload includes formatted events in its output."""
        session = {"session_id": "SESS-BUILD-01", "start_time": "2026-10-27T10:00:00Z", "end_time": "2026-10-27T10:05:00Z"}
        assessment = {"rula_score": 6.0, "reba_score": 7.0, "risk_level": "HIGH", "dominant_posture": "TRUNK_FLEXION"}
        events = [
            {
                "event_id": "EVT-01",
                "timestamp": "2026-10-27T10:02:00Z",
                "event_type": "ALERT",
                "event_value": json.dumps({"condition": "TRUNK_FLEXION", "risk_level": "HIGH", "rula_score": 6}),
            }
        ]

        payload = build_telemetry_window_payload(session, assessment, events, "NODE-001")
        assert "events" in payload
        assert len(payload["events"]) == 1
        assert payload["events"][0]["event_type"] == "ALERT"
        assert payload["events"][0]["event_id"] == "EVT-01"

    def test_local_db_saves_alert_on_high_risk(self, tmp_path: Path) -> None:
        """LocalDatabase.save_session_analysis persists an ALERT event when risk is high."""
        db = LocalDatabase(tmp_path / "test_edge.db")

        class MockStats:
            session_id = "SESS-HIGH-01"
            start_time = 1000.0
            end_time = 1300.0
            duration_sec = 300.0
            avg_rula = 5.5
            avg_reba = 6.0
            dominant_posture = "NECK_FLEXION"
            alerts_triggered = []

        db.save_session_analysis("NODE-TEST", MockStats())
        events = db.get_events_for_session("SESS-HIGH-01")
        assert len(events) >= 1
        assert events[0]["event_type"] == "ALERT"
        val = json.loads(events[0]["event_value"])
        assert val["risk_level"] == "HIGH"
        db.close()
