"""
Report and data export REST API routes (PRD §88, §106, Phase 15).

Endpoints:
  GET /api/v1/export/csv               — Export aggregated telemetry & posture assessment records
  GET /api/v1/reports/{report_type}    — Generate structured periodic report (daily, weekly, monthly)
  GET /api/v1/reports/{report_type}/html — Standalone print-optimized report for browser print-to-PDF
  GET /api/v1/reports                  — List historical generated reports
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

from central_server.api.edge import get_database
from central_server.database.database import CentralDatabase
from central_server.reports.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Reports & Exports"])


# ── 1. Telemetry CSV Export (PRD §88, §106) ───────────────────────────────────

@router.get(
    "/export/csv",
    summary="Export Telemetry CSV",
    description="Export aggregated posture and ergonomic telemetry data to clean CSV.",
)
def export_telemetry_csv(
    start_date: Optional[str] = Query(None, description="Start date filter (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO 8601)"),
    device_id: Optional[str] = Query(None, description="Filter by node/device identifier"),
    db: CentralDatabase = Depends(get_database),
) -> Response:
    generator = ReportGenerator(db)
    csv_content = generator.generate_csv(
        start_date=start_date, end_date=end_date, device_id=device_id
    )

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"edgeergo_telemetry_export_{now_str}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


# ── 2. Structured Periodic Reports (PRD §106) ─────────────────────────────────

@router.get(
    "/reports/{report_type}",
    summary="Generate Periodic Report",
    description="Generate daily, weekly, or monthly executive ergonomic reports.",
)
def get_periodic_report(
    report_type: str,
    start_date: Optional[str] = Query(None, description="Start date filter (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO 8601)"),
    db: CentralDatabase = Depends(get_database),
) -> dict[str, Any]:
    norm_type = report_type.lower()
    if norm_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type '{report_type}'. Must be 'daily', 'weekly', or 'monthly'.",
        )

    generator = ReportGenerator(db)
    return generator.generate_report(
        report_type=norm_type, start_date=start_date, end_date=end_date, save=True
    )


# ── 3. Standalone Print-Ready HTML Report (PRD §106) ──────────────────────────

@router.get(
    "/reports/{report_type}/html",
    response_class=HTMLResponse,
    summary="Generate Print-Ready HTML Report",
    description="Generate styled executive report formatted for browser Print-to-PDF.",
)
def get_report_html(
    report_type: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: CentralDatabase = Depends(get_database),
) -> HTMLResponse:
    norm_type = report_type.lower()
    if norm_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type '{report_type}'. Must be 'daily', 'weekly', or 'monthly'.",
        )

    generator = ReportGenerator(db)
    report_data = generator.generate_report(
        report_type=norm_type, start_date=start_date, end_date=end_date, save=False
    )
    html = generator.generate_html_report(report_data)
    return HTMLResponse(content=html)


# ── 4. Historical Reports Inventory ───────────────────────────────────────────

@router.get(
    "/reports",
    summary="List Generated Reports",
    description="List previously generated and persisted executive compliance reports.",
)
def list_reports(
    report_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: CentralDatabase = Depends(get_database),
) -> list[dict[str, Any]]:
    return db.list_reports(report_type=report_type, limit=limit)
