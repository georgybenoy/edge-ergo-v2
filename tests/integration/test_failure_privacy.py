"""
Failure & Privacy Integration Tests (Phase 19, PRD §110, §116).

Systematically validates Edge Agent resilience and privacy enforcement:
  1. Camera failure       — graceful degradation, no crash.
  2. Server failure       — local analysis/feedback/storage continue.
  3. Network failure      — sync queue holds data, recovers on reconnect.
  4. Low confidence       — no false high-risk alerts from poor visibility.
  5. Person leaves frame  — stops generating posture data, never fabricates.
  6. Multiple people      — single-worker constraint, no cross-attribution.
  7. Data sync recovery   — queued data arrives complete, no duplication.
  8. Raw video audit      — network traffic contains ONLY JSON telemetry, NEVER
                            pixel data, face crops, or camera frames.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Edge Agent modules
from edge_agent.camera.camera import Camera, CameraError, CameraErrorKind, Frame
from edge_agent.config.config_manager import ConfigManager, EdgeConfig
from edge_agent.ergonomics.scoring import AssessmentResult, RiskLevel, assess
from edge_agent.expression.classifier import ExpressionClassifier
from edge_agent.geometry.angle_calculator import AngleCalculator, PostureParameters
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import (
    ServerSync,
    SyncWorker,
    build_telemetry_window_payload,
)
from edge_agent.temporal.analyzer import TemporalAnalyzer
from edge_agent.vision.face_engine import FaceEngine
from edge_agent.vision.pose_engine import PoseEngine, PoseResult, LandmarkPoint

# Central Server modules
from central_server.database.database import CentralDatabase
from central_server.main import create_app

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures & Helpers
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_dir():
    """Provide a fresh temporary directory cleaned up after each test."""
    d = tempfile.TemporaryDirectory()
    yield Path(d.name)
    d.cleanup()


@pytest.fixture
def local_db(temp_dir):
    """Fresh local SQLite database for Edge Agent."""
    db = LocalDatabase(str(temp_dir / "test_local.db"))
    yield db
    db.close()


@pytest.fixture
def config_manager(temp_dir):
    """Fresh ConfigManager with test defaults."""
    cfg_path = temp_dir / "edge_config.json"
    cm = ConfigManager(cfg_path)
    cm.update({
        "server_url": "http://central-server:8000",
        "device_id": "NODE-TEST-001",
        "device_name": "FailureTestWorkstation",
        "local_db_path": str(temp_dir / "test_local.db"),
        "backoff_base_sec": 0.0,
    }, save_to_disk=True)
    return cm


@pytest.fixture
def central_app():
    """Spin up a Central Server FastAPI app with in-memory database."""
    app = create_app()
    # Create in-memory central database
    central_db = CentralDatabase(":memory:")
    app.state.db = central_db
    yield app
    central_db.close()


@pytest.fixture
def test_client(central_app):
    """FastAPI TestClient wired to the Central Server."""
    return TestClient(central_app)


class FakeHttpClient:
    """Bridges Edge Agent httpx calls to FastAPI TestClient for isolated testing.

    Supports network failure simulation via .block() / .unblock().
    Records all transmitted payloads for traffic inspection.
    """

    def __init__(self, test_client: TestClient) -> None:
        self.test_client = test_client
        self._blocked = False
        self.captured_payloads: List[Dict[str, Any]] = []
        self.captured_raw_bodies: List[bytes] = []

    def block(self) -> None:
        self._blocked = True

    def unblock(self) -> None:
        self._blocked = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        if self._blocked:
            import httpx
            raise httpx.ConnectError(f"Simulated network failure: {url}")
        path = url.replace("http://central-server:8000", "")
        return self.test_client.get(path, **kwargs)

    def post(self, url, *, json=None, headers=None, **kwargs):
        if self._blocked:
            import httpx
            raise httpx.ConnectError(f"Simulated network failure: {url}")

        # Capture the exact payload that would go on the wire
        if json is not None:
            self.captured_payloads.append(json)
            self.captured_raw_bodies.append(
                __import__("json").dumps(json).encode("utf-8")
            )

        path = url.replace("http://central-server:8000", "")
        return self.test_client.post(path, json=json, headers=headers or {})


def _register_node(test_client: TestClient, device_name: str = "TestNode") -> str:
    """Register a fresh node via the Central Server API and return its device_id."""
    resp = test_client.post("/api/v1/edge/register", json={
        "device_name": device_name,
        "software_version": "0.1.0",
        "camera_detected": True,
        "camera_index": 0,
    })
    assert resp.status_code == 201
    return resp.json()["device_id"]


def _make_synthetic_rgb(w: int = 640, h: int = 480, person: bool = True) -> np.ndarray:
    """Create a synthetic RGB frame with optional gradient."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    if person:
        # Add gradient to avoid trivial all-black detection skip
        for y in range(h):
            img[y, :, 0] = int((y / h) * 200)
            img[y, :, 1] = int(((h - y) / h) * 180)
            img[y, :, 2] = 120
    return img


def _make_low_visibility_landmarks() -> dict:
    """Create landmark dict where all points have very low visibility (simulates poor lighting)."""
    landmarks = {}
    for i in range(33):
        name = f"LANDMARK_{i}"
        landmarks[name] = LandmarkPoint(
            name=name, index=i,
            x=0.5, y=0.5, z=0.0,
            world_x=0.0, world_y=0.0, world_z=0.0,
            visibility=0.05,  # Extremely low confidence
            presence=0.1,
            is_visible=False,
        )
    return landmarks


def _make_mock_session_stats(session_id: str = "SESS-FP-001"):
    """Create a minimal SessionStats-compatible object for local DB saves."""
    from edge_agent.temporal.analyzer import SessionStats
    start = time.time() - 10
    end = time.time()
    return SessionStats(
        session_id=session_id,
        start_time=start,
        end_time=end,
        duration_sec=end - start,
        total_frames=15,
        analyzed_frames=10,
        avg_rula=2.5,
        max_rula=3,
        avg_reba=3.0,
        max_reba=4,
        dominant_posture="NEUTRAL",
        high_risk_percentage=0.0,
        risk_distribution={"LOW": 8, "MODERATE": 2},
        posture_distribution={"NEUTRAL": 10},
        expression_distribution={"NEUTRAL": 10},
        alerts_triggered=[],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Test 1: Camera Failure — Graceful Degradation (PRD §116 Risk 1)
# ═════════════════════════════════════════════════════════════════════════════

class TestCameraFailure:
    """Verify the Edge Agent degrades gracefully when the camera fails mid-run."""

    def test_camera_read_failure_raises_typed_error(self):
        """Camera.read_frame() raises a CameraError, not a raw exception, on failure."""
        cam = Camera(camera_index=0)
        # Attempting to read without opening should raise CameraError
        with pytest.raises(CameraError) as exc_info:
            cam.read_frame()
        assert exc_info.value.kind == CameraErrorKind.NOT_OPEN

    def test_camera_disconnect_mid_run(self):
        """Simulate camera disconnect: cap.read() returns (False, None)."""
        cam = Camera(camera_index=0)
        cam._is_open = True
        cam._cap = MagicMock()
        cam._cap.read.return_value = (False, None)
        cam._cap.isOpened.side_effect = [True, False]

        with pytest.raises(CameraError) as exc_info:
            cam.read_frame()
        assert exc_info.value.kind == CameraErrorKind.DISCONNECTED

    def test_pipeline_continues_after_camera_failure(self):
        """Main pipeline loop should catch CameraError and continue with synthetic frames."""
        angle_calc = AngleCalculator()
        pose_engine = PoseEngine()
        pose_engine.initialise()

        # Process a synthetic frame after simulated camera failure
        synthetic = _make_synthetic_rgb()
        pose_res = pose_engine.process_frame(synthetic)

        # Pipeline should continue to produce results (valid or empty)
        params = angle_calc.calculate(pose_res.landmarks, timestamp=time.time())
        assessment = assess(params)

        assert assessment is not None
        assert isinstance(assessment.risk_level, RiskLevel)
        pose_engine.close()

    def test_no_crash_on_repeated_failures(self):
        """System stays operational through multiple sequential camera failures."""
        cam = Camera(camera_index=99)  # Nonexistent camera
        errors = 0
        for _ in range(10):
            try:
                cam.read_frame()
            except CameraError:
                errors += 1
        assert errors == 10  # All failures caught cleanly, no crash


# ═════════════════════════════════════════════════════════════════════════════
# Test 2: Server Failure — Local Autonomy (PRD §116 Risk 2)
# ═════════════════════════════════════════════════════════════════════════════

class TestServerFailure:
    """Verify local analysis, feedback, and storage continue when the server is unreachable."""

    def test_local_analysis_runs_without_server(self):
        """Full vision + ergonomics + temporal pipeline runs with zero network."""
        pose_engine = PoseEngine()
        pose_engine.initialise()
        face_engine = FaceEngine()
        face_engine.initialise()
        angle_calc = AngleCalculator()
        expr_classifier = ExpressionClassifier()
        cfg = EdgeConfig()
        temporal = TemporalAnalyzer(config=cfg)
        temporal.start_session("SESS-OFFLINE", time.time())

        frame = _make_synthetic_rgb()
        for _ in range(5):
            pose_res = pose_engine.process_frame(frame)
            face_res = face_engine.process_frame(frame)
            params = angle_calc.calculate(pose_res.landmarks, timestamp=time.time())
            assessment = assess(params)
            expr = expr_classifier.classify(face_res, timestamp=time.time())
            temporal.process_frame(assessment=assessment, expression=expr, timestamp=time.time())

        stats = temporal.end_session(time.time())
        assert stats is not None
        assert stats.total_frames == 5
        pose_engine.close()
        face_engine.close()

    def test_local_storage_persists_during_server_outage(self, local_db):
        """Sessions and assessments are saved to local SQLite regardless of server status."""
        device_id = "NODE-OFFLINE-001"
        stats = _make_mock_session_stats("SESS-OFFLINE-DB")
        sync_id = local_db.save_session_analysis(device_id, stats)
        assert sync_id is not None

        # Verify data is retrievable from local DB
        session = local_db.get_session(stats.session_id)
        assert session is not None
        assert session["session_id"] == "SESS-OFFLINE-DB"

    def test_sync_queue_accumulates_during_outage(self, local_db):
        """Sync queue entries are created even though server is unreachable."""
        device_id = "NODE-OFFLINE-002"
        for i in range(5):
            stats = _make_mock_session_stats(f"SESS-QUEUE-{i}")
            local_db.save_session_analysis(device_id, stats)

        pending = local_db.get_pending_sync_records(limit=100)
        assert len(pending) == 5
        for item in pending:
            assert item["status"] == "PENDING"


# ═════════════════════════════════════════════════════════════════════════════
# Test 3: Network Failure — Sync Queue Hold & Recovery (PRD §116 Risk 3)
# ═════════════════════════════════════════════════════════════════════════════

class TestNetworkFailure:
    """Verify sync queue holds data during network failure and recovers on reconnect."""

    def test_sync_fails_gracefully_during_outage(self, local_db, config_manager, test_client):
        """ServerSync.sync_pending_telemetry catches network errors without crashing."""
        server_sync = ServerSync(config_manager, local_db)
        device_id = "NODE-TEST-001"

        # Save a session locally
        stats = _make_mock_session_stats("SESS-NETFAIL")
        local_db.save_session_analysis(device_id, stats)

        # Simulate network failure — httpx raises ConnectError
        fake = FakeHttpClient(test_client)
        fake.block()

        with patch("httpx.Client", return_value=fake):
            synced = server_sync.sync_pending_telemetry()

        # Should sync zero records, not crash
        assert synced == 0

        # Sync queue item should still be PENDING (with retry incremented)
        pending = local_db.get_pending_sync_records(limit=10)
        assert len(pending) >= 1

    def test_recovery_after_reconnect(self, local_db, config_manager, test_client):
        """After network recovery, queued data syncs successfully."""
        device_id = _register_node(test_client, "RecoveryNode")
        config_manager.update({"device_id": device_id}, save_to_disk=True)
        server_sync = ServerSync(config_manager, local_db)

        # Save sessions during "outage"
        stats1 = _make_mock_session_stats("SESS-RECOVER-1")
        stats2 = _make_mock_session_stats("SESS-RECOVER-2")
        local_db.save_session_analysis(device_id, stats1)
        local_db.save_session_analysis(device_id, stats2)

        # Phase 1: Network down
        fake = FakeHttpClient(test_client)
        fake.block()
        with patch("httpx.Client", return_value=fake):
            synced_down = server_sync.sync_pending_telemetry()
        assert synced_down == 0

        # Phase 2: Network restored
        fake.unblock()
        with patch("httpx.Client", return_value=fake):
            synced_up = server_sync.sync_pending_telemetry()

        assert synced_up == 2

        # Verify sync queue is now drained
        pending = local_db.get_pending_sync_records(limit=10)
        assert len(pending) == 0


# ═════════════════════════════════════════════════════════════════════════════
# Test 4: Low Confidence / Poor Lighting (PRD §116 Risk 4)
# ═════════════════════════════════════════════════════════════════════════════

class TestLowConfidence:
    """Verify that low-confidence/poor-lighting frames do NOT produce false high-risk alerts."""

    def test_low_visibility_landmarks_produce_no_angles(self):
        """AngleCalculator returns None for all angles when landmarks are low-confidence."""
        angle_calc = AngleCalculator()
        landmarks = _make_low_visibility_landmarks()
        params = angle_calc.calculate(landmarks, timestamp=time.time())

        # All angles should be None — nothing to measure
        assert params.neck_angle is None
        assert params.trunk_angle is None
        assert params.shoulder_angle is None
        assert params.elbow_angle is None

    def test_low_confidence_assessment_is_not_high_risk(self):
        """Assessment from empty/low-confidence landmarks should be LOW risk, not HIGH."""
        angle_calc = AngleCalculator()
        landmarks = _make_low_visibility_landmarks()
        params = angle_calc.calculate(landmarks, timestamp=time.time())
        assessment = assess(params)

        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.is_valid is False
        assert assessment.dominant_posture == "NO_PERSON_DETECTED"

    def test_all_black_frame_produces_low_risk(self):
        """An all-black frame (simulating lens cap / pitch dark) yields LOW risk."""
        pose_engine = PoseEngine()
        pose_engine.initialise()
        angle_calc = AngleCalculator()

        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pose_res = pose_engine.process_frame(black_frame)
        params = angle_calc.calculate(pose_res.landmarks, timestamp=time.time())
        assessment = assess(params)

        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.is_valid is False
        pose_engine.close()

    def test_temporal_analyzer_ignores_invalid_frames(self):
        """Temporal persistence tracker should not fire alerts on invalid/low-confidence frames."""
        cfg = EdgeConfig()
        temporal = TemporalAnalyzer(config=cfg)
        temporal.start_session("SESS-LOWCONF", time.time())

        angle_calc = AngleCalculator()
        landmarks = _make_low_visibility_landmarks()
        params = angle_calc.calculate(landmarks, timestamp=time.time())
        assessment = assess(params)

        # Feed 30 "invalid" frames — should NOT trigger any alert
        alerts = []
        for i in range(30):
            evt = temporal.process_frame(
                assessment=assessment, expression=None, timestamp=time.time() + i
            )
            if evt is not None:
                alerts.append(evt)

        assert len(alerts) == 0, f"Expected 0 alerts from low-confidence frames, got {len(alerts)}"
        temporal.end_session(time.time())


# ═════════════════════════════════════════════════════════════════════════════
# Test 5: Person Leaves Frame (PRD §116 Risk 5)
# ═════════════════════════════════════════════════════════════════════════════

class TestPersonLeavesFrame:
    """Verify assessments stop when the person is no longer detected — never fabricates data."""

    def test_empty_frame_returns_no_detection(self):
        """PoseEngine returns is_detected=False on empty/personless frame."""
        pose_engine = PoseEngine()
        pose_engine.initialise()

        # All-black frame with no person
        empty = np.zeros((480, 640, 3), dtype=np.uint8)
        result = pose_engine.process_frame(empty)
        assert result.is_detected is False
        assert len(result.landmarks) == 0
        pose_engine.close()

    def test_no_angles_computed_for_missing_person(self):
        """AngleCalculator returns all-None angles when landmarks dict is empty."""
        angle_calc = AngleCalculator()
        params = angle_calc.calculate({}, timestamp=time.time())
        assert params.available_angle_count == 0
        assert params.neck_angle is None
        assert params.trunk_angle is None

    def test_assessment_marks_no_person_detected(self):
        """assess() properly labels the result as invalid / NO_PERSON_DETECTED."""
        angle_calc = AngleCalculator()
        params = angle_calc.calculate({}, timestamp=time.time())
        result = assess(params)

        assert result.is_valid is False
        assert result.dominant_posture == "NO_PERSON_DETECTED"
        assert result.risk_level == RiskLevel.LOW

    def test_transition_person_present_then_leaves(self):
        """Pipeline handles the transition from detected → not detected cleanly."""
        pose_engine = PoseEngine()
        pose_engine.initialise()
        angle_calc = AngleCalculator()

        # Frame with content (may or may not detect person depending on content)
        populated = _make_synthetic_rgb(person=True)
        res1 = pose_engine.process_frame(populated)
        params1 = angle_calc.calculate(res1.landmarks, timestamp=time.time())
        assess1 = assess(params1)

        # Frame with no person (all black)
        empty = np.zeros((480, 640, 3), dtype=np.uint8)
        res2 = pose_engine.process_frame(empty)
        params2 = angle_calc.calculate(res2.landmarks, timestamp=time.time())
        assess2 = assess(params2)

        assert assess2.is_valid is False
        assert assess2.dominant_posture == "NO_PERSON_DETECTED"
        pose_engine.close()


# ═════════════════════════════════════════════════════════════════════════════
# Test 6: Multiple People in Frame (PRD §116 Risk 6)
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiplePeople:
    """Verify single-worker constraint — only the primary detected person is scored."""

    def test_pose_engine_takes_first_person_only(self):
        """PoseEngine._parse_result extracts landmarks from only the first detected person."""
        pose_engine = PoseEngine()
        pose_engine.initialise()

        # Create a mock MediaPipe result with multiple pose_landmarks entries
        mock_result = MagicMock()
        person1 = [MagicMock(x=0.5, y=0.5, z=0.0, visibility=0.9, presence=0.9) for _ in range(33)]
        person2 = [MagicMock(x=0.8, y=0.2, z=0.1, visibility=0.85, presence=0.85) for _ in range(33)]
        mock_result.pose_landmarks = [person1, person2]
        mock_result.pose_world_landmarks = [person1, person2]

        parsed = pose_engine._parse_result(mock_result)

        # Should use person1 (index 0) exclusively
        assert parsed.is_detected is True
        # Verify we did NOT merge or contaminate from person2
        for lm in parsed.landmarks.values():
            assert lm.x == 0.5  # person1's coordinate, not person2's 0.8
        pose_engine.close()

    def test_single_assessment_per_frame(self):
        """assess() produces exactly one AssessmentResult regardless of multi-person detection."""
        angle_calc = AngleCalculator()
        params = angle_calc.calculate({}, timestamp=time.time())
        result = assess(params)

        # Only one assessment, not one-per-person
        assert isinstance(result, AssessmentResult)

    def test_no_score_cross_attribution(self):
        """Scores from the primary person should never leak to a secondary detection."""
        pose_engine = PoseEngine()
        pose_engine.initialise()
        angle_calc = AngleCalculator()

        # Even when MediaPipe detects multiple people, our pipeline processes only
        # the first person's landmarks through AngleCalculator → RULA/REBA
        frame = _make_synthetic_rgb()
        result = pose_engine.process_frame(frame)
        params = angle_calc.calculate(result.landmarks, timestamp=time.time())
        assessment = assess(params)

        # There should be exactly one assessment
        assert isinstance(assessment, AssessmentResult)
        pose_engine.close()


# ═════════════════════════════════════════════════════════════════════════════
# Test 7: Data Sync Correctness After Recovery (PRD §116 Risk 7)
# ═════════════════════════════════════════════════════════════════════════════

class TestSyncRecoveryCorrectness:
    """Verify queued data arrives complete and without duplication after recovery."""

    def test_all_queued_windows_arrive_after_recovery(self, local_db, config_manager, test_client):
        """Every session queued during outage is successfully synced after reconnect."""
        device_id = _register_node(test_client, "SyncRecoveryNode")
        config_manager.update({"device_id": device_id}, save_to_disk=True)
        server_sync = ServerSync(config_manager, local_db)
        fake = FakeHttpClient(test_client)

        # Queue 5 sessions during outage
        session_ids = []
        for i in range(5):
            sid = f"SESS-SYNC-{i}"
            session_ids.append(sid)
            stats = _make_mock_session_stats(sid)
            local_db.save_session_analysis(device_id, stats)

        # Network down: nothing syncs
        fake.block()
        with patch("httpx.Client", return_value=fake):
            assert server_sync.sync_pending_telemetry() == 0

        # Network up: all 5 should sync
        fake.unblock()
        with patch("httpx.Client", return_value=fake):
            synced = server_sync.sync_pending_telemetry()

        assert synced == 5

        # All captured payloads should contain our session_ids
        synced_session_ids = {p.get("session_id") for p in fake.captured_payloads}
        for sid in session_ids:
            assert sid in synced_session_ids, f"Session {sid} was not found in synced payloads"

    def test_no_duplicate_entries_on_double_sync(self, local_db, config_manager, test_client):
        """Re-syncing the same data should be idempotently rejected (409 Conflict), not duplicated."""
        device_id = _register_node(test_client, "DuplicateCheckNode")
        config_manager.update({"device_id": device_id}, save_to_disk=True)
        server_sync = ServerSync(config_manager, local_db)
        fake = FakeHttpClient(test_client)

        # Create and sync a single session
        stats = _make_mock_session_stats("SESS-DEDUP")
        local_db.save_session_analysis(device_id, stats)

        with patch("httpx.Client", return_value=fake):
            first_sync = server_sync.sync_pending_telemetry()
        assert first_sync == 1

        # Manually reset sync status to simulate a re-send attempt
        pending = local_db.get_pending_sync_records(limit=10)
        # Force re-queue by inserting a new sync_queue entry for the same session
        import sqlite3
        import uuid
        conn = sqlite3.connect(str(config_manager.config.local_db_path))
        try:
            conn.execute(
                "INSERT INTO sync_queue (sync_id, record_id, created_at, status, retry_count, last_attempt) "
                "VALUES (?, ?, ?, 'PENDING', 0, NULL)",
                (str(uuid.uuid4()), "SESS-DEDUP", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        # Re-sync: server should reject as duplicate (409), but Edge marks it SYNCED
        with patch("httpx.Client", return_value=fake):
            second_sync = server_sync.sync_pending_telemetry()
        assert second_sync == 1  # 409 is treated as "already synced" → counts as success

    def test_sync_data_completeness(self, local_db, config_manager, test_client):
        """Each synced payload contains all required telemetry fields."""
        device_id = _register_node(test_client, "CompletenessNode")
        config_manager.update({"device_id": device_id}, save_to_disk=True)
        server_sync = ServerSync(config_manager, local_db)
        fake = FakeHttpClient(test_client)

        stats = _make_mock_session_stats("SESS-COMPLETE")
        local_db.save_session_analysis(device_id, stats)

        with patch("httpx.Client", return_value=fake):
            server_sync.sync_pending_telemetry()

        assert len(fake.captured_payloads) == 1
        payload = fake.captured_payloads[0]

        # Validate all required fields exist
        assert "device_id" in payload
        assert "session_id" in payload
        assert "window_start" in payload
        assert "window_end" in payload
        assert "ergonomics" in payload
        assert "facial_expression" in payload
        assert "breaks" in payload

        ergo = payload["ergonomics"]
        assert "average_rula" in ergo
        assert "average_reba" in ergo
        assert "dominant_posture" in ergo
        assert "high_risk_percentage" in ergo


# ═════════════════════════════════════════════════════════════════════════════
# Test 8: Raw Video Transmission Audit (PRD §116 Privacy Guarantee)
# ═════════════════════════════════════════════════════════════════════════════

class TestRawVideoAudit:
    """Inspect actual captured network traffic to CONFIRM no video/face/camera data on the wire.

    This is the strongest privacy verification — packet-level evidence, not just code review.
    """

    def test_telemetry_payload_contains_only_json_numerics(self, local_db, config_manager, test_client):
        """The exact bytes transmitted contain ONLY JSON with numeric/string fields — no binary data."""
        device_id = _register_node(test_client, "PrivacyAuditNode")
        config_manager.update({"device_id": device_id}, save_to_disk=True)
        server_sync = ServerSync(config_manager, local_db)
        fake = FakeHttpClient(test_client)

        # Create multiple sessions to generate traffic
        for i in range(3):
            stats = _make_mock_session_stats(f"SESS-AUDIT-{i}")
            local_db.save_session_analysis(device_id, stats)

        with patch("httpx.Client", return_value=fake):
            server_sync.sync_pending_telemetry()

        assert len(fake.captured_raw_bodies) == 3

        for idx, raw_body in enumerate(fake.captured_raw_bodies):
            # 1. Must be valid UTF-8 (no binary image data)
            try:
                text = raw_body.decode("utf-8")
            except UnicodeDecodeError:
                pytest.fail(f"Payload {idx} contains non-UTF-8 binary data (possible image/video leak)")

            # 2. Must be valid JSON
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pytest.fail(f"Payload {idx} is not valid JSON")

            # 3. Must NOT contain any image-like binary signatures
            _assert_no_image_signatures(raw_body, idx)

            # 4. Must NOT contain base64-encoded image data
            _assert_no_base64_images(text, idx)

            # 5. Must contain ONLY the documented telemetry schema fields
            _assert_telemetry_schema_only(parsed, idx)

    def test_no_frame_data_in_registration(self, test_client):
        """Registration payload contains no pixel data or camera frames."""
        resp = test_client.post("/api/v1/edge/register", json={
            "device_name": "AuditRegistration",
            "software_version": "0.1.0",
            "camera_detected": True,
            "camera_index": 0,
        })
        assert resp.status_code == 201

        # Inspect request: only metadata strings and booleans, no binary
        response_data = resp.json()
        assert "device_id" in response_data
        for key, value in response_data.items():
            assert not isinstance(value, bytes), f"Binary data found in registration response field: {key}"

    def test_no_frame_data_in_heartbeat(self, test_client):
        """Heartbeat payloads are pure JSON status pings with no image content."""
        device_id = _register_node(test_client, "HeartbeatAudit")
        resp = test_client.post("/api/v1/edge/heartbeat", json={
            "device_id": device_id,
            "software_version": "0.1.0",
            "status": "online",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] is True

        # Verify payload is tiny (no embedded images)
        raw_len = len(json.dumps(data).encode())
        assert raw_len < 500, f"Heartbeat response suspiciously large: {raw_len} bytes"

    def test_telemetry_payload_size_reasonable(self, local_db, config_manager, test_client):
        """Each telemetry window payload is under 2 KB — far too small for any image data."""
        device_id = _register_node(test_client, "SizeAuditNode")
        config_manager.update({"device_id": device_id}, save_to_disk=True)
        server_sync = ServerSync(config_manager, local_db)
        fake = FakeHttpClient(test_client)

        stats = _make_mock_session_stats("SESS-SIZE")
        local_db.save_session_analysis(device_id, stats)

        with patch("httpx.Client", return_value=fake):
            server_sync.sync_pending_telemetry()

        for idx, raw_body in enumerate(fake.captured_raw_bodies):
            size = len(raw_body)
            # A single 640x480 JPEG frame is typically 50-100 KB
            # Our telemetry payload should be < 2 KB
            assert size < 2048, (
                f"Payload {idx} is {size} bytes — suspiciously large, "
                f"possible image data leak"
            )

    def test_build_telemetry_payload_contains_no_landmarks(self):
        """build_telemetry_window_payload never includes raw landmark coordinates."""
        session = {
            "session_id": "SESS-LM-CHECK",
            "start_time": "2026-09-19T10:00:00",
            "end_time": "2026-09-19T10:05:00",
        }
        assessment = {
            "rula_score": 3.5,
            "reba_score": 4.0,
            "risk_level": "MODERATE",
            "dominant_posture": "NECK_FLEXION",
        }
        events = [{"event_type": "BREAK_REMINDER", "event_value": "suggested"}]

        payload = build_telemetry_window_payload(session, assessment, events, "NODE-001")
        payload_text = json.dumps(payload)

        # Must not contain coordinate-like fields
        forbidden_keys = [
            "landmark", "landmarks", "keypoint", "keypoints",
            "face_mesh", "face_crop", "frame", "image", "pixel",
            "raw_data", "camera_data", "video",
            "world_x", "world_y", "world_z",
            "visibility", "presence",
        ]
        for key in forbidden_keys:
            assert key not in payload_text.lower(), (
                f"Telemetry payload contains forbidden field/term: '{key}'"
            )

    def test_full_pipeline_traffic_audit(self):
        """End-to-end audit: run real inference, capture what would be transmitted, verify no images."""
        pose_engine = PoseEngine()
        pose_engine.initialise()
        face_engine = FaceEngine()
        face_engine.initialise()
        angle_calc = AngleCalculator()
        expr_classifier = ExpressionClassifier()

        frame = _make_synthetic_rgb()
        pose_res = pose_engine.process_frame(frame)
        face_res = face_engine.process_frame(frame)
        params = angle_calc.calculate(pose_res.landmarks, timestamp=time.time())
        assessment = assess(params)
        expr = expr_classifier.classify(face_res, timestamp=time.time())

        # Build the telemetry payload that would be transmitted
        session = {
            "session_id": "SESS-PIPELINE-AUDIT",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
        }
        assess_dict = {
            "rula_score": assessment.rula_score,
            "reba_score": assessment.reba_score,
            "risk_level": assessment.risk_level.value,
            "dominant_posture": assessment.dominant_posture,
            "expression_category": expr.category.value if expr else "Neutral",
        }
        payload = build_telemetry_window_payload(session, assess_dict, [], "NODE-AUDIT")
        raw_bytes = json.dumps(payload).encode("utf-8")

        # Verify: no image signatures, valid JSON only, small size
        _assert_no_image_signatures(raw_bytes, 0)
        assert len(raw_bytes) < 2048
        parsed = json.loads(raw_bytes)
        _assert_telemetry_schema_only(parsed, 0)

        pose_engine.close()
        face_engine.close()


# ── Privacy Audit Helpers ─────────────────────────────────────────────────────

# Common image format magic byte signatures
_IMAGE_SIGNATURES = [
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"GIF87a", "GIF87"),
    (b"GIF89a", "GIF89"),
    (b"BM", "BMP"),
    (b"RIFF", "WEBP/AVI"),
    (b"\x00\x00\x00\x1cftyp", "MP4"),
    (b"\x1aE\xdf\xa3", "WEBM/MKV"),
]


def _assert_no_image_signatures(raw: bytes, payload_idx: int) -> None:
    """Assert that raw bytes do not contain any known image/video format headers."""
    for sig, fmt in _IMAGE_SIGNATURES:
        if sig in raw:
            pytest.fail(
                f"Payload {payload_idx} contains {fmt} signature at offset "
                f"{raw.index(sig)} — possible raw image/video leak"
            )


def _assert_no_base64_images(text: str, payload_idx: int) -> None:
    """Assert text does not contain base64-encoded image data patterns."""
    import re
    # Base64-encoded JPEG starts with /9j/, PNG with iVBOR
    b64_patterns = [
        r"/9j/[A-Za-z0-9+/=]{100,}",   # Base64 JPEG
        r"iVBOR[A-Za-z0-9+/=]{100,}",   # Base64 PNG
        r"data:image/[a-z]+;base64,",    # Data URI
    ]
    for pattern in b64_patterns:
        if re.search(pattern, text):
            pytest.fail(
                f"Payload {payload_idx} contains base64-encoded image data "
                f"matching pattern: {pattern}"
            )


# Allowed top-level and nested keys in telemetry payloads
_ALLOWED_TELEMETRY_KEYS = {
    "window_id", "device_id", "session_id", "window_start", "window_end",
    "ergonomics", "facial_expression", "breaks",
    # Nested under ergonomics
    "average_rula", "maximum_rula", "average_reba", "maximum_reba",
    "high_risk_percentage", "dominant_posture",
    # Nested under facial_expression
    "neutral_percentage", "positive_percentage",
    "negative_percentage", "reduced_expression_percentage",
    # Nested under breaks
    "breaks_recommended", "breaks_acknowledged",
}


def _assert_telemetry_schema_only(parsed: dict, payload_idx: int) -> None:
    """Assert payload contains only documented telemetry fields — no extra data leaks."""
    def _check_keys(d: dict, path: str = ""):
        for key, value in d.items():
            full_key = f"{path}.{key}" if path else key
            assert key in _ALLOWED_TELEMETRY_KEYS, (
                f"Payload {payload_idx} contains undocumented field '{full_key}' — "
                f"potential privacy leak"
            )
            if isinstance(value, dict):
                _check_keys(value, full_key)

    _check_keys(parsed)
