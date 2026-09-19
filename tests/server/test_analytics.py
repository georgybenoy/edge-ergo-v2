"""
Unit and integration tests for Phase 13: Collective Analytics Engine (PRD §50, §51, §54, §55).

Verifies:
  1. Hand-calculated mathematical aggregates across a seeded multi-node dataset.
  2. Per-workstation comparative summaries.
  3. Time-based hourly progression trend series.
  4. Combined multi-factor correlations strictly avoiding causal language.
"""

from datetime import datetime, timezone
import pytest

from central_server.aggregation.aggregator import TelemetryAggregator, aggregate_telemetry
from central_server.analytics.analytics import (
    AnalyticsEngine,
    get_combined_correlations,
    get_time_based_trends,
    get_workstation_summaries,
)
from central_server.database.database import CentralDatabase


# ── Seeded Multi-Node Test Fixture ────────────────────────────────────────────

@pytest.fixture
def seeded_db() -> CentralDatabase:
    """Pre-populates an in-memory CentralDatabase with a known 6-window dataset across 3 nodes."""
    db = CentralDatabase(":memory:")

    # Register 3 devices
    db.register_device("Desk-Alpha", "0.1.0", assigned_id="NODE-001")
    db.register_device("Desk-Beta", "0.1.0", assigned_id="NODE-002")
    db.register_device("Desk-Gamma", "0.1.0", assigned_id="NODE-003")

    # Seed 6 known telemetry windows
    windows = [
        # Window 1: Node 1 at 09:00 (RULA 4, REBA 4, 20% high risk, NECK_FLEXION, 1 break rec/ack)
        {
            "device_id": "NODE-001",
            "session_id": "S-01",
            "window_start": "2026-09-19T09:00:00Z",
            "window_end": "2026-09-19T09:05:00Z",
            "ergonomics": {
                "average_rula": 4.0, "maximum_rula": 5,
                "average_reba": 4.0, "maximum_reba": 5,
                "high_risk_percentage": 20.0, "dominant_posture": "NECK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 80.0, "positive_percentage": 10.0,
                "negative_percentage": 0.0, "reduced_expression_percentage": 10.0,
            },
            "breaks": {"breaks_recommended": 1, "breaks_acknowledged": 1},
        },
        # Window 2: Node 1 at 10:00 (RULA 6, REBA 6, 80% high risk, NECK_FLEXION, 1 break rec / 0 ack)
        {
            "device_id": "NODE-001",
            "session_id": "S-01",
            "window_start": "2026-09-19T10:00:00Z",
            "window_end": "2026-09-19T10:05:00Z",
            "ergonomics": {
                "average_rula": 6.0, "maximum_rula": 7,
                "average_reba": 6.0, "maximum_reba": 7,
                "high_risk_percentage": 80.0, "dominant_posture": "NECK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 50.0, "positive_percentage": 10.0,
                "negative_percentage": 10.0, "reduced_expression_percentage": 30.0,
            },
            "breaks": {"breaks_recommended": 1, "breaks_acknowledged": 0},
        },
        # Window 3: Node 2 at 09:00 (RULA 2, REBA 2, 0% high risk, NEUTRAL, 0 breaks)
        {
            "device_id": "NODE-002",
            "session_id": "S-02",
            "window_start": "2026-09-19T09:00:00Z",
            "window_end": "2026-09-19T09:05:00Z",
            "ergonomics": {
                "average_rula": 2.0, "maximum_rula": 2,
                "average_reba": 2.0, "maximum_reba": 2,
                "high_risk_percentage": 0.0, "dominant_posture": "NEUTRAL",
            },
            "facial_expression": {
                "neutral_percentage": 90.0, "positive_percentage": 5.0,
                "negative_percentage": 0.0, "reduced_expression_percentage": 5.0,
            },
            "breaks": {"breaks_recommended": 0, "breaks_acknowledged": 0},
        },
        # Window 4: Node 2 at 14:00 (RULA 4, REBA 4, 10% high risk, TRUNK_FLEXION, 1 break rec/ack)
        {
            "device_id": "NODE-002",
            "session_id": "S-02",
            "window_start": "2026-09-19T14:00:00Z",
            "window_end": "2026-09-19T14:05:00Z",
            "ergonomics": {
                "average_rula": 4.0, "maximum_rula": 4,
                "average_reba": 4.0, "maximum_reba": 4,
                "high_risk_percentage": 10.0, "dominant_posture": "TRUNK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 70.0, "positive_percentage": 5.0,
                "negative_percentage": 5.0, "reduced_expression_percentage": 20.0,
            },
            "breaks": {"breaks_recommended": 1, "breaks_acknowledged": 1},
        },
        # Window 5: Node 3 at 14:00 (RULA 6, REBA 7, 70% high risk, TRUNK_FLEXION, 2 breaks rec / 1 ack)
        {
            "device_id": "NODE-003",
            "session_id": "S-03",
            "window_start": "2026-09-19T14:00:00Z",
            "window_end": "2026-09-19T14:05:00Z",
            "ergonomics": {
                "average_rula": 6.0, "maximum_rula": 6,
                "average_reba": 7.0, "maximum_reba": 8,
                "high_risk_percentage": 70.0, "dominant_posture": "TRUNK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 40.0, "positive_percentage": 10.0,
                "negative_percentage": 10.0, "reduced_expression_percentage": 40.0,
            },
            "breaks": {"breaks_recommended": 2, "breaks_acknowledged": 1},
        },
        # Window 6: Node 3 at 15:00 (RULA 5, REBA 5, 60% high risk, TRUNK_FLEXION, 1 break rec / 1 ack)
        {
            "device_id": "NODE-003",
            "session_id": "S-03",
            "window_start": "2026-09-19T15:00:00Z",
            "window_end": "2026-09-19T15:05:00Z",
            "ergonomics": {
                "average_rula": 5.0, "maximum_rula": 6,
                "average_reba": 5.0, "maximum_reba": 6,
                "high_risk_percentage": 60.0, "dominant_posture": "TRUNK_FLEXION",
            },
            "facial_expression": {
                "neutral_percentage": 60.0, "positive_percentage": 10.0,
                "negative_percentage": 5.0, "reduced_expression_percentage": 25.0,
            },
            "breaks": {"breaks_recommended": 1, "breaks_acknowledged": 1},
        },
    ]

    for w in windows:
        db.save_telemetry_window(w)

    yield db
    db.close()


# ── 1. Hand-Calculated Aggregate Verification ─────────────────────────────────

class TestAggregatorMath:

    def test_overall_dataset_hand_calculated_aggregates(self, seeded_db: CentralDatabase) -> None:
        """Verify exact mathematical averages and distributions against hand-calculated values."""
        agg = TelemetryAggregator(seeded_db)
        metrics = agg.aggregate()

        # Hand calculations:
        # Total windows: 6
        # Total nodes: 3
        # Average RULA: (4.0 + 6.0 + 2.0 + 4.0 + 6.0 + 5.0) / 6 = 27.0 / 6 = 4.50
        # Peak RULA: max(5, 7, 2, 4, 6, 6) = 7
        # Average REBA: (4.0 + 6.0 + 2.0 + 4.0 + 7.0 + 5.0) / 6 = 28.0 / 6 = 4.67
        # Peak REBA: max(5, 7, 2, 4, 8, 6) = 8
        # High-risk %: (20 + 80 + 0 + 10 + 70 + 60) / 6 = 240 / 6 = 40.0%
        # Dominant posture mode: TRUNK_FLEXION (3 windows vs 2 neck flexion vs 1 neutral)
        assert metrics.total_windows == 6
        assert metrics.total_nodes == 3
        assert metrics.average_rula == 4.50
        assert metrics.maximum_rula == 7
        assert metrics.average_reba == 4.67
        assert metrics.maximum_reba == 8
        assert metrics.high_risk_percentage == 40.0
        assert metrics.dominant_posture == "TRUNK_FLEXION"

        # Risk distribution:
        # LOW (<3): 1 (Window 3 = 2.0) -> 1/6 = 16.7%
        # MODERATE (3..4): 2 (Window 1 = 4.0, Window 4 = 4.0) -> 2/6 = 33.3%
        # HIGH (5..6): 3 (Window 2 = 6.0, Window 5 = 6.0, Window 6 = 5.0) -> 3/6 = 50.0%
        # VERY_HIGH (>=7): 0 -> 0.0%
        assert metrics.risk_distribution["LOW"] == 1
        assert metrics.risk_distribution["MODERATE"] == 2
        assert metrics.risk_distribution["HIGH"] == 3
        assert metrics.risk_distribution["VERY_HIGH"] == 0
        assert metrics.risk_percentages["LOW"] == 16.7
        assert metrics.risk_percentages["MODERATE"] == 33.3
        assert metrics.risk_percentages["HIGH"] == 50.0

        # Expression distribution:
        # neutral: (80 + 50 + 90 + 70 + 40 + 60) / 6 = 390 / 6 = 65.0%
        # reduced: (10 + 30 + 5 + 20 + 40 + 25) / 6 = 130 / 6 = 21.67%
        assert metrics.expression_distribution["neutral_percentage"] == 65.0
        assert metrics.expression_distribution["reduced_expression_percentage"] == 21.67

        # Break metrics:
        # Recommended: 1 + 1 + 0 + 1 + 2 + 1 = 6
        # Acknowledged: 1 + 0 + 0 + 1 + 1 + 1 = 4
        # Compliance: 4 / 6 * 100 = 66.7%
        assert metrics.total_breaks_recommended == 6
        assert metrics.total_breaks_acknowledged == 4
        assert metrics.break_compliance_rate == 66.7

    def test_aggregate_with_device_filter(self, seeded_db: CentralDatabase) -> None:
        """Filter aggregates specifically to NODE-001."""
        metrics = aggregate_telemetry(seeded_db, device_id="NODE-001")

        assert metrics.total_windows == 2
        assert metrics.total_nodes == 1
        # Avg RULA: (4.0 + 6.0) / 2 = 5.0
        assert metrics.average_rula == 5.0
        assert metrics.dominant_posture == "NECK_FLEXION"
        assert metrics.total_breaks_recommended == 2
        assert metrics.total_breaks_acknowledged == 1
        assert metrics.break_compliance_rate == 50.0


# ── 2. Workstation Summaries Tests ────────────────────────────────────────────

class TestWorkstationSummaries:

    def test_workstation_summaries_structure_and_values(self, seeded_db: CentralDatabase) -> None:
        summaries = get_workstation_summaries(seeded_db)
        assert len(summaries) == 3

        node_map = {s["device_id"]: s for s in summaries}

        # NODE-001
        n1 = node_map["NODE-001"]
        assert n1["device_name"] == "Desk-Alpha"
        assert n1["total_windows"] == 2
        assert n1["average_rula"] == 5.0
        assert n1["dominant_posture"] == "NECK_FLEXION"

        # NODE-002
        n2 = node_map["NODE-002"]
        assert n2["device_name"] == "Desk-Beta"
        assert n2["total_windows"] == 2
        # Avg RULA: (2.0 + 4.0) / 2 = 3.0
        assert n2["average_rula"] == 3.0
        assert n2["high_risk_percentage"] == 5.0

        # NODE-003
        n3 = node_map["NODE-003"]
        assert n3["total_windows"] == 2
        # Avg RULA: (6.0 + 5.0) / 2 = 5.5
        assert n3["average_rula"] == 5.5
        assert n3["dominant_posture"] == "TRUNK_FLEXION"


# ── 3. Time-Based Trends Tests ────────────────────────────────────────────────

class TestTimeBasedTrends:

    def test_hourly_trend_progression(self, seeded_db: CentralDatabase) -> None:
        """Verify hourly bucketing matching PRD §55 example format."""
        trends = get_time_based_trends(seeded_db, interval="hourly")
        assert len(trends) == 4  # 09:00, 10:00, 14:00, 15:00

        bucket_map = {t["time_bucket"][-8:]: t for t in trends}

        # 09:00: Windows 1 (RULA 4) & 3 (RULA 2) -> Avg 3.0 -> MODERATE
        b09 = bucket_map["09:00:00"]
        assert b09["window_count"] == 2
        assert b09["average_rula"] == 3.0
        assert b09["dominant_risk_level"] == "MODERATE"

        # 10:00: Window 2 (RULA 6) -> Avg 6.0 -> HIGH
        b10 = bucket_map["10:00:00"]
        assert b10["window_count"] == 1
        assert b10["average_rula"] == 6.0
        assert b10["dominant_risk_level"] == "HIGH"

        # 14:00: Windows 4 (RULA 4) & 5 (RULA 6) -> Avg 5.0 -> HIGH
        b14 = bucket_map["14:00:00"]
        assert b14["window_count"] == 2
        assert b14["average_rula"] == 5.0
        assert b14["dominant_risk_level"] == "HIGH"

        # 15:00: Window 6 (RULA 5) -> Avg 5.0 -> HIGH
        b15 = bucket_map["15:00:00"]
        assert b15["window_count"] == 1
        assert b15["average_rula"] == 5.0
        assert b15["dominant_risk_level"] == "HIGH"


# ── 4. Non-Causal Combined Analysis Tests ─────────────────────────────────────

class TestCombinedCorrelationsAndCausalityGuard:

    def test_combined_correlations_generation(self, seeded_db: CentralDatabase) -> None:
        results = get_combined_correlations(seeded_db)
        assert results["total_analyzed_windows"] == 6
        patterns = results["observed_patterns"]
        assert len(patterns) >= 2

        # Check structure
        for p in patterns:
            assert "pattern_id" in p
            assert "observed_pattern" in p
            assert "quantitative_metrics" in p

    def test_strict_non_causal_language_compliance(self, seeded_db: CentralDatabase) -> None:
        """PRD §54: Zero auto-generated text may imply causation."""
        results = get_combined_correlations(seeded_db)
        forbidden_causal_words = [
            "cause",
            "causes",
            "caused",
            "causing",
            "induce",
            "induces",
            "induced",
            "lead to",
            "leads to",
            "led to",
            "trigger",
            "triggers",
            "triggered",
            "due to emotion",
            "due to stress",
        ]

        for p in results["observed_patterns"]:
            text = p["observed_pattern"].lower()
            for forbidden in forbidden_causal_words:
                assert forbidden not in text, (
                    f"Causal language violation: found '{forbidden}' in pattern:\n{text}"
                )
            # Confirm approved correlational phrasing is present
            assert any(
                term in text
                for term in ("observed", "correlation", "co-occurred", "associated", "pattern", "trend")
            )
