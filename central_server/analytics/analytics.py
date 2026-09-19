"""
Collective Analytics Engine (PRD §51, §54, §55).

Computes:
  1. Per-workstation comparative summaries.
  2. Time-based trend series (e.g. hourly posture progression).
  3. Combined co-occurrence patterns between ergonomics, facial expressions, and breaks.

IMPORTANT ARCHITECTURAL CONSTRAINT (PRD §54):
  All combined multi-factor outputs must be presented strictly as
  "observed patterns" or "statistical correlations" — NEVER as causal claims.
  Do not generate text implying causation (e.g. 'X causes Y').
"""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import logging
from typing import Any, Optional

from central_server.aggregation.aggregator import (
    TelemetryAggregator,
    aggregate_telemetry,
    categorize_rula_risk,
)
from central_server.database.database import CentralDatabase

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Provides higher-level multi-node analytics, workstation comparisons, and trend series."""

    def __init__(self, db: CentralDatabase) -> None:
        self.db = db
        self.aggregator = TelemetryAggregator(db)

    # ── 1. Per-Workstation Summaries (PRD §51) ─────────────────────────────────

    def get_workstation_summaries(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Compute aggregated ergonomic & expression KPIs per registered workstation in a single batch pass."""
        devices = self.db.list_devices_with_health(timeout_sec=120.0)
        if not devices:
            return []

        # Single batch query across all devices in range (eliminates N+1 query pattern)
        query = """
            SELECT w.device_id, w.window_id, w.session_id, w.window_start, w.window_end,
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
        if start_date:
            query += " AND w.window_start >= ?"
            params.append(start_date)
        if end_date:
            query += " AND w.window_end <= ?"
            params.append(end_date)

        query += " ORDER BY w.window_start ASC"

        with self.db.get_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            all_rows = cursor.fetchall()

        rows_by_device: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for r in all_rows:
            rows_by_device[r["device_id"]].append(dict(r))

        summaries: list[dict[str, Any]] = []

        for dev in devices:
            device_id = dev["device_id"]
            rows = rows_by_device.get(device_id, [])
            total_windows = len(rows)

            if total_windows == 0:
                summaries.append({
                    "device_id": device_id,
                    "device_name": dev["device_name"],
                    "status": dev["health_status"],
                    "software_version": dev["software_version"],
                    "total_windows": 0,
                    "average_rula": 0.0,
                    "maximum_rula": 0,
                    "average_reba": 0.0,
                    "maximum_reba": 0,
                    "high_risk_percentage": 0.0,
                    "dominant_posture": "NEUTRAL",
                    "primary_expression": "Neutral",
                    "breaks_recommended": 0,
                    "breaks_acknowledged": 0,
                    "break_compliance_rate": 100.0,
                })
                continue

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

            posture_counts: dict[str, int] = collections.Counter(r["dominant_posture"] for r in rows)
            non_neutral = [p for p in posture_counts if p not in ("NEUTRAL", "NO_PERSON_DETECTED")]
            if non_neutral:
                dominant_posture = max(non_neutral, key=lambda k: posture_counts[k])
            else:
                dominant_posture = max(posture_counts, key=lambda k: posture_counts[k])

            neutral_avg = sum(float(r["neutral_percentage"]) for r in rows) / total_windows
            pos_avg = sum(float(r["positive_percentage"]) for r in rows) / total_windows
            neg_avg = sum(float(r["negative_percentage"]) for r in rows) / total_windows
            red_avg = sum(float(r["reduced_expression_percentage"]) for r in rows) / total_windows

            expr_map = {
                "Neutral": neutral_avg,
                "Positive": pos_avg,
                "Negative": neg_avg,
                "Reduced": red_avg,
            }
            primary_expr = max(expr_map, key=lambda k: expr_map[k])

            breaks_rec = sum(int(r["breaks_recommended"]) for r in rows)
            breaks_ack = sum(int(r["breaks_acknowledged"]) for r in rows)
            compliance = round((breaks_ack / breaks_rec * 100.0), 1) if breaks_rec > 0 else 100.0

            summaries.append({
                "device_id": device_id,
                "device_name": dev["device_name"],
                "status": dev["health_status"],
                "software_version": dev["software_version"],
                "total_windows": total_windows,
                "average_rula": avg_rula,
                "maximum_rula": peak_rula,
                "average_reba": avg_reba,
                "maximum_reba": peak_reba,
                "high_risk_percentage": avg_high_risk,
                "dominant_posture": dominant_posture,
                "primary_expression": primary_expr,
                "breaks_recommended": breaks_rec,
                "breaks_acknowledged": breaks_ack,
                "break_compliance_rate": compliance,
            })

        return summaries

    # ── 2. Time-Based Trend Series (PRD §55) ───────────────────────────────────

    def get_time_based_trends(
        self,
        interval: str = "hourly",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Bucket telemetry windows into temporal intervals.

        Example: '09:00 -> Low risk, 10:00 -> Moderate risk, 11:00 -> High risk'
        """
        query = """
            SELECT w.window_start, w.window_end, w.device_id,
                   p.average_rula, p.maximum_rula, p.average_reba, p.maximum_reba,
                   p.high_risk_percentage, p.dominant_posture,
                   w.breaks_recommended, w.breaks_acknowledged
            FROM telemetry_windows w
            JOIN posture_metrics p ON w.window_id = p.window_id
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

        if not rows:
            return []

        # Bucket rows by hour or day
        buckets: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for r in rows:
            ws = r["window_start"].replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(ws)
                if interval == "daily":
                    key = dt.strftime("%Y-%m-%d")
                else:
                    # Default: hourly bucket (YYYY-MM-DDTHH:00:00)
                    key = dt.strftime("%Y-%m-%dT%H:00:00")
            except Exception:
                key = ws[:13] + ":00:00" if len(ws) >= 13 else ws
            buckets[key].append(r)

        trend_series: list[dict[str, Any]] = []
        for bucket_key in sorted(buckets.keys()):
            b_rows = buckets[bucket_key]
            n = len(b_rows)
            avg_rula = round(sum(float(x["average_rula"]) for x in b_rows) / n, 2)
            max_rula = max(int(x["maximum_rula"]) for x in b_rows)
            avg_reba = round(sum(float(x["average_reba"]) for x in b_rows) / n, 2)
            max_reba = max(int(x["maximum_reba"]) for x in b_rows)
            avg_high_risk = round(sum(float(x["high_risk_percentage"]) for x in b_rows) / n, 2)

            # Dominant posture in bucket
            posture_counts = collections.Counter(x["dominant_posture"] for x in b_rows)
            non_neutral = [p for p in posture_counts if p not in ("NEUTRAL", "NO_PERSON_DETECTED")]
            dom_posture = max(non_neutral, key=lambda k: posture_counts[k]) if non_neutral else max(posture_counts, key=lambda k: posture_counts[k])

            trend_series.append({
                "time_bucket": bucket_key,
                "window_count": n,
                "average_rula": avg_rula,
                "maximum_rula": max_rula,
                "average_reba": avg_reba,
                "maximum_reba": max_reba,
                "high_risk_percentage": avg_high_risk,
                "dominant_risk_level": categorize_rula_risk(avg_rula),
                "dominant_posture": dom_posture,
            })

        return trend_series

    # ── 3. Combined Correlations & Observed Patterns (PRD §54) ────────────────

    def get_combined_correlations(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyze multi-factor relationships without making causal claims.

        Examines co-occurrences between:
          - Ergonomic risk & facial expression distributions
          - Ergonomic risk & time-of-day / session duration
          - Break events & risk score variations

        NON-CAUSAL CONSTRAINT: All generated observations use strictly correlational
        language ('co-occurred', 'associated with', 'observed pattern'), never causal
        language ('causes', 'caused', 'led to').
        """
        query = """
            SELECT w.window_id, w.device_id, w.window_start, w.breaks_recommended, w.breaks_acknowledged,
                   p.average_rula, p.high_risk_percentage, p.dominant_posture,
                   e.neutral_percentage, e.reduced_expression_percentage, e.positive_percentage, e.negative_percentage
            FROM telemetry_windows w
            JOIN posture_metrics p ON w.window_id = p.window_id
            JOIN expression_metrics e ON w.window_id = e.window_id
            WHERE 1=1
        """
        params: list[Any] = []
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
            return {
                "total_analyzed_windows": 0,
                "observed_patterns": [],
            }

        patterns: list[dict[str, Any]] = []

        # ── Pattern 1: Ergonomic Risk & Expression Co-occurrence ─────────────
        high_risk_rows = [r for r in rows if float(r["average_rula"]) >= 5.0 or float(r["high_risk_percentage"]) >= 50.0]
        low_risk_rows = [r for r in rows if float(r["average_rula"]) < 3.0]

        if high_risk_rows and low_risk_rows:
            avg_red_high = round(sum(float(r["reduced_expression_percentage"]) for r in high_risk_rows) / len(high_risk_rows), 1)
            avg_red_low = round(sum(float(r["reduced_expression_percentage"]) for r in low_risk_rows) / len(low_risk_rows), 1)
            diff_red = round(avg_red_high - avg_red_low, 1)

            obs_msg = (
                f"Observed statistical correlation: windows with elevated ergonomic risk (RULA >= 5.0) "
                f"co-occurred with an average of {avg_red_high}% reduced-expression state, compared to "
                f"{avg_red_low}% during low-risk windows (difference of {diff_red}%)."
            )
            patterns.append({
                "pattern_id": "PATTERN-ERGO-EXPR",
                "pattern_name": "Ergonomic Risk and Facial Expression Co-occurrence",
                "observed_pattern": obs_msg,
                "correlation_type": "positive" if diff_red > 0 else "neutral",
                "quantitative_metrics": {
                    "high_risk_sample_count": len(high_risk_rows),
                    "low_risk_sample_count": len(low_risk_rows),
                    "high_risk_reduced_expression_avg": avg_red_high,
                    "low_risk_reduced_expression_avg": avg_red_low,
                },
            })

        # ── Pattern 2: Time-of-Day Progression ────────────────────────────────
        morning_rows = []
        afternoon_rows = []
        for r in rows:
            try:
                hour = datetime.fromisoformat(r["window_start"].replace("Z", "+00:00")).hour
                if 8 <= hour < 12:
                    morning_rows.append(r)
                elif 12 <= hour < 18:
                    afternoon_rows.append(r)
            except Exception:
                continue

        if morning_rows and afternoon_rows:
            avg_rula_morn = round(sum(float(r["average_rula"]) for r in morning_rows) / len(morning_rows), 2)
            avg_rula_aft = round(sum(float(r["average_rula"]) for r in afternoon_rows) / len(afternoon_rows), 2)
            rula_diff = round(avg_rula_aft - avg_rula_morn, 2)

            obs_msg = (
                f"Observed temporal pattern: average RULA scores recorded during afternoon hours "
                f"(12:00-18:00) averaged {avg_rula_aft} compared to {avg_rula_morn} during morning "
                f"hours (08:00-12:00), showing a delta of {rula_diff:+0.2f} points."
            )
            patterns.append({
                "pattern_id": "PATTERN-TIME-PROGRESSION",
                "pattern_name": "Diurnal Posture Trend",
                "observed_pattern": obs_msg,
                "correlation_type": "temporal",
                "quantitative_metrics": {
                    "morning_windows": len(morning_rows),
                    "afternoon_windows": len(afternoon_rows),
                    "morning_average_rula": avg_rula_morn,
                    "afternoon_average_rula": avg_rula_aft,
                },
            })

        # ── Pattern 3: Break Compliance & Posture Relationship ────────────────
        break_ack_rows = [r for r in rows if int(r["breaks_acknowledged"]) > 0]
        break_none_rows = [r for r in rows if int(r["breaks_acknowledged"]) == 0 and int(r["breaks_recommended"]) > 0]

        if break_ack_rows and break_none_rows:
            hr_ack = round(sum(float(r["high_risk_percentage"]) for r in break_ack_rows) / len(break_ack_rows), 1)
            hr_none = round(sum(float(r["high_risk_percentage"]) for r in break_none_rows) / len(break_none_rows), 1)

            obs_msg = (
                f"Observed wellness association: sessions with acknowledged movement breaks exhibited "
                f"an average high-risk posture percentage of {hr_ack}%, compared to {hr_none}% in sessions "
                f"where recommended breaks were not acknowledged."
            )
            patterns.append({
                "pattern_id": "PATTERN-BREAK-ASSOCIATION",
                "pattern_name": "Break Response Association",
                "observed_pattern": obs_msg,
                "correlation_type": "inverse" if hr_ack < hr_none else "neutral",
                "quantitative_metrics": {
                    "acknowledged_break_windows": len(break_ack_rows),
                    "unacknowledged_break_windows": len(break_none_rows),
                    "high_risk_pct_with_breaks": hr_ack,
                    "high_risk_pct_without_breaks": hr_none,
                },
            })

        return {
            "total_analyzed_windows": total_windows,
            "observed_patterns": patterns,
        }


# ── Functional Conveniences ───────────────────────────────────────────────────

def get_workstation_summaries(
    db: CentralDatabase,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    return AnalyticsEngine(db).get_workstation_summaries(start_date=start_date, end_date=end_date)


def get_time_based_trends(
    db: CentralDatabase,
    interval: str = "hourly",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    device_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    return AnalyticsEngine(db).get_time_based_trends(
        interval=interval, start_date=start_date, end_date=end_date, device_id=device_id
    )


def get_combined_correlations(
    db: CentralDatabase,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    return AnalyticsEngine(db).get_combined_correlations(start_date=start_date, end_date=end_date)
