"""
Unit and integration tests for Phase 9: Local Storage (PRD §37, §38, §39).

Verifies:
  1. Automatic schema initialization on fresh install.
  2. Device registration and query helpers.
  3. Atomic writes for completed temporal sessions, assessments, and events.
  4. Enqueuing sync_queue items and state transitions.
  5. Crash / failure simulation mid-write ensuring rollback and zero DB corruption.
  6. Overlay read helpers (latest assessment, sync summary).
  7. Offline-first resilience: multiple sessions buffer in sync_queue.
  8. Configuration store key/value persistence.
  9. Privacy audit: database schema stores no raw video, crops, or landmarks.
"""

import json
from pathlib import Path
import sqlite3
import time
import pytest

from edge_agent.storage.local_db import LocalDatabase, SCHEMA_SQL
from edge_agent.temporal.analyzer import AlertEvent, SessionStats


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_db() -> LocalDatabase:
    """Provides an in-memory LocalDatabase instance."""
    db = LocalDatabase(":memory:")
    yield db
    db.close()


@pytest.fixture
def temp_db(tmp_path: Path) -> LocalDatabase:
    """Provides a file-backed LocalDatabase instance in a temporary folder."""
    db_file = tmp_path / "test_edgeergo.db"
    db = LocalDatabase(db_file)
    yield db
    db.close()


# ── 1. Schema & Initialization Tests ──────────────────────────────────────────

class TestSchemaInitialization:

    def test_fresh_install_creates_file_and_all_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "fresh_install" / "edgeergo.db"
        assert not db_path.exists()

        db = LocalDatabase(db_path)
        assert db_path.exists()

        # Verify all tables exist
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row["name"] for row in cursor.fetchall()}

        expected_tables = {"device", "session", "assessment", "events", "sync_queue", "configuration"}
        assert expected_tables.issubset(tables)
        db.close()

    def test_indexes_are_created(self, mem_db: LocalDatabase) -> None:
        with mem_db.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row["name"] for row in cursor.fetchall()}

        expected_indexes = {
            "idx_session_start",
            "idx_assessment_session",
            "idx_events_session",
            "idx_sync_queue_status",
        }
        assert expected_indexes.issubset(indexes)

    def test_foreign_key_constraints_enforced(self, mem_db: LocalDatabase) -> None:
        # Attempting to insert a session with a non-existent device_id must fail foreign key constraint
        with pytest.raises(sqlite3.IntegrityError):
            mem_db.record_session(
                session_id="sess-001",
                device_id="non-existent-device",
                start_time="2026-09-19T09:00:00Z",
                end_time="2026-09-19T09:05:00Z",
                duration=300.0,
            )


# ── 2. Device Registration ───────────────────────────────────────────────────

class TestDeviceManagement:

    def test_register_and_get_device(self, mem_db: LocalDatabase) -> None:
        device_info = mem_db.register_device(
            device_id="dev-pc-01",
            device_name="Floor-1-Desk-4",
            software_version="0.2.0",
        )
        assert device_info["device_id"] == "dev-pc-01"

        fetched = mem_db.get_device("dev-pc-01")
        assert fetched is not None
        assert fetched["device_name"] == "Floor-1-Desk-4"
        assert fetched["software_version"] == "0.2.0"
        assert fetched["last_sync"] is None

    def test_device_update_sync_time(self, mem_db: LocalDatabase) -> None:
        mem_db.register_device(device_id="dev-pc-01")
        mem_db.update_device_sync("dev-pc-01", "2026-09-19T10:00:00Z")

        fetched = mem_db.get_device("dev-pc-01")
        assert fetched["last_sync"] == "2026-09-19T10:00:00Z"


# ── 3. Session & Temporal Write Path ──────────────────────────────────────────

class TestSessionWritePath:

    def test_save_session_analysis_creates_all_records(self, mem_db: LocalDatabase) -> None:
        alert = AlertEvent(
            condition="NECK_FLEXION",
            risk_level="HIGH",
            rula_score=6,
            reba_score=5,
            duration_sec=22.5,
            timestamp=1789725620.0,
            message="Maintain neutral neck position",
        )

        stats = SessionStats(
            session_id="sess-test-100",
            start_time=1789725600.0,
            end_time=1789725900.0,
            duration_sec=300.0,
            total_frames=300,
            analyzed_frames=300,
            avg_rula=5.2,
            max_rula=7,
            avg_reba=4.8,
            max_reba=6,
            dominant_posture="NECK_FLEXION",
            high_risk_percentage=35.0,
            alerts_triggered=[alert],
        )

        sync_id = mem_db.save_session_analysis(
            device_id="dev-alpha-01",
            session_stats=stats,
            expression_category="Neutral",
        )
        assert sync_id is not None

        # Verify session table
        session = mem_db.get_session("sess-test-100")
        assert session is not None
        assert session["device_id"] == "dev-alpha-01"
        assert session["duration"] == 300.0

        # Verify assessment table
        assessment = mem_db.get_latest_assessment("sess-test-100")
        assert assessment is not None
        assert assessment["session_id"] == "sess-test-100"
        assert assessment["rula_score"] == 5  # round(5.2)
        assert assessment["reba_score"] == 5  # round(4.8)
        assert assessment["risk_level"] == "HIGH"
        assert assessment["dominant_posture"] == "NECK_FLEXION"
        assert assessment["expression_category"] == "Neutral"

        # Verify events table
        events = mem_db.get_events_for_session("sess-test-100")
        assert len(events) == 1
        assert events[0]["event_type"] == "ALERT"
        val = json.loads(events[0]["event_value"])
        assert val["condition"] == "NECK_FLEXION"
        assert val["duration_sec"] == 22.5

        # Verify sync_queue table
        pending = mem_db.get_pending_sync_records()
        assert len(pending) == 1
        assert pending[0]["sync_id"] == sync_id
        assert pending[0]["record_id"] == "sess-test-100"
        assert pending[0]["status"] == "PENDING"
        assert pending[0]["retry_count"] == 0


# ── 4. Crash & Transaction Rollback Durability ────────────────────────────────

class TestTransactionDurability:

    def test_simulated_crash_mid_write_rolls_back_completely(self, temp_db: LocalDatabase) -> None:
        """Simulate a failure during session persistence (e.g. invalid event insert).

        The entire transaction must roll back cleanly, leaving 0 rows in all tables.
        """
        temp_db.register_device("dev-durable-01")

        bad_stats = SessionStats(
            session_id="sess-fail-999",
            start_time=1789725600.0,
            end_time=1789725900.0,
            duration_sec=300.0,
            total_frames=10,
            analyzed_frames=10,
            avg_rula=4.0,
            max_rula=4,
            avg_reba=4.0,
            max_reba=4,
            dominant_posture="NEUTRAL",
            high_risk_percentage=0.0,
        )

        # Inject an event with non-string/unacceptable structure to trigger a forced crash
        class PoisonEvent:
            pass

        bad_stats.alerts_triggered = [PoisonEvent()]  # Will raise AttributeError during processing

        with pytest.raises(AttributeError):
            temp_db.save_session_analysis("dev-durable-01", bad_stats)

        # Confirm nothing was written to session, assessment, events, or sync_queue
        assert temp_db.get_session("sess-fail-999") is None
        assert temp_db.get_latest_assessment("sess-fail-999") is None
        assert len(temp_db.get_events_for_session("sess-fail-999")) == 0
        assert len(temp_db.get_pending_sync_records()) == 0


# ── 5. Offline Operation & Sync Queue Transitions ─────────────────────────────

class TestOfflineAndSyncQueue:

    def test_offline_buffering_multiple_sessions(self, mem_db: LocalDatabase) -> None:
        """Edge Agent buffers sessions locally when offline (PRD §39)."""
        mem_db.register_device("dev-offline")

        # Record 5 consecutive sessions without server sync
        for i in range(5):
            stats = SessionStats(
                session_id=f"sess-offline-{i}",
                start_time=1000.0 + (i * 600),
                end_time=1300.0 + (i * 600),
                duration_sec=300.0,
                total_frames=100,
                analyzed_frames=100,
                avg_rula=3.0,
                max_rula=4,
                avg_reba=3.0,
                max_reba=4,
                dominant_posture="NEUTRAL",
                high_risk_percentage=0.0,
            )
            mem_db.save_session_analysis("dev-offline", stats)

        # All 5 records must be buffered and pending
        summary = mem_db.get_sync_status_summary()
        assert summary["PENDING"] == 5
        assert summary["SYNCED"] == 0
        assert summary["TOTAL"] == 5

        pending = mem_db.get_pending_sync_records(limit=10)
        assert len(pending) == 5

    def test_sync_status_transitions_and_retry_count(self, mem_db: LocalDatabase) -> None:
        sync_id = mem_db.enqueue_sync(record_id="rec-001")

        # Mark in progress
        mem_db.update_sync_status(sync_id, status="IN_PROGRESS")
        summary = mem_db.get_sync_status_summary()
        assert summary["IN_PROGRESS"] == 1
        assert summary["PENDING"] == 0

        # Simulate network failure -> retry increment
        mem_db.update_sync_status(sync_id, status="PENDING", retry_increment=True)
        with mem_db.get_connection() as conn:
            row = conn.execute("SELECT * FROM sync_queue WHERE sync_id = ?", (sync_id,)).fetchone()
            assert row["retry_count"] == 1
            assert row["status"] == "PENDING"
            assert row["last_attempt"] is not None

        # Simulate eventual success
        mem_db.update_sync_status(sync_id, status="SYNCED")
        summary = mem_db.get_sync_status_summary()
        assert summary["SYNCED"] == 1
        assert summary["PENDING"] == 0


# ── 6. Read Helpers (Overlay & Dashboard) ─────────────────────────────────────

class TestReadHelpers:

    def test_latest_assessment_helper(self, mem_db: LocalDatabase) -> None:
        mem_db.register_device("dev-01")

        stats1 = SessionStats(
            session_id="sess-early",
            start_time=1000.0,
            end_time=1300.0,
            duration_sec=300.0,
            total_frames=10,
            analyzed_frames=10,
            avg_rula=2.0,
            max_rula=2,
            avg_reba=2.0,
            max_reba=2,
            dominant_posture="NEUTRAL",
            high_risk_percentage=0.0,
        )
        mem_db.save_session_analysis("dev-01", stats1)

        time.sleep(0.01)

        stats2 = SessionStats(
            session_id="sess-late",
            start_time=2000.0,
            end_time=2300.0,
            duration_sec=300.0,
            total_frames=10,
            analyzed_frames=10,
            avg_rula=7.0,
            max_rula=7,
            avg_reba=7.0,
            max_reba=7,
            dominant_posture="TRUNK_FLEXION",
            high_risk_percentage=80.0,
        )
        mem_db.save_session_analysis("dev-01", stats2)

        latest = mem_db.get_latest_assessment()
        assert latest is not None
        assert latest["session_id"] == "sess-late"
        assert latest["dominant_posture"] == "TRUNK_FLEXION"
        assert latest["risk_level"] == "HIGH"

    def test_session_history_with_event_counts(self, mem_db: LocalDatabase) -> None:
        mem_db.register_device("dev-01")

        stats = SessionStats(
            session_id="sess-hist-1",
            start_time=1000.0,
            end_time=1300.0,
            duration_sec=300.0,
            total_frames=10,
            analyzed_frames=10,
            avg_rula=3.0,
            max_rula=3,
            avg_reba=3.0,
            max_reba=3,
            dominant_posture="NEUTRAL",
            high_risk_percentage=0.0,
            alerts_triggered=[
                AlertEvent("NECK_FLEXION", "HIGH", 5, 5, 20.0, 1050.0, "tip"),
                AlertEvent("TRUNK_FLEXION", "HIGH", 6, 6, 25.0, 1150.0, "tip"),
            ],
        )
        mem_db.save_session_analysis("dev-01", stats)

        history = mem_db.get_session_history(limit=5)
        assert len(history) == 1
        assert history[0]["session_id"] == "sess-hist-1"
        assert history[0]["event_count"] == 2


# ── 7. Configuration Store Tests ──────────────────────────────────────────────

class TestConfigurationStore:

    def test_set_and_get_config(self, mem_db: LocalDatabase) -> None:
        mem_db.set_config("monitoring_start_time", "08:30")
        mem_db.set_config("session_interval_min", 45)
        mem_db.set_config("features_enabled", {"pose": True, "face": False})

        assert mem_db.get_config("monitoring_start_time") == "08:30"
        assert mem_db.get_config("session_interval_min") == 45
        assert mem_db.get_config("features_enabled") == {"pose": True, "face": False}
        assert mem_db.get_config("unknown_key", "default_val") == "default_val"

    def test_get_all_config(self, mem_db: LocalDatabase) -> None:
        mem_db.set_config("k1", "v1")
        mem_db.set_config("k2", 42)

        all_cfg = mem_db.get_all_config()
        assert all_cfg["k1"] == "v1"
        assert all_cfg["k2"] == 42


# ── 9. Privacy & Data Minimization Audit ───────────────────────────────────────

class TestPrivacyCompliance:

    def test_no_forbidden_columns_in_local_schema(self, mem_db: LocalDatabase) -> None:
        """PRD §28, §38: Schema must NEVER contain columns for images, video, or coordinates."""
        forbidden_keywords = {
            "image", "frame", "crop", "video", "jpeg", "png", "bitmap",
            "landmark_x", "landmark_y", "landmark_z", "embedding", "raw"
        }

        with mem_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row["name"] for row in cursor.fetchall()]

            for table in tables:
                col_cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = [col["name"].lower() for col in col_cursor.fetchall()]
                for col in columns:
                    for forbidden in forbidden_keywords:
                        assert forbidden not in col, (
                            f"Privacy violation: Column '{col}' in table '{table}' "
                            f"contains forbidden keyword '{forbidden}'."
                        )


# ── 10. Temporal Engine Integration Cycle ─────────────────────────────────────

class TestTemporalEngineIntegrationCycle:

    def test_temporal_session_to_database_write_cycle(self, mem_db: LocalDatabase) -> None:
        """Verify the full pipeline from TemporalAnalyzer session completion to DB persistence."""
        from edge_agent.temporal.analyzer import TemporalAnalyzer
        from edge_agent.ergonomics.scoring import AssessmentResult, RiskLevel

        analyzer = TemporalAnalyzer(persistence_threshold_sec=5.0, alert_cooldown_sec=30.0)
        session_id = "cycle-session-01"
        analyzer.start_session(session_id=session_id, timestamp=100.0)

        from edge_agent.ergonomics.rula import RulaBreakdown
        from edge_agent.ergonomics.reba import RebaBreakdown
        from edge_agent.geometry.angle_calculator import PostureParameters

        # Feed 10 frames of high risk posture to accumulate stats
        for i in range(10):
            ts = 100.0 + (i * 1.0)
            mock_assess = AssessmentResult(
                rula_score=6,
                reba_score=6,
                risk_level=RiskLevel.HIGH,
                dominant_posture="NECK_FLEXION",
                rula_action_level=3,
                reba_action_level=3,
                rula_breakdown=RulaBreakdown(grand_score=6),
                reba_breakdown=RebaBreakdown(grand_score=6),
                posture_parameters=PostureParameters(timestamp=ts),
                timestamp=ts,
            )
            analyzer.process_frame(mock_assess, None, timestamp=ts)

        # Complete session
        stats = analyzer.end_session(timestamp=110.0)
        assert stats is not None
        assert stats.session_id == session_id

        # Persist to local database
        sync_id = mem_db.save_session_analysis("device-cycle-test", stats, expression_category="Neutral")
        assert sync_id is not None

        # Query latest assessment
        latest = mem_db.get_latest_assessment()
        assert latest is not None
        assert latest["session_id"] == "cycle-session-01"
        assert latest["rula_score"] == 6
        assert latest["risk_level"] == "HIGH"
        assert latest["dominant_posture"] == "NECK_FLEXION"

        # Check sync summary
        summary = mem_db.get_sync_status_summary()
        assert summary["PENDING"] == 1

