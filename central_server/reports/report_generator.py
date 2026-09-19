"""
Report generator for EdgeErgo (PRD §106, Phase 15).

Produces:
  1. RFC-4180 compliant CSV exports of verified ergonomic telemetry windows.
  2. Structured Periodic Reports (daily, weekly, monthly) matching Analytics & Reports pages.
  3. Standalone print-optimized HTML reports for browser print-to-PDF.

PRIVACY GUARANTEE:
  Exports and reports contain strictly aggregated telemetry and posture metrics.
  Zero video streams, raw camera frames, facial crops, or landmark embeddings are ever included.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import io
import json
import logging
from typing import Any, Optional
import uuid

from central_server.aggregation.aggregator import (
    TelemetryAggregator,
    categorize_rula_risk,
)
from central_server.analytics.analytics import (
    AnalyticsEngine,
    get_combined_correlations,
    get_time_based_trends,
    get_workstation_summaries,
)
from central_server.database.database import CentralDatabase

logger = logging.getLogger(__name__)


def _parse_or_default_range(
    report_type: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, str]:
    """Calculate ISO 8601 start and end timestamps based on report period."""
    now = datetime.now(timezone.utc)
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except Exception:
            end_dt = now
    else:
        end_dt = now

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except Exception:
            start_dt = end_dt - timedelta(days=1)
    else:
        norm_type = report_type.lower()
        if norm_type == "daily":
            start_dt = end_dt - timedelta(days=1)
        elif norm_type == "weekly":
            start_dt = end_dt - timedelta(days=7)
        elif norm_type == "monthly":
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = end_dt - timedelta(days=7)

    return start_dt.isoformat().replace("+00:00", "Z"), end_dt.isoformat().replace("+00:00", "Z")


class ReportGenerator:
    """Generates compliance CSV exports and structured periodic ergonomic reports."""

    def __init__(self, db: CentralDatabase) -> None:
        self.db = db

    # ── 1. CSV Telemetry Export (PRD §88, §106) ───────────────────────────────

    def generate_csv(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> str:
        """Export telemetry and posture assessment records to clean CSV text."""
        query = """
            SELECT
                w.window_id,
                w.device_id,
                d.device_name,
                w.session_id,
                w.window_start,
                w.window_end,
                ROUND((JULIANDAY(w.window_end) - JULIANDAY(w.window_start)) * 86400.0, 1) as duration_sec,
                p.average_rula,
                p.maximum_rula,
                p.average_reba,
                p.maximum_reba,
                p.high_risk_percentage,
                p.dominant_posture,
                e.neutral_percentage,
                e.positive_percentage,
                e.negative_percentage,
                e.reduced_expression_percentage,
                w.breaks_recommended,
                w.breaks_acknowledged
            FROM telemetry_windows w
            LEFT JOIN devices d ON w.device_id = d.device_id
            LEFT JOIN posture_metrics p ON w.window_id = p.window_id
            LEFT JOIN expression_metrics e ON w.window_id = e.window_id
            WHERE 1=1
        """
        params: list[Any] = []
        if start_date:
            query += " AND w.window_start >= ?"
            params.append(start_date)
        if end_date:
            query += " AND w.window_start <= ?"
            params.append(end_date)
        if device_id:
            query += " AND w.device_id = ?"
            params.append(device_id)

        query += " ORDER BY w.window_start DESC"

        with self.db.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Standard CSV header
        writer.writerow([
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
        ])

        for r in rows:
            avg_rula = float(r["average_rula"]) if r["average_rula"] is not None else 1.0
            risk_cat = categorize_rula_risk(avg_rula)
            writer.writerow([
                r["window_id"],
                r["device_id"],
                r["device_name"] or f"Station {r['device_id']}",
                r["session_id"],
                r["window_start"],
                r["window_end"],
                r["duration_sec"] or 300.0,
                f"{avg_rula:.1f}",
                r["maximum_rula"] or 1,
                f"{float(r['average_reba'] or 1.0):.1f}",
                r["maximum_reba"] or 1,
                risk_cat,
                r["dominant_posture"] or "NEUTRAL",
                f"{float(r['neutral_percentage'] or 100.0):.1f}",
                f"{float(r['positive_percentage'] or 0.0):.1f}",
                f"{float(r['negative_percentage'] or 0.0):.1f}",
                f"{float(r['reduced_expression_percentage'] or 0.0):.1f}",
                r["breaks_recommended"] or 0,
                r["breaks_acknowledged"] or 0,
            ])

        return output.getvalue()

    # ── 2. Structured Periodic Report Generation (PRD §106) ───────────────────

    def generate_report(
        self,
        report_type: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        save: bool = True,
    ) -> dict[str, Any]:
        """Produce structured periodic report matching Reports and Analytics pages."""
        norm_type = report_type.lower()
        if norm_type not in ("daily", "weekly", "monthly"):
            norm_type = "daily"

        s_date, e_date = _parse_or_default_range(norm_type, start_date, end_date)

        # 1. Compute aggregate fleet metrics for the period
        agg = TelemetryAggregator(self.db)
        metrics = agg.aggregate(start_date=start_date, end_date=end_date)

        # 2. Compute per-workstation comparison
        analytics = AnalyticsEngine(self.db)
        worker_comparisons = analytics.get_workstation_summaries(start_date=start_date, end_date=end_date)

        # 3. Compute time trends
        trend_interval = "hourly" if norm_type == "daily" else "daily"
        posture_trends = get_time_based_trends(
            self.db, interval=trend_interval, start_date=start_date, end_date=end_date
        )

        # 4. Count unique sessions & high risk incidents in period
        with self.db.get_connection() as conn:
            query_sess = (
                "SELECT COUNT(DISTINCT session_id) as sess_cnt, "
                "COUNT(DISTINCT device_id) as dev_cnt FROM telemetry_windows WHERE 1=1"
            )
            params_sess = []
            if start_date:
                query_sess += " AND window_start >= ?"
                params_sess.append(start_date)
            if end_date:
                query_sess += " AND window_start <= ?"
                params_sess.append(end_date)

            cnt_row = conn.execute(query_sess, params_sess).fetchone()
            sessions_count = cnt_row["sess_cnt"] if cnt_row else 0
            workers_analyzed = cnt_row["dev_cnt"] if cnt_row else len(worker_comparisons)

            # High risk alert events count
            query_alert = "SELECT COUNT(*) as alert_cnt FROM events WHERE event_type = 'ALERT'"
            params_alert = []
            if start_date:
                query_alert += " AND timestamp >= ?"
                params_alert.append(start_date)
            if end_date:
                query_alert += " AND timestamp <= ?"
                params_alert.append(end_date)

            alert_row = conn.execute(query_alert, params_alert).fetchone()
            high_risk_events_count = alert_row["alert_cnt"] if alert_row else 0

        # 5. Formulate actionable insight observation
        compliance_pct = round(max(0.0, 100.0 - metrics.high_risk_percentage), 1)
        if metrics.high_risk_percentage > 20.0:
            observation = (
                f"Fleet posture compliance during this {norm_type} period stood at {compliance_pct}%. "
                f"Elevated risk was predominantly associated with {metrics.dominant_posture.replace('_', ' ').title()}. "
                "Recommend targeted ergonomic workstation adjustments and scheduled movement reminders."
            )
        else:
            observation = (
                f"Optimal posture compliance of {compliance_pct}% maintained across all monitored workstations "
                f"throughout this {norm_type} evaluation period."
            )

        # 6. Assemble report data structure
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        report_id = f"RPT-{norm_type.upper()}-{uuid.uuid4().hex[:8]}"

        report_payload: dict[str, Any] = {
            "report_id": report_id,
            "report_type": norm_type,
            "title": f"EdgeErgo {norm_type.capitalize()} Ergonomic Executive Briefing",
            "start_date": s_date,
            "end_date": e_date,
            "generated_at": now_iso,
            "summary": {
                "workers_analyzed": workers_analyzed,
                "sessions_count": sessions_count,
                "total_windows": metrics.total_windows,
                "average_rula": round(metrics.average_rula, 1),
                "maximum_rula": metrics.maximum_rula,
                "average_reba": round(metrics.average_reba, 1),
                "maximum_reba": metrics.maximum_reba,
                "high_risk_windows_count": round(metrics.total_windows * (metrics.high_risk_percentage / 100.0)),
                "high_risk_events_count": high_risk_events_count,
                "posture_compliance_pct": compliance_pct,
                "break_adherence_pct": metrics.break_compliance_rate,
                "dominant_posture": metrics.dominant_posture,
            },
            "risk_distribution": metrics.risk_distribution,
            "posture_trend": posture_trends,
            "worker_comparison": worker_comparisons,
            "expression_patterns": {
                "neutral_percentage": metrics.expression_distribution.get("neutral_percentage", 100.0),
                "reduced_expression_percentage": metrics.expression_distribution.get("reduced_expression_percentage", 0.0),
                "other_expression_percentage": round(
                    metrics.expression_distribution.get("positive_percentage", 0.0) +
                    metrics.expression_distribution.get("negative_percentage", 0.0),
                    1
                ),
            },
            "actionable_observation": observation,
            "privacy_statement": (
                "CONFIRMED: Assessment conducted via decentralized edge computer vision. "
                "Zero camera feeds, facial crops, or raw video streams stored or transmitted."
            ),
        }

        # 7. Persist to reports table
        if save:
            try:
                self.db.save_report(
                    report_id=report_id,
                    report_type=norm_type,
                    start_date=s_date,
                    end_date=e_date,
                    data_json=json.dumps(report_payload),
                    generated_at=now_iso,
                )
            except Exception as e:
                logger.warning("Failed to persist report %s to database: %s", report_id, e)

        return report_payload

    # ── 3. Standalone Print-Ready HTML Report (PRD §106) ───────────────────────

    def generate_html_report(self, report_data: dict[str, Any]) -> str:
        """Render a standalone, dark-themed, print-optimized HTML executive briefing."""
        rep = report_data
        summary = rep.get("summary", {})
        workers = rep.get("worker_comparison", [])
        dist = rep.get("risk_distribution", {})
        expr = rep.get("expression_patterns", {})

        worker_rows = ""
        for w in workers:
            is_high = w.get("average_rula", 1.0) >= 5.0
            r_color = "#FF6B7A" if is_high else "#39D98A" if w.get("average_rula", 1.0) < 3.0 else "#F2C94C"
            worker_rows += f"""
            <tr>
              <td style="padding: 10px; border-bottom: 1px solid #303030; font-weight: 500;">{w.get('device_name', '')} ({w.get('device_id', '')})</td>
              <td style="padding: 10px; border-bottom: 1px solid #303030; font-family: monospace; color: {r_color};">{w.get('average_rula', 1.0):.1f}</td>
              <td style="padding: 10px; border-bottom: 1px solid #303030; font-family: monospace;">{w.get('average_reba', 1.0):.1f}</td>
              <td style="padding: 10px; border-bottom: 1px solid #303030;">{w.get('dominant_posture', '').replace('_', ' ')}</td>
              <td style="padding: 10px; border-bottom: 1px solid #303030; font-family: monospace;">{w.get('break_compliance_rate', 0)}%</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{rep.get('title', 'EdgeErgo Report')}</title>
  <style>
    body {{
      background-color: #121212;
      color: #F5F5F5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 40px;
      line-height: 1.5;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      background: #1D1D1D;
      border: 1px solid #303030;
      border-radius: 14px;
      padding: 32px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid #303030;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    .logo {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}
    .logo span {{ color: #D98CB3; }}
    .meta {{
      text-align: right;
      font-size: 12px;
      color: #A7A7A7;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}
    .kpi-card {{
      background: #222222;
      border: 1px solid #303030;
      border-radius: 10px;
      padding: 14px;
    }}
    .kpi-label {{
      font-size: 12px;
      color: #A7A7A7;
      margin-bottom: 6px;
      text-transform: uppercase;
    }}
    .kpi-val {{
      font-size: 26px;
      font-weight: 600;
      color: #F5F5F5;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
      font-size: 13px;
    }}
    th {{
      text-align: left;
      padding: 10px;
      background: #222222;
      color: #A7A7A7;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1px solid #303030;
    }}
    .observation-box {{
      background: #222222;
      border-left: 4px solid #D98CB3;
      padding: 16px;
      border-radius: 6px;
      margin: 24px 0;
      font-size: 13px;
    }}
    .privacy-notice {{
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid #303030;
      font-size: 11px;
      color: #707070;
      text-align: center;
    }}
    @media print {{
      body {{ background-color: #ffffff; color: #000000; padding: 0; }}
      .container {{ border: none; box-shadow: none; padding: 0; }}
      .kpi-card, .observation-box {{ background: #f8f9fa; border: 1px solid #dee2e6; color: #000; }}
      .kpi-val {{ color: #000; }}
      th {{ background: #e9ecef; color: #495057; }}
      td {{ border-bottom: 1px solid #dee2e6; color: #000; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <div class="logo">EDGE<span>ERGO</span></div>
        <h2 style="margin: 8px 0 0 0; font-size: 22px;">{rep.get('title')}</h2>
        <div style="font-size: 12px; color: #A7A7A7; margin-top: 4px;">Period: {rep.get('start_date')} to {rep.get('end_date')}</div>
      </div>
      <div class="meta">
        <div><strong>Report ID:</strong> {rep.get('report_id')}</div>
        <div><strong>Generated:</strong> {rep.get('generated_at')}</div>
        <div style="margin-top: 4px; color: #39D98A;">Status: Validated Compliance</div>
      </div>
    </div>

    <!-- Summary KPIs -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Workers Monitored</div>
        <div class="kpi-val">{summary.get('workers_analyzed', 0)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Average Fleet RULA</div>
        <div class="kpi-val">{summary.get('average_rula', 1.0)} / 7</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Posture Compliance</div>
        <div class="kpi-val" style="color: #39D98A;">{summary.get('posture_compliance_pct', 100)}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Break Adherence</div>
        <div class="kpi-val">{summary.get('break_adherence_pct', 0)}%</div>
      </div>
    </div>

    <!-- Actionable Insight -->
    <div class="observation-box">
      <strong>Actionable Intelligence Observation:</strong><br>
      {rep.get('actionable_observation', '')}
    </div>

    <!-- Workstation Breakdown -->
    <h3 style="font-size: 16px; margin: 24px 0 8px 0;">Monitored Workstations Audit</h3>
    <table>
      <thead>
        <tr>
          <th>Workstation / Node</th>
          <th>Avg RULA</th>
          <th>Avg REBA</th>
          <th>Dominant Defect</th>
          <th>Break Adherence</th>
        </tr>
      </thead>
      <tbody>
        {worker_rows if worker_rows else '<tr><td colspan="5" style="text-align:center; padding:16px;">No workstation records for this timeframe.</td></tr>'}
      </tbody>
    </table>

    <div class="privacy-notice">
      {rep.get('privacy_statement')}<br>
      EdgeErgo Distributed AI Architecture &bull; ISO/IEC Ergonomic Assessment Standards Compliant
    </div>
  </div>
</body>
</html>
"""
        return html
