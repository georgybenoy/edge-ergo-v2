"""
Analytics & Database Query Scalability Performance Benchmark (Phase 20, PRD §111).

Validates database index utilization and query latency against a realistic enterprise dataset:
  - 10 registered Edge Nodes
  - 4 weeks of continuous multi-node telemetry (5,000+ telemetry windows)
  - Collective aggregate queries, workstation summaries, and time-based trends
"""

from __future__ import annotations

import datetime
from datetime import timezone
import random
import time
from typing import List

import pytest

from central_server.aggregation.aggregator import TelemetryAggregator
from central_server.analytics.analytics import AnalyticsEngine
from central_server.database.database import CentralDatabase


@pytest.fixture(scope="module")
def populated_benchmark_db():
    """Create a database populated with 5,000 telemetry windows across 10 devices."""
    db = CentralDatabase(":memory:")

    num_devices = 10
    total_windows = 5000

    # 1. Register devices
    device_ids = []
    for i in range(1, num_devices + 1):
        dev_id = f"NODE-{i:03d}"
        device_ids.append(dev_id)
        db.register_device(
            assigned_id=dev_id,
            device_name=f"Workstation-{i:02d}",
            software_version="0.1.0",
        )

    # 2. Populate telemetry windows over 28 days
    base_time = datetime.datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
    postures = ["NEUTRAL", "NECK_FLEXION", "TRUNK_FLEXION", "SHOULDER_ELEVATION", "REACHING"]

    with db.get_connection() as conn:
        for idx in range(total_windows):
            dev_id = device_ids[idx % num_devices]
            window_start = base_time + datetime.timedelta(minutes=idx * 8)
            window_end = window_start + datetime.timedelta(minutes=5)
            w_start_iso = window_start.isoformat()
            w_end_iso = window_end.isoformat()
            window_id = f"WIN-{idx:05d}"
            sess_id = f"SESS-{idx // 10:04d}"

            # Ensure parent session exists
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, device_id, start_time, end_time, duration, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sess_id, dev_id, w_start_iso, w_end_iso, 300.0, w_start_iso),
            )

            # Insert window
            conn.execute(
                """
                INSERT INTO telemetry_windows (window_id, device_id, session_id, window_start, window_end, created_at, breaks_recommended, breaks_acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (window_id, dev_id, sess_id, w_start_iso, w_end_iso, w_start_iso, random.choice([0, 1]), random.choice([0, 1])),
            )

            # Insert posture metrics
            rula = random.uniform(1.5, 6.5)
            reba = random.uniform(1.8, 7.2)
            conn.execute(
                """
                INSERT INTO posture_metrics (metric_id, window_id, average_rula, maximum_rula, average_reba, maximum_reba, high_risk_percentage, dominant_posture)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"PM-{idx}", window_id, rula, int(rula + 1), reba, int(reba + 1), 15.0 if rula >= 4.0 else 0.0, random.choice(postures)),
            )

            # Insert expression metrics
            conn.execute(
                """
                INSERT INTO expression_metrics (metric_id, window_id, neutral_percentage, positive_percentage, negative_percentage, reduced_expression_percentage)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"EM-{idx}", window_id, 75.0, 15.0, 5.0, 5.0),
            )

    yield db
    db.close()


def test_collective_aggregation_query_performance(populated_benchmark_db):
    """TelemetryAggregator.aggregate() across 5,000 windows should execute well under 100 ms."""
    aggregator = TelemetryAggregator(populated_benchmark_db)

    t0 = time.perf_counter()
    metrics = aggregator.aggregate()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert metrics.total_windows == 5000
    assert metrics.total_nodes == 10
    print(f"\n[BENCHMARK] Collective Aggregation (5,000 rows): {elapsed_ms:.2f} ms")
    assert elapsed_ms < 150.0, f"Query took {elapsed_ms:.2f} ms (expected < 150 ms)"


def test_workstation_summaries_query_performance(populated_benchmark_db):
    """AnalyticsEngine.get_workstation_summaries() with batch optimization should execute well under 100 ms."""
    analytics = AnalyticsEngine(populated_benchmark_db)

    t0 = time.perf_counter()
    summaries = analytics.get_workstation_summaries()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(summaries) == 10
    total_w = sum(s["total_windows"] for s in summaries)
    assert total_w == 5000
    print(f"\n[BENCHMARK] Workstation Summaries (10 nodes, 5,000 rows): {elapsed_ms:.2f} ms")
    assert elapsed_ms < 150.0, f"Query took {elapsed_ms:.2f} ms (expected < 150 ms)"


def test_time_based_trends_query_performance(populated_benchmark_db):
    """AnalyticsEngine.get_time_based_trends() across 28 days should execute well under 100 ms."""
    analytics = AnalyticsEngine(populated_benchmark_db)

    t0 = time.perf_counter()
    trends = analytics.get_time_based_trends(interval="hourly")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(trends) > 0
    print(f"\n[BENCHMARK] Time-based Trends (Hourly, 5,000 rows): {elapsed_ms:.2f} ms")
    assert elapsed_ms < 150.0, f"Query took {elapsed_ms:.2f} ms (expected < 150 ms)"


def test_combined_patterns_query_performance(populated_benchmark_db):
    """AnalyticsEngine.get_combined_correlations() should execute well under 100 ms."""
    analytics = AnalyticsEngine(populated_benchmark_db)

    t0 = time.perf_counter()
    patterns = analytics.get_combined_correlations()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert "total_analyzed_windows" in patterns
    assert patterns["total_analyzed_windows"] == 5000
    print(f"\n[BENCHMARK] Combined Correlations (5,000 rows): {elapsed_ms:.2f} ms")
    assert elapsed_ms < 150.0, f"Query took {elapsed_ms:.2f} ms (expected < 150 ms)"
