"""
Unit tests for Phase 14: Dashboard REST API endpoints (central_server/api/dashboard.py).

Verifies:
  1. GET /api/v1/dashboard/summary (KPIs, metrics, actionable insight, privacy notice).
  2. GET /api/v1/dashboard/workstations (per-workstation aggregates, health status).
  3. GET /api/v1/dashboard/workstations/{device_id} (segment breakdown, fatigue indicators, 404 behavior).
  4. GET /api/v1/dashboard/trends (hourly/daily trend aggregation).
  5. GET /api/v1/dashboard/correlations (observed statistical correlations).
  6. GET /api/v1/dashboard/alerts (alert formatting, severity filtering).
  7. GET /api/v1/dashboard/devices (registered devices list, online/offline health).
"""

from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient

from central_server.database.database import CentralDatabase
from central_server.main import create_app


@pytest.fixture
def central_db() -> CentralDatabase:
    db = CentralDatabase(":memory:")
    # Seed test device and telemetry data
    db.register_device(device_name="Workstation Alpha", software_version="0.1.0", assigned_id="NODE-001")
    db.register_device(device_name="Workstation Beta", software_version="0.1.0", assigned_id="NODE-002")

    # Insert test telemetry window for NODE-001 (High risk)
    w1 = {
        "device_id": "NODE-001",
        "session_id": "sess-001",
        "window_start": "2026-09-19T09:00:00Z",
        "window_end": "2026-09-19T09:05:00Z",
        "ergonomics": {
            "average_rula": 5.2,
            "maximum_rula": 6,
            "average_reba": 6.1,
            "maximum_reba": 7,
            "high_risk_percentage": 45.0,
            "dominant_posture": "FORWARD_HEAD",
        },
        "facial_expression": {
            "neutral_percentage": 60.0,
            "positive_percentage": 10.0,
            "negative_percentage": 5.0,
            "reduced_expression_percentage": 25.0,
        },
        "breaks": {
            "breaks_recommended": 2,
            "breaks_acknowledged": 1,
        },
        "events": [
            {
                "event_type": "ALERT",
                "timestamp": "2026-09-19T09:03:00Z",
                "event_value": json.dumps({
                    "risk_level": "HIGH",
                    "condition": "FORWARD_HEAD",
                    "message": "Forward head posture sustained for 25s",
                    "duration_sec": 25.0,
                    "rula_score": 6,
                }),
            }
        ],
    }
    db.save_telemetry_window(w1)

    # Insert test telemetry window for NODE-002 (Low risk)
    w2 = {
        "device_id": "NODE-002",
        "session_id": "sess-002",
        "window_start": "2026-09-19T09:00:00Z",
        "window_end": "2026-09-19T09:05:00Z",
        "ergonomics": {
            "average_rula": 2.1,
            "maximum_rula": 3,
            "average_reba": 2.4,
            "maximum_reba": 3,
            "high_risk_percentage": 0.0,
            "dominant_posture": "NEUTRAL",
        },
        "facial_expression": {
            "neutral_percentage": 80.0,
            "positive_percentage": 15.0,
            "negative_percentage": 0.0,
            "reduced_expression_percentage": 5.0,
        },
        "breaks": {
            "breaks_recommended": 0,
            "breaks_acknowledged": 0,
        },
        "events": [],
    }
    db.save_telemetry_window(w2)

    # Simulate NODE-002 being offline by updating last_seen to 2 hours ago
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE devices SET last_seen = '2026-09-19T07:00:00Z' WHERE device_id = 'NODE-002'"
        )

    yield db
    db.close()


@pytest.fixture
def client(central_db: CentralDatabase) -> TestClient:
    app = create_app(database=central_db)
    with TestClient(app) as c:
        yield c


class TestDashboardEndpoints:

    def test_summary_kpis(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()

        assert "kpis" in data
        assert "metrics" in data
        assert "insight" in data
        assert "privacy_guarantee" in data

        kpis = data["kpis"]
        assert kpis["workers_monitored"] == 2
        assert kpis["at_risk_workers"] == 1  # NODE-001 has RULA 5.2 >= 5.0
        assert kpis["active_alerts"] >= 1
        assert "posture_compliance_pct" in kpis

        # Verify privacy guarantee is explicit
        assert "Zero camera frames" in data["privacy_guarantee"]

    def test_workstations_roster(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/workstations")
        assert resp.status_code == 200
        workstations = resp.json()
        assert len(workstations) == 2

        node_ids = {w["device_id"] for w in workstations}
        assert "NODE-001" in node_ids
        assert "NODE-002" in node_ids

        node1 = next(w for w in workstations if w["device_id"] == "NODE-001")
        assert node1["average_rula"] == 5.2
        assert node1["dominant_posture"] == "FORWARD_HEAD"
        assert node1["health_status"] == "ONLINE"

    def test_workstation_detail(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/workstations/NODE-001")
        assert resp.status_code == 200
        data = resp.json()

        assert data["device_id"] == "NODE-001"
        assert "body_segments" in data
        assert "fatigue_indicators" in data
        assert "recent_windows" in data
        assert len(data["recent_windows"]) == 1

        # Neck should be flagged Attention because dominant is FORWARD_HEAD
        assert data["body_segments"]["neck"] == "Attention"
        assert data["fatigue_indicators"]["break_adherence_pct"] >= 0.0

    def test_workstation_detail_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/workstations/NON_EXISTENT")
        assert resp.status_code == 404

    def test_trends_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/trends?interval=hourly")
        assert resp.status_code == 200
        trends = resp.json()
        assert isinstance(trends, list)
        if trends:
            assert "time_bucket" in trends[0]
            assert "dominant_risk_level" in trends[0]
            assert "average_rula" in trends[0]

    def test_correlations_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/correlations")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_analyzed_windows" in data
        assert "observed_patterns" in data

    def test_alerts_endpoint_and_filtering(self, client: TestClient) -> None:
        # Fetch all
        resp = client.get("/api/v1/dashboard/alerts")
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) >= 1
        first = alerts[0]
        assert first["device_id"] == "NODE-001"
        assert first["severity"] == "High Risk"
        assert "rula_score" in first

        # Filter by High Risk
        resp_filtered = client.get("/api/v1/dashboard/alerts?severity=High Risk")
        assert resp_filtered.status_code == 200
        assert len(resp_filtered.json()) >= 1

        # Filter by Attention (should return empty since ours is High Risk)
        resp_empty = client.get("/api/v1/dashboard/alerts?severity=Attention")
        assert resp_empty.status_code == 200
        assert len(resp_empty.json()) == 0

    def test_devices_inventory(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/devices")
        assert resp.status_code == 200
        devices = resp.json()
        assert len(devices) == 2
        dev_map = {d["device_id"]: d for d in devices}
        assert dev_map["NODE-001"]["health_status"] == "ONLINE"
        assert dev_map["NODE-002"]["health_status"] == "OFFLINE"

    def test_static_dashboard_mounted(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "EdgeErgo" in resp.text
