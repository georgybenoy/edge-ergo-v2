"""
EdgeErgo — Edge Agent Main Entry Point (PRD §11, §15, §30, §42, §43, §107).

Orchestrates:
  1. CLI argument parsing & first-time Central Server registration.
  2. Background daemon threads for heartbeat reporting and telemetry queue synchronization.
  3. Real-time in-memory computer vision pipeline (MediaPipe Pose + Face, Angle Calculator, RULA/REBA).
  4. Temporal posture persistence tracking and non-medical alert generation.
  5. PySide6 non-blocking desktop worker awareness overlay.

Privacy invariant:
  Raw camera frames, video feeds, and facial landmark crops NEVER leave local memory.
  Only aggregated mathematical telemetry summaries are persisted or synchronized.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Optional

import numpy as np

# Core edge agent modules
from edge_agent.camera.camera import Camera, CameraError, Frame, list_available_cameras
from edge_agent.config.config_manager import ConfigManager
from edge_agent.ergonomics.scoring import assess
from edge_agent.expression.classifier import ExpressionClassifier
from edge_agent.feedback.alert_engine import AlertEngine, AlertPriority
from edge_agent.feedback.recommendations import get_posture_recommendation
from edge_agent.feedback.scheduler import MonitoringScheduler
from edge_agent.geometry.angle_calculator import AngleCalculator
from edge_agent.health.heartbeat import HeartbeatClient
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.sync.server_sync import ServerSync, SyncWorker
from edge_agent.temporal.analyzer import TemporalAnalyzer
from edge_agent.vision.face_engine import FaceEngine
from edge_agent.vision.pose_engine import PoseEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("edge_agent")


class EdgeAgentController:
    """Coordinates camera capture, vision inference, ergonomics, alerts, and sync."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        server_url: Optional[str] = None,
        device_name: Optional[str] = None,
        no_camera: bool = False,
        headless: bool = False,
        target_fps: float = 15.0,
    ) -> None:
        self.no_camera = no_camera
        self.headless = headless
        self.target_fps = target_fps
        self._running = False
        self._analysis_thread: Optional[threading.Thread] = None

        # 1. Configuration manager
        c_path = Path(config_path) if config_path else Path("edge_config.json")
        self.config_manager = ConfigManager(c_path)
        overrides = {}
        if server_url:
            overrides["server_url"] = server_url
        if device_name:
            overrides["device_name"] = device_name
        if overrides:
            self.config_manager.update(overrides, save_to_disk=True)

        # 2. Local database
        self.db = LocalDatabase(str(self.config_manager.config.local_db_path))

        # 3. Vision & Analytics Engines
        self.pose_engine = PoseEngine()
        self.face_engine = FaceEngine()
        self.angle_calc = AngleCalculator()
        self.expr_classifier = ExpressionClassifier()
        self.temporal_analyzer = TemporalAnalyzer(config=self.config_manager.config)
        self.alert_engine = AlertEngine()
        self.scheduler = MonitoringScheduler(config=self.config_manager.config)

        # 4. Sync & Network Services (heartbeat and worker initialized in setup_and_register)
        self.server_sync = ServerSync(self.config_manager, self.db)
        self.sync_worker: Optional[SyncWorker] = None
        self.heartbeat_client: Optional[HeartbeatClient] = None

        # 5. UI Overlay reference
        self.overlay_widget = None

    def setup_and_register(self) -> str:
        """Verify camera and register with Central Server if not already registered."""
        # Check camera
        cams = list_available_cameras(max_index=2)
        has_cam = len(cams) > 0 or self.no_camera
        logger.info("Detected local camera devices: %s", cams)

        # Check existing registration
        device_id = self.config_manager.config.device_id
        if device_id:
            logger.info("Node already registered as: %s", device_id)
        else:
            # First-time registration
            server = self.config_manager.config.server_url
            d_name = self.config_manager.config.device_name or "Workstation"
            logger.info("Performing first-time node registration with Central Server: %s", server)
            success, dev_id_or_err = self.server_sync.register_node(
                device_name=d_name,
                camera_index=cams[0] if cams else 0,
            )
            if success:
                device_id = dev_id_or_err
                logger.info("Registration successful! Assigned Node ID: %s", device_id)
            else:
                device_id = "NODE-LOCAL"
                self.config_manager.update({"device_id": device_id}, save_to_disk=True)
                self.db.register_device(
                    device_id=device_id,
                    device_name=d_name,
                    software_version=self.config_manager.config.software_version,
                )
                logger.warning(
                    "Could not reach Central Server: %s. Continuing in offline mode with ID: %s",
                    dev_id_or_err,
                    device_id,
                )

        # Initialize network workers
        self.heartbeat_client = HeartbeatClient(
            server_url=self.config_manager.config.server_url,
            device_id=device_id,
            software_version=self.config_manager.config.software_version,
            interval_sec=float(self.config_manager.config.heartbeat_interval_sec),
        )
        self.sync_worker = SyncWorker(
            server_sync=self.server_sync,
            interval_sec=float(self.config_manager.config.sync_interval_sec),
        )
        return device_id

    def start_background_services(self) -> None:
        """Start heartbeat and telemetry sync background loops."""
        if self.heartbeat_client:
            self.heartbeat_client.start()
        if self.sync_worker:
            self.sync_worker.start()

    def stop_background_services(self) -> None:
        """Stop background network threads cleanly."""
        if self.heartbeat_client:
            self.heartbeat_client.stop()
        if self.sync_worker:
            self.sync_worker.stop()

    def run_pipeline_loop(self) -> None:
        """Continuous frame processing and ergonomic evaluation loop."""
        self._running = True
        logger.info("Starting EdgeErgo analysis pipeline. Camera active=%s", not self.no_camera)

        self.pose_engine.initialise()
        self.face_engine.initialise()

        cam = None
        if not self.no_camera:
            try:
                cam = Camera(camera_index=0, frame_width=640, frame_height=480)
                cam.open()
            except Exception as e:
                logger.warning("Failed to open physical camera: %s. Falling back to synthetic frames.", e)
                cam = None

        frame_interval = 1.0 / self.target_fps
        frame_idx = 0

        # Session tracking
        session_id = f"SESS-{int(time.time())}"
        device_id = self.config_manager.config.device_id or "NODE-001"
        session_start_time = time.time()
        self.temporal_analyzer.start_session(session_id, session_start_time)
        telemetry_interval_sec = min(10.0, float(self.config_manager.config.telemetry_window_sec))

        try:
            while self._running:
                loop_start = time.time()

                # 1. Fetch frame
                rgb = None
                if cam is not None and cam.is_open:
                    try:
                        cf = cam.read_frame()
                        if cf is not None:
                            rgb = cf.to_rgb()
                    except CameraError as e:
                        logger.warning("Camera frame read issue: %s. Using synthetic frame.", e)
                    except Exception as e:
                        logger.warning("Unexpected error during frame read: %s", e)

                if rgb is None:
                    # Synthetic 640x480 RGB frame for headless/test/fallback operation
                    rgb = np.zeros((480, 640, 3), dtype=np.uint8)

                if rgb is not None:

                    cur_time = time.time()

                    # 2. Vision Inference
                    pose_res = self.pose_engine.process_frame(rgb)
                    face_res = self.face_engine.process_frame(rgb)

                    # 3. Ergonomics & Posture
                    posture_params = self.angle_calc.calculate(pose_res.landmarks, timestamp=cur_time)
                    assessment = assess(posture_params)
                    rula = float(assessment.rula_score)
                    reba = float(assessment.reba_score)
                    risk_cat = assessment.risk_level.value

                    # 4. Facial Expression
                    expr_res = self.expr_classifier.classify(face_res, timestamp=cur_time)
                    expr_cat = expr_res.category.value if expr_res else "Neutral"

                    # 5. Temporal Posture Persistence & Alert Detection
                    alert_evt = self.temporal_analyzer.process_frame(
                        assessment=assessment,
                        expression=expr_res,
                        timestamp=cur_time,
                    )

                    # 6. Trigger Alerts
                    if alert_evt is not None:
                        rec = get_posture_recommendation(alert_evt.condition)
                        msg = rec.action_tip if rec is not None else alert_evt.message
                        self.alert_engine.enqueue(
                            message=msg,
                            priority=AlertPriority.WARNING if "HIGH" in alert_evt.risk_level else AlertPriority.ATTENTION,
                            duration_seconds=6.0,
                        )

                    # 7. Update UI Overlay Status
                    if self.overlay_widget is not None:
                        try:
                            last_str = time.strftime("%H:%M:%S", time.localtime(cur_time))
                            self.overlay_widget.update_status(
                                is_monitoring=True,
                                risk_level=risk_cat,
                                rula=rula,
                                reba=reba,
                                dominant_posture=getattr(assessment, "dominant_posture", "NEUTRAL"),
                                last_time_str=last_str,
                                sync_status="Synced ●" if not self.server_sync.is_busy() else "Syncing...",
                            )
                        except Exception as e:
                            logger.debug("Overlay update issue: %s", e)

                    frame_idx += 1

                    # Log periodically
                    if frame_idx % 75 == 0:
                        logger.info(
                            "Edge Node Monitoring: RULA=%.1f (%s), REBA=%.1f, Expression=%s, Frames=%d",
                            rula, risk_cat, reba, expr_cat, frame_idx,
                        )

                    # Window rollover for telemetry persistence
                    if (cur_time - session_start_time) >= telemetry_interval_sec:
                        stats = self.temporal_analyzer.end_session(cur_time)
                        if stats is not None and stats.total_frames > 0:
                            try:
                                sync_id = self.db.save_session_analysis(device_id, stats, expression_category=expr_cat)
                                logger.info("Persisted telemetry window %s (%d frames, sync_id=%s)", stats.session_id, stats.total_frames, sync_id)
                                self.server_sync.sync_pending_telemetry(limit=5)
                            except Exception as e:
                                logger.warning("Failed to persist telemetry window: %s", e)
                        session_id = f"SESS-{int(time.time())}"
                        session_start_time = time.time()
                        self.temporal_analyzer.start_session(session_id, session_start_time)

                # Regulate frame rate
                elapsed = time.time() - loop_start
                sleep_time = max(0.001, frame_interval - elapsed)
                time.sleep(sleep_time)

        finally:
            if cam is not None:
                cam.release()
            # Save any remaining analyzed frames on shutdown
            stats = self.temporal_analyzer.end_session(time.time())
            if stats is not None and stats.total_frames > 0:
                try:
                    sync_id = self.db.save_session_analysis(device_id, stats)
                    logger.info("Persisted final session %s to local DB (sync_id=%s)", stats.session_id, sync_id)
                    self.server_sync.sync_pending_telemetry(limit=5)
                except Exception as e:
                    logger.warning("Error saving final session: %s", e)
            self.pose_engine.close()
            self.face_engine.close()
            self.db.close()
            logger.info("EdgeErgo analysis pipeline stopped cleanly.")

    def start_pipeline(self) -> None:
        """Run analysis loop in a dedicated background thread."""
        self._analysis_thread = threading.Thread(target=self.run_pipeline_loop, daemon=True)
        self._analysis_thread.start()

    def stop(self) -> None:
        """Stop all pipelines and threads."""
        self._running = False
        self.stop_background_services()


def main() -> None:
    """EdgeErgo Agent CLI & Desktop Application Entry Point."""
    parser = argparse.ArgumentParser(
        description="EdgeErgo — Privacy-Preserving Edge AI Ergonomic & Expression Monitoring Agent"
    )
    parser.add_argument("--config", type=str, help="Path to local configuration JSON file")
    parser.add_argument("--server", "--server-url", type=str, help="Central Server address (e.g. http://localhost:8000)")
    parser.add_argument("--device-name", type=str, help="Custom workstation or desk label")
    parser.add_argument("--headless", action="store_true", help="Run without PySide6 desktop overlay")
    parser.add_argument("--no-camera", action="store_true", help="Run with synthetic test frames without physical camera")
    parser.add_argument("--fps", type=float, default=15.0, help="Target capture FPS (default: 15.0)")

    args = parser.parse_args()

    controller = EdgeAgentController(
        config_path=args.config,
        server_url=args.server,
        device_name=args.device_name,
        no_camera=args.no_camera,
        headless=args.headless,
        target_fps=args.fps,
    )

    # 1. First-time registration & node identification
    controller.setup_and_register()

    # 2. Start background heartbeat & sync threads
    controller.start_background_services()

    # 3. Start analysis pipeline
    controller.start_pipeline()

    # 4. UI Loop vs Headless Loop
    if args.headless:
        logger.info("Edge Agent running in HEADLESS daemon mode. Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Received termination signal. Shutting down Edge Agent...")
        finally:
            controller.stop()
    else:
        # Launch PySide6 Desktop Worker Overlay
        try:
            from PySide6.QtWidgets import QApplication
            from edge_agent.overlay.overlay import WorkerOverlayWidget

            app = QApplication.instance() or QApplication(sys.argv)
            overlay = WorkerOverlayWidget(alert_engine=controller.alert_engine)
            controller.overlay_widget = overlay

            # Position in top-right screen quadrant
            screen_geo = app.primaryScreen().availableGeometry()
            overlay.move(screen_geo.width() - 440, 40)
            overlay.show()

            logger.info("Worker Desktop Awareness Overlay launched. Running Qt event loop.")
            app.exec()
        except Exception as e:
            logger.warning("Could not launch graphical overlay: %s. Continuing in console mode.", e)
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                pass
        finally:
            controller.stop()


if __name__ == "__main__":
    main()
