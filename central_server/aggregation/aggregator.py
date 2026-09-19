"""
Collective Telemetry Aggregation Engine (PRD §50, §54).

Aggregates posture metrics, facial expressions, and break compliance
across multiple Edge Nodes and time windows into actionable statistics.
"""

from __future__ import annotations

import collections
from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Optional

from central_server.database.database import CentralDatabase

logger = logging.getLogger(__name__)


# ── Aggregated Data Structure ─────────────────────────────────────────────────

@dataclass
class AggregatedMetrics:
    """Consolidated metrics across a set of telemetry windows."""
    total_windows: int
    total_nodes: int
    average_rula: float
    maximum_rula: int
    average_reba: float
    maximum_reba: int
    high_risk_percentage: float
    dominant_posture: str
    risk_distribution: dict[str, int] = field(default_factory=dict)
    risk_percentages: dict[str, float] = field(default_factory=dict)
    posture_distribution: dict[str, int] = field(default_factory=dict)
    expression_distribution: dict[str, float] = field(default_factory=dict)
    total_breaks_recommended: int = 0
    total_breaks_acknowledged: int = 0
    break_compliance_rate: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Helper for Risk Categorization ───────────────────────────────────────────

def categorize_rula_risk(rula_score: float) -> str:
    """Categorize numerical RULA score into official Action Level risk."""
    if rula_score >= 7.0:
        return "VERY_HIGH"
    elif rula_score >= 5.0:
        return "HIGH"
    elif rula_score >= 3.0:
        return "MODERATE"
    return "LOW"


# ── Aggregator Engine ─────────────────────────────────────────────────────────

class TelemetryAggregator:
    """Computes statistical summaries across telemetry windows stored in CentralDatabase."""

    def __init__(self, db: CentralDatabase) -> None:
        self.db = db

    def aggregate(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> AggregatedMetrics:
        """Query and aggregate telemetry data matching optional filters.

        Args:
            start_date: Optional ISO 8601 lower bound for window_start.
            end_date:   Optional ISO 8601 upper bound for window_end.
            device_id:  Optional filter for a specific Edge Node ID.

        Returns:
            AggregatedMetrics object containing mathematical averages and distributions.
        """
        query = """
            SELECT w.window_id, w.device_id, w.session_id, w.window_start, w.window_end,
                   w.breaks_recommended, w.breaks_acknowledged,
                   p.average_rula, p.maximum_rula, p.average_reba, p.maximum_reba,
                   p.high_risk_percentage, p.dominant_posture,
                   e.neutral_percentage, e.positive_percentage, e.negative_percentage,
                   e.reduced_expression_percentage
            FROM telemetry_windows w
            JOIN posture_metrics p ON w.window_id = p.window_id
            JOIN expression_metrics e ON w.window_id = e.window_id
            WHERE 1=1
        """
        params: list[Any] = []

        if device_id:
            query += " AND w.device_id = ?"
            params.append(device_id)
        if start_date:
            query += " AND w.window_start >= ?"
            params.append(start_date)
        if end_date:
            query += " AND w.window_end <= ?"
            params.append(end_date)

        query += " ORDER BY w.window_start ASC"

        with self.db.get_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = [dict(r) for r in cursor.fetchall()]

        total_windows = len(rows)
        if total_windows == 0:
            return AggregatedMetrics(
                total_windows=0,
                total_nodes=0,
                average_rula=0.0,
                maximum_rula=0,
                average_reba=0.0,
                maximum_reba=0,
                high_risk_percentage=0.0,
                dominant_posture="NEUTRAL",
                risk_distribution={"LOW": 0, "MODERATE": 0, "HIGH": 0, "VERY_HIGH": 0},
                risk_percentages={"LOW": 0.0, "MODERATE": 0.0, "HIGH": 0.0, "VERY_HIGH": 0.0},
                posture_distribution={},
                expression_distribution={
                    "neutral_percentage": 0.0,
                    "positive_percentage": 0.0,
                    "negative_percentage": 0.0,
                    "reduced_expression_percentage": 0.0,
                },
                total_breaks_recommended=0,
                total_breaks_acknowledged=0,
                break_compliance_rate=100.0,
            )

        unique_nodes = len(set(r["device_id"] for r in rows))
        rula_scores = [float(r["average_rula"]) for r in rows]
        max_rulas = [int(r["maximum_rula"]) for r in rows]
        reba_scores = [float(r["average_reba"]) for r in rows]
        max_rebas = [int(r["maximum_reba"]) for r in rows]
        high_risk_pcts = [float(r["high_risk_percentage"]) for r in rows]

        avg_rula = round(sum(rula_scores) / total_windows, 2)
        peak_rula = max(max_rulas)
        avg_reba = round(sum(reba_scores) / total_windows, 2)
        peak_reba = max(max_rebas)
        avg_high_risk = round(sum(high_risk_pcts) / total_windows, 2)

        # Risk distribution based on window average RULA
        risk_dist: dict[str, int] = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "VERY_HIGH": 0}
        for score in rula_scores:
            cat = categorize_rula_risk(score)
            risk_dist[cat] += 1

        risk_pcts = {
            cat: round((cnt / total_windows) * 100.0, 1)
            for cat, cnt in risk_dist.items()
        }

        # Posture distribution and dominant posture mode
        posture_counts: dict[str, int] = collections.Counter(
            r["dominant_posture"] for r in rows
        )
        # Choose most frequent posture (preferring non-neutral if present)
        non_neutral = [p for p in posture_counts if p not in ("NEUTRAL", "NO_PERSON_DETECTED")]
        if non_neutral:
            dominant_posture = max(non_neutral, key=lambda k: posture_counts[k])
        else:
            dominant_posture = max(posture_counts, key=lambda k: posture_counts[k])

        # Expression distribution averages
        neutral_avg = round(sum(float(r["neutral_percentage"]) for r in rows) / total_windows, 2)
        pos_avg = round(sum(float(r["positive_percentage"]) for r in rows) / total_windows, 2)
        neg_avg = round(sum(float(r["negative_percentage"]) for r in rows) / total_windows, 2)
        red_avg = round(sum(float(r["reduced_expression_percentage"]) for r in rows) / total_windows, 2)

        # Break metrics
        breaks_rec = sum(int(r["breaks_recommended"]) for r in rows)
        breaks_ack = sum(int(r["breaks_acknowledged"]) for r in rows)
        compliance_rate = round((breaks_ack / breaks_rec * 100.0), 1) if breaks_rec > 0 else 100.0

        return AggregatedMetrics(
            total_windows=total_windows,
            total_nodes=unique_nodes,
            average_rula=avg_rula,
            maximum_rula=peak_rula,
            average_reba=avg_reba,
            maximum_reba=peak_reba,
            high_risk_percentage=avg_high_risk,
            dominant_posture=dominant_posture,
            risk_distribution=dict(risk_dist),
            risk_percentages=risk_pcts,
            posture_distribution=dict(posture_counts),
            expression_distribution={
                "neutral_percentage": neutral_avg,
                "positive_percentage": pos_avg,
                "negative_percentage": neg_avg,
                "reduced_expression_percentage": red_avg,
            },
            total_breaks_recommended=breaks_rec,
            total_breaks_acknowledged=breaks_ack,
            break_compliance_rate=compliance_rate,
        )


def aggregate_telemetry(
    db: CentralDatabase,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    device_id: Optional[str] = None,
) -> AggregatedMetrics:
    """Convenience functional wrapper for TelemetryAggregator."""
    agg = TelemetryAggregator(db)
    return agg.aggregate(start_date=start_date, end_date=end_date, device_id=device_id)
