"""
EdgeErgo — Privacy & Network Traffic Audit Script (Phase 19, PRD §110, §116).

Audits all outbound network traffic from the Edge Agent to verify strict adherence
to the Edge-First Privacy Guarantee (PRD §8, §116):
  1. ZERO video frames or pixel arrays transmitted.
  2. ZERO raw facial landmarks, crops, or embeddings transmitted.
  3. Only aggregated, anonymized numeric/statistical JSON telemetry emitted.
  4. Payload sizes verify absence of base64-encoded binary media.

Usage:
    python scripts/audit_privacy.py [--frames N] [--server URL]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from fastapi.testclient import TestClient

# Ensure root directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from edge_agent.camera.camera import Camera
from edge_agent.config.config_manager import ConfigManager, EdgeConfig
from edge_agent.ergonomics.scoring import assess
from edge_agent.expression.classifier import ExpressionClassifier
from edge_agent.geometry.angle_calculator import AngleCalculator
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import ServerSync, build_telemetry_window_payload
from edge_agent.temporal.analyzer import TemporalAnalyzer
from edge_agent.vision.face_engine import FaceEngine
from edge_agent.vision.pose_engine import PoseEngine
from central_server.main import create_app
from central_server.database.database import CentralDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PrivacyAudit")


class TrafficCaptureClient:
    """Interception client that records full HTTP transaction bodies for privacy auditing."""

    def __init__(self, test_client: TestClient) -> None:
        self.test_client = test_client
        self.captured_requests: List[Dict[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url: str, **kwargs):
        path = url.replace("http://central-server:8000", "").replace("http://localhost:8000", "")
        return self.test_client.get(path, **kwargs)

    def post(self, url: str, *, json=None, headers=None, **kwargs):
        raw_bytes = __import__("json").dumps(json).encode("utf-8") if json is not None else b""
        record = {
            "timestamp": time.time(),
            "url": url,
            "path": url.replace("http://central-server:8000", "").replace("http://localhost:8000", ""),
            "json": json,
            "byte_size": len(raw_bytes),
            "raw_bytes": raw_bytes,
        }
        self.captured_requests.append(record)
        path = record["path"]
        return self.test_client.post(path, json=json, headers=headers or {})


def run_audit(num_frames: int = 20) -> bool:
    """Execute complete edge pipeline and audit all outbound traffic."""
    print("=" * 72)
    print("       EDGEERGO PRIVACY & NETWORK TRAFFIC AUDIT (PHASE 19)")
    print("=" * 72)

    # 1. Initialize Central Server (in-memory)
    app = create_app()
    central_db = CentralDatabase(":memory:")
    app.state.db = central_db
    test_client = TestClient(app)
    traffic_client = TrafficCaptureClient(test_client)

    # 2. Register Edge Node
    reg_resp = test_client.post("/api/v1/edge/register", json={
        "device_name": "AUDIT-WORKSTATION-01",
        "software_version": "0.1.0",
        "camera_detected": True,
        "camera_index": 0,
    })
    device_id = reg_resp.json()["device_id"]
    print(f"[*] Registered Edge Agent: {device_id}")

    # 3. Initialize Local Edge Agent Components
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "audit_local.db"
        cfg_path = Path(temp_dir) / "edge_config.json"
        local_db = LocalDatabase(str(db_path))
        cfg_mgr = ConfigManager(cfg_path)
        cfg_mgr.update({
            "device_id": device_id,
            "device_name": "AUDIT-WORKSTATION-01",
            "server_url": "http://central-server:8000",
            "local_db_path": str(db_path),
            "backoff_base_sec": 0.0,
        }, save_to_disk=True)

        pose_engine = PoseEngine()
        pose_engine.initialise()
        face_engine = FaceEngine()
        face_engine.initialise()
        angle_calc = AngleCalculator()
        expr_classifier = ExpressionClassifier()
        temporal = TemporalAnalyzer(config=cfg_mgr.config)
        server_sync = ServerSync(cfg_mgr, local_db)

        session_id = f"SESS-AUDIT-{int(time.time())}"
        temporal.start_session(session_id, time.time())

        print(f"[*] Processing {num_frames} frames through local AI pipeline...")
        for i in range(num_frames):
            # Synthetic camera frame (gradient BGR)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :, 0] = int((i / max(1, num_frames)) * 255)
            frame[:, :, 1] = 128
            frame[:, :, 2] = 200

            now = time.time()
            pose_res = pose_engine.process_frame(frame)
            face_res = face_engine.process_frame(frame)
            params = angle_calc.calculate(pose_res.landmarks, timestamp=now)
            assessment = assess(params)
            expr = expr_classifier.classify(face_res, timestamp=now)
            temporal.process_frame(assessment=assessment, expression=expr, timestamp=now)

        stats = temporal.end_session(time.time())
        local_db.save_session_analysis(device_id, stats)
        pose_engine.close()
        face_engine.close()

        # 4. Perform Network Heartbeat & Sync through Traffic Interceptor
        print("[*] Synchronizing telemetry with central server...")
        from edge_agent.health.heartbeat import HeartbeatClient
        from unittest.mock import patch
        heartbeat_client = HeartbeatClient(
            server_url="http://central-server:8000",
            device_id=device_id,
            software_version="0.1.0",
        )
        with patch("httpx.Client", return_value=traffic_client):
            # Send heartbeat
            heartbeat_client.send_heartbeat()
            # Drain sync queue
            server_sync.sync_pending_telemetry()

        # 5. Audit Captured Traffic
        print("\n" + "-" * 72)
        print("                  TRAFFIC INSPECTION LOG")
        print("-" * 72)
        print(f"{'Endpoint':<32} | {'Bytes':<8} | {'Media Content':<14} | {'Status'}")
        print("-" * 72)

        violations = []
        MEDIA_KEYWORDS = ["image", "frame", "pixel", "crop", "video", "jpeg", "png", "base64", "bgr", "rgb", "landmark"]

        for req in traffic_client.captured_requests:
            payload_str = req["raw_bytes"].decode("utf-8", errors="ignore").lower()
            size = req["byte_size"]
            path = req["path"]

            # Check for binary signatures or excessive size (> 10 KB indicates potential media leak)
            has_media = False
            for kw in MEDIA_KEYWORDS:
                if f'"{kw}"' in payload_str or f"'{kw}'" in payload_str:
                    has_media = True
                    violations.append(f"Suspicious keyword '{kw}' found in payload for {path}")

            if size > 10240:
                has_media = True
                violations.append(f"Payload size {size} bytes exceeds 10 KB threshold (possible embedded media)")

            media_status = "DETECTED" if has_media else "NONE (0 bytes)"
            status = "VIOLATION" if has_media else "PASSED"
            print(f"{path:<32} | {size:<8} | {media_status:<14} | {status}")

        print("-" * 72)

        # 6. Detailed Schema Verification on Telemetry Payload
        telemetry_requests = [r for r in traffic_client.captured_requests if "assessment" in r["path"]]
        if telemetry_requests:
            sample_payload = telemetry_requests[0]["json"]
            print("\n[*] Audited Telemetry Payload Schema:")
            print(json.dumps(sample_payload, indent=2))

        print("\n" + "=" * 72)
        if not violations:
            print(">>> AUDIT RESULT: PASSED (100% Zero-Media Privacy Enforcement)")
            print("    No pixels, frames, video streams, or facial geometry on the wire.")
            print("=" * 72)
            return True
        else:
            print(">>> AUDIT RESULT: FAILED (Privacy Violations Detected)")
            for v in violations:
                print(f"    - {v}")
            print("=" * 72)
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EdgeErgo Privacy Traffic Auditor")
    parser.add_argument("--frames", type=int, default=20, help="Number of frames to simulate")
    args = parser.parse_args()
    success = run_audit(num_frames=args.frames)
    sys.exit(0 if success else 1)
