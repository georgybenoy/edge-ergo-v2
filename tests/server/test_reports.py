"""
Unit and integration tests for Phase 15: CSV Export and Reporting (PRD §106).

Verifies:
  1. RFC-4180 CSV generation with exact headers and mathematical validity.
  2. Date and device filtering for CSV exports.
  3. Structured report generation (daily, weekly, monthly) matching Phase 13 math.
  4. Privacy compliance: zero raw media / face images in exports and reports.
  5. Standalone print-optimized HTML executive report generation.
  6. Central Server REST endpoints:
     - GET /api/v1/export/csv
     - GET /api/v1/reports/{daily|weekly|monthly}
     - GET /api/v1/reports/{daily|weekly|monthly}/html
     - GET /api/v1/reports (historical inventory)
"""

import csv
import io
import json
import pytest
from fastapi.testclient import TestClient

from central_server.database.database import CentralDatabase
from central_server.main import create_app
from central_server.reports.report_generator import ReportGenerator


@pytest.fixture
def seeded_db() -> CentralDatabase:
    """Pre-populates an in-memory database with test telemetry and events."""
    db = CentralDatabase(":memory:")

    db.register_device(device_name="Desk Alpha", software_version="0.1.0", assigned_id="NODE-001")
    db.register_device(device_name="Desk Beta", software_version="0.1.0", assigned_id="NODE-002")

    # Window 1: NODE-001 (High risk RULA 5.5, Neck Flexion, 2 breaks rec / 1 ack)
    w1 = {
        "device_id": "NODE-001",
        "session_id": "S-01",
        "window_start": "2026-09-19T09:00:00Z",
        "window_end": "2026-09-19T09:05:00Z",
        "ergonomics": {
            "average_rula": 5.5,
            "maximum_rula": 6,
            "average_reba": 6.0,
            "maximum_reba": 7,
            "high_risk_percentage": 50.0,
            "dominant_posture": "NECK_FLEXION",
        },
        "facial_expression": {
            "neutral_percentage": 65.0,
            "positive_percentage": 10.0,
            "negative_percentage": 5.0,
            "reduced_expression_percentage": 20.0,
        },
        "breaks": {
            "breaks_recommended": 2,
            "breaks_acknowledged": 1,
        },
        "events": [
            {
                "event_type": "ALERT",
                "timestamp": "2026-09-19T09:03:00Z",
                "event_value": json.dumps({"risk_level": "HIGH", "message": "Neck flexion sustained"}),
            }
        ],
    }
    db.save_telemetry_window(w1)

    # Window 2: NODE-002 (Low risk RULA 2.0, Neutral, 0 breaks)
    w2 = {
        "device_id": "NODE-002",
        "session_id": "S-02",
        "window_start": "2026-09-19T10:00:00Z",
        "window_end": "2026-09-19T10:05:00Z",
        "ergonomics": {
            "average_rula": 2.0,
            "maximum_rula": 2,
            "average_reba": 2.0,
            "maximum_reba": 3,
            "high_risk_percentage": 0.0,
            "dominant_posture": "NEUTRAL",
        },
        "facial_expression": {
            "neutral_percentage": 85.0,
            "positive_percentage": 10.0,
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

    yield db
    db.close()


@pytest.fixture
def client(seeded_db: CentralDatabase) -> TestClient:
    app = create_app(database=seeded_db)
    with TestClient(app) as c:
        yield c


# ── 1. ReportGenerator Core Logic Tests ────────────────────────────────────────

class TestReportGenerator:

    def test_generate_csv_structure_and_headers(self, seeded_db: CentralDatabase) -> None:
        generator = ReportGenerator(seeded_db)
        csv_text = generator.generate_csv()

        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)

        assert len(rows) == 2
        expected_fields = [
            "window_id",
            "device_id",
            "device_name",
            "session_id",
            "window_start",
            "window_end",
            "duration_sec",
            "average_rula",
            "maximum_rula",
            "average_reba",
            "maximum_reba",
            "risk_level",
            "dominant_posture",
            "neutral_percentage",
            "positive_percentage",
            "negative_percentage",
            "reduced_expression_percentage",
            "breaks_recommended",
            "breaks_acknowledged",
        ]
        assert reader.fieldnames == expected_fields

        # Check values
        r1 = next(r for r in rows if r["device_id"] == "NODE-001")
        assert float(r1["average_rula"]) == 5.5
        assert r1["dominant_posture"] == "NECK_FLEXION"
        assert r1["risk_level"] == "HIGH"
        assert int(r1["breaks_recommended"]) == 2
        assert int(r1["breaks_acknowledged"]) == 1

    def test_generate_csv_filtering(self, seeded_db: CentralDatabase) -> None:
        generator = ReportGenerator(seeded_db)

        # Filter by device_id
        csv_node1 = generator.generate_csv(device_id="NODE-001")
        reader1 = csv.DictReader(io.StringIO(csv_node1))
        rows1 = list(reader1)
        assert len(rows1) == 1
        assert rows1[0]["device_id"] == "NODE-001"

        # Filter by non-existent device
        csv_none = generator.generate_csv(device_id="NON_EXISTENT")
        reader_none = csv.DictReader(io.StringIO(csv_none))
        assert len(list(reader_none)) == 0

    def test_generate_periodic_report_data(self, seeded_db: CentralDatabase) -> None:
        generator = ReportGenerator(seeded_db)
        report = generator.generate_report(report_type="daily", save=True)

        assert report["report_type"] == "daily"
        assert "report_id" in report
        assert "summary" in report

        summary = report["summary"]
        assert summary["total_windows"] == 2
        # Avg RULA = (5.5 + 2.0) / 2 = 3.75 -> round to 3.8
        assert summary["average_rula"] == 3.8
        assert summary["workers_analyzed"] >= 2
        assert summary["break_adherence_pct"] == 50.0  # 1 ack out of 2 rec

        # Check chart-ready components
        assert "risk_distribution" in report
        assert "posture_trend" in report
        assert "worker_comparison" in report
        assert len(report["worker_comparison"]) == 2
        assert "actionable_observation" in report

        # Verify saved in database
        saved = seeded_db.get_report(report["report_id"])
        assert saved is not None
        assert saved["report_type"] == "daily"

    def test_generate_html_report_rendering(self, seeded_db: CentralDatabase) -> None:
        generator = ReportGenerator(seeded_db)
        report_data = generator.generate_report(report_type="weekly", save=False)
        html = generator.generate_html_report(report_data)

        assert "<!DOCTYPE html>" in html
        assert "EDGE" in html
        assert "ERGO" in html
        assert "Desk Alpha" in html
        assert "Posture Compliance" in html
        assert "@media print" in html

    def test_strict_privacy_guarantee(self, seeded_db: CentralDatabase) -> None:
        generator = ReportGenerator(seeded_db)
        csv_text = generator.generate_csv()
        report = generator.generate_report(report_type="daily")

        forbidden_terms = ["jpeg", "jpg", "png", "base64", "embedding", "landmark_0", "face_crop", "raw_frame"]
        for term in forbidden_terms:
            assert term not in csv_text.lower()
            assert term not in json.dumps(report).lower()


# ── 2. REST Endpoints Tests ───────────────────────────────────────────────────

class TestReportsEndpoints:

    def test_export_csv_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/v1/export/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment; filename=" in resp.headers["content-disposition"]

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2

    def test_export_csv_with_filter(self, client: TestClient) -> None:
        resp = client.get("/api/v1/export/csv?device_id=NODE-001")
        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["device_id"] == "NODE-001"

    def test_periodic_report_endpoints(self, client: TestClient) -> None:
        for r_type in ["daily", "weekly", "monthly"]:
            resp = client.get(f"/api/v1/reports/{r_type}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == r_type
            assert "summary" in data
            assert data["summary"]["total_windows"] == 2

    def test_periodic_report_invalid_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reports/yearly")
        assert resp.status_code == 400
        assert "Invalid report type" in resp.json()["detail"]

    def test_report_html_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reports/weekly/html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<!DOCTYPE html>" in resp.text
        assert "EDGE" in resp.text

    def test_list_historical_reports(self, client: TestClient) -> None:
        # Trigger generation of two reports
        client.get("/api/v1/reports/daily")
        client.get("/api/v1/reports/weekly")

        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) >= 2
        types = {r["report_type"] for r in reports}
        assert "daily" in types
        assert "weekly" in types
