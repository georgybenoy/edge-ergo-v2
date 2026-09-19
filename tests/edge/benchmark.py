"""
EdgeErgo — Automated Hardware Benchmarking Suite (PRD §109 Phase 18).

Measures and profiles Edge Agent performance across diverse hardware configurations:
  1. Pose Inference FPS & Latency (MediaPipe Pose Landmarker Lite)
  2. Face Inference FPS & Latency (MediaPipe Face Landmarker)
  3. Joint Geometry, Ergonomic Assessment (RULA/REBA), and Facial Expression Classification
  4. End-to-End Processing Latency (Frame Capture -> Scoring -> Persistence)
  5. Sustained Pipeline FPS under throttled & unthrottled conditions
  6. CPU Utilization (Process % and System %) via psutil
  7. Memory Utilization (Resident Set Size RSS, VMS, Memory Drift) via psutil
  8. Extended Multi-Cycle Stability & Memory Leak Verification

Hardware Profiles Evaluated:
  - Profile 1: High-Performance Multi-Core Workstation (Unconstrained 12/16 Threads, 16 GB RAM, 720p/1080p)
  - Profile 2: Enterprise Office Laptop (Constrained Dual-Core / 4-Thread Affinity, 16 GB RAM, 480p @ 15 FPS)
  - Profile 3: Entry-Level / Legacy Thin Client (Constrained Single-Core Affinity, 480p @ 10 FPS)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import psutil

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Core edge agent components
from edge_agent.camera.camera import Camera, list_available_cameras
from edge_agent.config.config_manager import ConfigManager, EdgeConfig
from edge_agent.ergonomics.scoring import assess
from edge_agent.expression.classifier import ExpressionClassifier
from edge_agent.feedback.alert_engine import AlertEngine
from edge_agent.geometry.angle_calculator import AngleCalculator
from edge_agent.storage.local_db import LocalDatabase
from edge_agent.temporal.analyzer import TemporalAnalyzer
from edge_agent.vision.face_engine import FaceEngine
from edge_agent.vision.pose_engine import PoseEngine

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclasses.dataclass
class HardwareSpecs:
    platform: str
    os_version: str
    architecture: str
    processor: str
    physical_cores: int
    logical_cores: int
    cpu_freq_mhz: float
    total_ram_gb: float
    available_ram_gb: float
    detected_cameras: List[int]
    python_version: str


@dataclasses.dataclass
class LatencyStats:
    count: int
    mean_ms: float
    min_ms: float
    max_ms: float
    median_ms: float
    p95_ms: float
    fps: float


@dataclasses.dataclass
class ProfileResult:
    profile_name: str
    cpu_affinity: Optional[List[int]]
    resolution: Tuple[int, int]
    target_fps: float
    pose_stats: LatencyStats
    face_stats: LatencyStats
    geometry_stats: LatencyStats
    expression_stats: LatencyStats
    end_to_end_stats: LatencyStats
    sustained_fps: float
    cpu_mean_pct: float
    cpu_peak_pct: float
    memory_start_rss_mb: float
    memory_peak_rss_mb: float
    memory_end_rss_mb: float
    memory_delta_mb: float
    total_frames_processed: int
    total_duration_sec: float


@dataclasses.dataclass
class StabilityResult:
    total_frames: int
    total_duration_sec: float
    start_rss_mb: float
    end_rss_mb: float
    peak_rss_mb: float
    rss_drift_mb_per_hour: float
    mean_latency_ms: float
    p95_latency_ms: float
    dropped_frames: int
    passed_leak_check: bool


# ── Hardware Detection ───────────────────────────────────────────────────────

def detect_hardware_specs() -> HardwareSpecs:
    """Inspect and return current host hardware and system specifications."""
    vm = psutil.virtual_memory()
    freq = psutil.cpu_freq()
    freq_mhz = freq.current if freq else 0.0

    cams: List[int] = []
    try:
        cams = list_available_cameras(max_index=2)
    except Exception:
        cams = [0]

    return HardwareSpecs(
        platform=platform.platform(),
        os_version=platform.version(),
        architecture=platform.machine(),
        processor=platform.processor(),
        physical_cores=psutil.cpu_count(logical=False) or 1,
        logical_cores=psutil.cpu_count(logical=True) or 1,
        cpu_freq_mhz=round(freq_mhz, 1),
        total_ram_gb=round(vm.total / (1024 ** 3), 2),
        available_ram_gb=round(vm.available / (1024 ** 3), 2),
        detected_cameras=cams,
        python_version=platform.python_version(),
    )


# ── Statistical Aggregation ──────────────────────────────────────────────────

def compute_latency_stats(latencies_ms: List[float]) -> LatencyStats:
    """Compute standard statistical summaries over a sequence of latency samples."""
    if not latencies_ms:
        return LatencyStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    arr = np.array(latencies_ms, dtype=np.float64)
    mean = float(np.mean(arr))
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    median = float(np.median(arr))
    p95 = float(np.percentile(arr, 95))
    fps = 1000.0 / mean if mean > 0 else 0.0

    return LatencyStats(
        count=len(latencies_ms),
        mean_ms=round(mean, 2),
        min_ms=round(min_val, 2),
        max_ms=round(max_val, 2),
        median_ms=round(median, 2),
        p95_ms=round(p95, 2),
        fps=round(fps, 2),
    )


# ── Benchmark Runner ─────────────────────────────────────────────────────────

class HardwareBenchmarkSuite:
    """Executes controlled performance and stability benchmarks."""

    def __init__(self, specs: HardwareSpecs) -> None:
        self.specs = specs
        self.process = psutil.Process(os.getpid())
        self._orig_affinity = self.process.cpu_affinity()

    def set_affinity(self, affinity: Optional[List[int]]) -> None:
        """Constrain CPU affinity to simulate specific hardware architectures."""
        if affinity is None:
            self.process.cpu_affinity(self._orig_affinity)
        else:
            valid_cores = [c for c in affinity if c < self.specs.logical_cores]
            if valid_cores:
                self.process.cpu_affinity(valid_cores)

    def restore_affinity(self) -> None:
        """Restore original host affinity."""
        self.process.cpu_affinity(self._orig_affinity)

    def run_profile(
        self,
        name: str,
        affinity: Optional[List[int]],
        resolution: Tuple[int, int] = (640, 480),
        target_fps: float = 15.0,
        warmup_frames: int = 20,
        benchmark_frames: int = 150,
        use_camera: bool = False,
    ) -> ProfileResult:
        """Run standard isolated and end-to-end benchmark for a hardware profile."""
        self.set_affinity(affinity)
        w, h = resolution

        # Initialize engines
        pose_engine = PoseEngine()
        pose_engine.initialise()

        face_engine = FaceEngine()
        face_engine.initialise()

        angle_calc = AngleCalculator()
        expr_classifier = ExpressionClassifier()
        alert_engine = AlertEngine()

        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "benchmark_test.db"
        db = LocalDatabase(str(db_path))
        cfg = EdgeConfig()
        temporal_analyzer = TemporalAnalyzer(config=cfg)
        temporal_analyzer.start_session(f"SESS-BENCH-{int(time.time())}-0", time.time())

        # Physical camera or synthetic frame source
        cam: Optional[Camera] = None
        if use_camera:
            try:
                cam = Camera(camera_index=0, frame_width=w, frame_height=h)
                cam.open()
            except Exception:
                cam = None

        # Prepare synthetic test pattern if camera unavailable
        synthetic_frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Add gradient to prevent OpenCV/MediaPipe all-black zero-branch skip
        for y in range(h):
            synthetic_frame[y, :, 0] = int((y / h) * 200)
            synthetic_frame[y, :, 1] = int(((h - y) / h) * 180)
            synthetic_frame[y, :, 2] = 120

        def get_frame() -> np.ndarray:
            if cam is not None and cam.is_open:
                cf = cam.read_frame()
                if cf is not None:
                    return cf.to_rgb()
            return synthetic_frame.copy()

        # ── 1. Warm-up ────────────────────────────────────────────────────────
        for _ in range(warmup_frames):
            frame = get_frame()
            _ = pose_engine.process_frame(frame)
            _ = face_engine.process_frame(frame)

        # ── 2. Isolated Pose Inference ────────────────────────────────────────
        pose_latencies: List[float] = []
        for _ in range(benchmark_frames):
            frame = get_frame()
            t0 = time.perf_counter()
            _ = pose_engine.process_frame(frame)
            t1 = time.perf_counter()
            pose_latencies.append((t1 - t0) * 1000.0)

        # ── 3. Isolated Face Inference ────────────────────────────────────────
        face_latencies: List[float] = []
        for _ in range(benchmark_frames):
            frame = get_frame()
            t0 = time.perf_counter()
            _ = face_engine.process_frame(frame)
            t1 = time.perf_counter()
            face_latencies.append((t1 - t0) * 1000.0)

        # ── 4. End-to-End Pipeline Latency & Resource Utilization ─────────────
        e2e_latencies: List[float] = []
        geometry_latencies: List[float] = []
        expression_latencies: List[float] = []
        cpu_samples: List[float] = []

        # Reset CPU meter
        self.process.cpu_percent(interval=None)
        start_mem = self.process.memory_info()
        peak_rss = start_mem.rss

        start_time = time.time()
        for i in range(benchmark_frames):
            t_frame_start = time.perf_counter()
            frame = get_frame()
            cur_time = time.time()

            # Vision
            pose_res = pose_engine.process_frame(frame)
            face_res = face_engine.process_frame(frame)

            # Geometry & Ergonomics
            t_geo0 = time.perf_counter()
            posture_params = angle_calc.calculate(pose_res.landmarks, timestamp=cur_time)
            assessment = assess(posture_params)
            t_geo1 = time.perf_counter()
            geometry_latencies.append((t_geo1 - t_geo0) * 1000.0)

            # Expression
            t_exp0 = time.perf_counter()
            expr_res = expr_classifier.classify(face_res, timestamp=cur_time)
            t_exp1 = time.perf_counter()
            expression_latencies.append((t_exp1 - t_exp0) * 1000.0)

            # Temporal persistence
            _ = temporal_analyzer.process_frame(
                assessment=assessment,
                expression=expr_res,
                timestamp=cur_time,
            )

            # Simulate batch storage flush every 50 frames
            if (i + 1) % 50 == 0:
                stats = temporal_analyzer.end_session(cur_time)
                if stats is not None:
                    db.save_session_analysis("NODE-BENCH", stats, expression_category="Neutral")
                temporal_analyzer.start_session(f"SESS-BENCH-{int(cur_time*1000)}-{i}", cur_time)

            t_frame_end = time.perf_counter()
            e2e_latencies.append((t_frame_end - t_frame_start) * 1000.0)

            # Resource sampling
            current_mem = self.process.memory_info().rss
            if current_mem > peak_rss:
                peak_rss = current_mem

            if (i + 1) % 15 == 0:
                cpu_samples.append(self.process.cpu_percent(interval=None))

        total_duration = time.time() - start_time
        sustained_fps = benchmark_frames / total_duration if total_duration > 0 else 0.0

        end_mem = self.process.memory_info()
        mean_cpu = float(np.mean(cpu_samples)) if cpu_samples else self.process.cpu_percent(interval=None)
        peak_cpu = float(np.max(cpu_samples)) if cpu_samples else mean_cpu

        # Cleanup
        if cam is not None:
            cam.release()
        pose_engine.close()
        face_engine.close()
        db.close()
        temp_dir.cleanup()
        self.restore_affinity()

        return ProfileResult(
            profile_name=name,
            cpu_affinity=affinity,
            resolution=resolution,
            target_fps=target_fps,
            pose_stats=compute_latency_stats(pose_latencies),
            face_stats=compute_latency_stats(face_latencies),
            geometry_stats=compute_latency_stats(geometry_latencies),
            expression_stats=compute_latency_stats(expression_latencies),
            end_to_end_stats=compute_latency_stats(e2e_latencies),
            sustained_fps=round(sustained_fps, 2),
            cpu_mean_pct=round(mean_cpu, 1),
            cpu_peak_pct=round(peak_cpu, 1),
            memory_start_rss_mb=round(start_mem.rss / (1024 * 1024), 2),
            memory_peak_rss_mb=round(peak_rss / (1024 * 1024), 2),
            memory_end_rss_mb=round(end_mem.rss / (1024 * 1024), 2),
            memory_delta_mb=round((end_mem.rss - start_mem.rss) / (1024 * 1024), 2),
            total_frames_processed=benchmark_frames,
            total_duration_sec=round(total_duration, 2),
        )

    def run_stability_test(
        self,
        frames: int = 600,
        resolution: Tuple[int, int] = (640, 480),
        target_fps: float = 15.0,
    ) -> StabilityResult:
        """Extended continuous execution test verifying memory stability and leak-freedom."""
        w, h = resolution
        pose_engine = PoseEngine()
        pose_engine.initialise()
        face_engine = FaceEngine()
        face_engine.initialise()
        angle_calc = AngleCalculator()
        expr_classifier = ExpressionClassifier()

        temp_dir = tempfile.TemporaryDirectory()
        db = LocalDatabase(str(Path(temp_dir.name) / "stability.db"))
        cfg = EdgeConfig()
        analyzer = TemporalAnalyzer(config=cfg)
        analyzer.start_session(f"SESS-STABILITY-{int(time.time()*1000)}-0", time.time())

        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[100:380, 200:440] = 180  # Simple synthetic torso block

        # Warm-up to reach steady-state runtime and memory allocations
        for _ in range(30):
            p_res = pose_engine.process_frame(frame)
            f_res = face_engine.process_frame(frame)
            posture = angle_calc.calculate(p_res.landmarks, timestamp=time.time())
            _ = assess(posture)
            _ = expr_classifier.classify(f_res, timestamp=time.time())

        start_time = time.time()
        start_rss = self.process.memory_info().rss
        peak_rss = start_rss
        latencies: List[float] = []

        frame_interval = 1.0 / target_fps
        dropped_frames = 0

        for i in range(frames):
            t0 = time.perf_counter()
            cur_time = time.time()

            p_res = pose_engine.process_frame(frame)
            f_res = face_engine.process_frame(frame)
            posture = angle_calc.calculate(p_res.landmarks, timestamp=cur_time)
            asmt = assess(posture)
            exp = expr_classifier.classify(f_res, timestamp=cur_time)
            _ = analyzer.process_frame(assessment=asmt, expression=exp, timestamp=cur_time)

            if (i + 1) % 50 == 0:
                stats = analyzer.end_session(cur_time)
                if stats is not None:
                    db.save_session_analysis("NODE-STABILITY", stats)
                analyzer.start_session(f"SESS-STABILITY-{int(cur_time*1000)}-{i}", cur_time)

            t1 = time.perf_counter()
            elapsed_ms = (t1 - t0) * 1000.0
            latencies.append(elapsed_ms)

            # Check memory
            rss = self.process.memory_info().rss
            if rss > peak_rss:
                peak_rss = rss

            # Frame rate regulation
            cycle_time = t1 - t0
            if cycle_time > frame_interval:
                dropped_frames += 1
            else:
                time.sleep(frame_interval - cycle_time)

        total_duration = time.time() - start_time
        end_rss = self.process.memory_info().rss

        pose_engine.close()
        face_engine.close()
        db.close()
        temp_dir.cleanup()

        hours = total_duration / 3600.0
        delta_rss_mb = (end_rss - start_rss) / (1024 * 1024)
        drift_rate = delta_rss_mb / hours if hours > 0 else 0.0

        p95_lat = float(np.percentile(latencies, 95))
        mean_lat = float(np.mean(latencies))

        # Pass criteria: steady state growth < 5.0 MB, mean latency within 100ms
        passed = (delta_rss_mb < 5.0) and (mean_lat < 100.0)

        return StabilityResult(
            total_frames=frames,
            total_duration_sec=round(total_duration, 2),
            start_rss_mb=round(start_rss / (1024 * 1024), 2),
            end_rss_mb=round(end_rss / (1024 * 1024), 2),
            peak_rss_mb=round(peak_rss / (1024 * 1024), 2),
            rss_drift_mb_per_hour=round(drift_rate, 2),
            mean_latency_ms=round(mean_lat, 2),
            p95_latency_ms=round(p95_lat, 2),
            dropped_frames=dropped_frames,
            passed_leak_check=passed,
        )


# ── Formatting & Reporting ───────────────────────────────────────────────────

def format_markdown_table(results: List[ProfileResult]) -> str:
    """Generate GitHub-flavored markdown comparison table."""
    lines = [
        "| Hardware Profile | CPU Config | Camera Res | Pose FPS (Lat) | Face FPS (Lat) | E2E Latency (Mean/p95) | Sustained FPS | Process CPU % | Memory (RSS) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in results:
        cpu_cfg = "All Cores" if r.cpu_affinity is None else f"{len(r.cpu_affinity)} Core(s)"
        res_str = f"{r.resolution[0]}x{r.resolution[1]}"
        pose_str = f"{r.pose_stats.fps} ({r.pose_stats.mean_ms}ms)"
        face_str = f"{r.face_stats.fps} ({r.face_stats.mean_ms}ms)"
        e2e_str = f"{r.end_to_end_stats.mean_ms}ms / {r.end_to_end_stats.p95_ms}ms"
        mem_str = f"{r.memory_end_rss_mb} MB"
        lines.append(
            f"| **{r.profile_name}** | {cpu_cfg} | {res_str} | {pose_str} | {face_str} | {e2e_str} | **{r.sustained_fps}** | {r.cpu_mean_pct}% | {mem_str} |"
        )
    return "\n".join(lines)


def print_cli_summary(results: List[ProfileResult], specs: HardwareSpecs) -> None:
    """Print clean terminal summary."""
    print("=" * 88)
    print(f"  EdgeErgo Automated Hardware Benchmark Results (Phase 18)")
    print(f"  Host: {specs.processor} ({specs.physical_cores}C/{specs.logical_cores}T, {specs.total_ram_gb} GB RAM)")
    print(f"  OS:   {specs.platform}")
    print("=" * 88)
    print(f"{'Profile':<24} | {'Pose FPS':<10} | {'Face FPS':<10} | {'E2E Latency':<16} | {'Sustained':<10} | {'CPU %':<8} | {'RSS MB':<8}")
    print("-" * 88)
    for r in results:
        print(
            f"{r.profile_name:<24} | "
            f"{r.pose_stats.fps:<10.1f} | "
            f"{r.face_stats.fps:<10.1f} | "
            f"{r.end_to_end_stats.mean_ms:<7.1f} (p95:{r.end_to_end_stats.p95_ms:<4.1f}) | "
            f"{r.sustained_fps:<10.1f} | "
            f"{r.cpu_mean_pct:<8.1f} | "
            f"{r.memory_end_rss_mb:<8.1f}"
        )
    print("=" * 88)


# ── Pytest Validation Tests ──────────────────────────────────────────────────

def test_hardware_specs_detection() -> None:
    """Verify hardware detection accurately introspects the host machine."""
    specs = detect_hardware_specs()
    assert specs.logical_cores >= 1
    assert specs.total_ram_gb > 0.5
    assert specs.processor != ""
    assert specs.python_version != ""


def test_benchmark_quick_run() -> None:
    """Quick validation of isolated & end-to-end benchmark pipeline."""
    specs = detect_hardware_specs()
    suite = HardwareBenchmarkSuite(specs)
    result = suite.run_profile(
        name="Quick CI Test",
        affinity=None,
        resolution=(640, 480),
        target_fps=15.0,
        warmup_frames=3,
        benchmark_frames=10,
    )
    assert result.pose_stats.count == 10
    assert result.face_stats.count == 10
    assert result.pose_stats.mean_ms > 0.0
    assert result.face_stats.mean_ms > 0.0
    assert result.end_to_end_stats.mean_ms < 500.0
    assert result.sustained_fps > 0.0
    assert result.memory_end_rss_mb > 0.0


# ── CLI & Entry Point ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EdgeErgo Hardware Benchmarking Tool (PRD §109 Phase 18)")
    parser.add_argument("--profile", choices=["all", "workstation", "laptop", "thin_client"], default="all", help="Profile to execute")
    parser.add_argument("--frames", type=int, default=150, help="Benchmark iterations per profile (default: 150)")
    parser.add_argument("--use-camera", action="store_true", help="Use physical webcam rather than synthetic frame generator")
    parser.add_argument("--stability", action="store_true", help="Run extended stability & memory leak verification")
    parser.add_argument("--stability-frames", type=int, default=600, help="Frames for stability verification (default: 600)")
    parser.add_argument("--output-json", type=str, help="Export benchmark data to JSON file")
    args = parser.parse_args()

    specs = detect_hardware_specs()
    suite = HardwareBenchmarkSuite(specs)

    profiles_to_run = []
    if args.profile in ("all", "workstation", "1080p"):
        profiles_to_run.append(("High-End Workstation (1080p)", None, (1920, 1080), 30.0))
    if args.profile in ("all", "workstation", "720p"):
        profiles_to_run.append(("Modern Desktop (720p)", None, (1280, 720), 30.0))
    if args.profile in ("all", "laptop", "480p"):
        profiles_to_run.append(("Standard Office Laptop (480p)", [0, 1, 2, 3], (640, 480), 15.0))
    if args.profile in ("all", "thin_client"):
        profiles_to_run.append(("Entry-Level Thin Client (Single Core)", [0], (640, 480), 10.0))

    results: List[ProfileResult] = []
    print(f"[INFO] Running EdgeErgo benchmark on: {specs.processor} ({specs.logical_cores} threads)")
    for name, affinity, res, target_fps in profiles_to_run:
        print(f"[RUNNING] Benchmarking profile: {name} (Res: {res[0]}x{res[1]}, Affinity: {affinity})...")
        res_data = suite.run_profile(
            name=name,
            affinity=affinity,
            resolution=res,
            target_fps=target_fps,
            benchmark_frames=args.frames,
            use_camera=args.use_camera,
        )
        results.append(res_data)

    print_cli_summary(results, specs)

    stability_data = None
    if args.stability:
        print(f"\n[RUNNING] Executing continuous stability test ({args.stability_frames} frames)...")
        stability_data = suite.run_stability_test(frames=args.stability_frames)
        print(f"[STABILITY] Total Duration: {stability_data.total_duration_sec}s | Start RSS: {stability_data.start_rss_mb} MB | End RSS: {stability_data.end_rss_mb} MB")
        print(f"[STABILITY] Drift Rate: {stability_data.rss_drift_mb_per_hour} MB/hr | p95 Latency: {stability_data.p95_latency_ms} ms | Leak-Free: {stability_data.passed_leak_check}")

    if args.output_json:
        payload: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "hardware_specs": dataclasses.asdict(specs),
            "profiles": [dataclasses.asdict(r) for r in results],
        }
        if stability_data:
            payload["stability"] = dataclasses.asdict(stability_data)

        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"[SAVED] Exported benchmark results to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
