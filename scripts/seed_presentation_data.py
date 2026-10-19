"""
Seed Presentation Data for EdgeErgo Executive Showcase.

Populates central_server.db with a multi-workstation fleet:
- NODE-001: Engineering CAD Rig 1 (Active, Low/Mod Risk)
- NODE-002: Financial Analyst Terminal 4 (Active, Moderate Risk)
- NODE-003: UX Design Workstation 2 (Active, Optimal Ergonomics)
- NODE-004: Data Operations Console 3 (Active, High Risk Posture)
- NODE-005: Executive Strategy Desk (Active, Good Ergonomics)

Generates time-series telemetry windows, posture & expression metrics,
and alert events to make all dashboard pages (Overview, Workstations,
Devices, Analytics, Reports, Alerts) look rich and presentation-ready.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from central_server.database.database import CentralDatabase

def seed_database(db_path: str = "central_server.db"):
    db = CentralDatabase(db_path=db_path, auto_init=True)
    now = datetime.now(timezone.utc)

    workstations = [
        {
            "id": "NODE-001",
            "name": "Engineering CAD Rig 1",
            "base_rula": 3.4,
            "base_reba": 3.1,
            "dominant": "FORWARD_HEAD",
            "high_risk_pct": 12.5,
            "neutral_pct": 74.0,
            "positive_pct": 18.0,
            "negative_pct": 5.0,
            "reduced_pct": 3.0,
            "breaks_rec": 4,
            "breaks_ack": 3,
        },
        {
            "id": "NODE-002",
            "name": "Financial Trading Terminal 4",
            "base_rula": 5.2,
            "base_reba": 4.8,
            "dominant": "TRUNK_FLEXION",
            "high_risk_pct": 38.0,
            "neutral_pct": 68.0,
            "positive_pct": 8.0,
            "negative_pct": 16.0,
            "reduced_pct": 8.0,
            "breaks_rec": 6,
            "breaks_ack": 2,
        },
        {
            "id": "NODE-003",
            "name": "UX Design Workstation 2",
            "base_rula": 2.1,
            "base_reba": 1.9,
            "dominant": "NEUTRAL",
            "high_risk_pct": 4.0,
            "neutral_pct": 65.0,
            "positive_pct": 28.0,
            "negative_pct": 4.0,
            "reduced_pct": 3.0,
            "breaks_rec": 5,
            "breaks_ack": 5,
        },
        {
            "id": "NODE-004",
            "name": "Data Operations Console 3",
            "base_rula": 5.8,
            "base_reba": 5.4,
            "dominant": "SLOUCHING",
            "high_risk_pct": 46.5,
            "neutral_pct": 60.0,
            "positive_pct": 6.0,
            "negative_pct": 22.0,
            "reduced_pct": 12.0,
            "breaks_rec": 7,
            "breaks_ack": 3,
        },
        {
            "id": "NODE-005",
            "name": "Executive Strategy Desk",
            "base_rula": 2.5,
            "base_reba": 2.2,
            "dominant": "NEUTRAL",
            "high_risk_pct": 6.0,
            "neutral_pct": 72.0,
            "positive_pct": 22.0,
            "negative_pct": 4.0,
            "reduced_pct": 2.0,
            "breaks_rec": 3,
            "breaks_ack": 3,
        },
    ]

    print(f"[*] Registering {len(workstations)} enterprise workstation nodes...")

    with db.get_connection() as conn:
        for ws in workstations:
            # Register or update device
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, device_name, software_version, registered_at,
                    last_seen, status, camera_detected, camera_index
                ) VALUES (?, ?, '0.1.0', ?, ?, 'active', 1, 0)
                ON CONFLICT(device_id) DO UPDATE SET
                    device_name = excluded.device_name,
                    last_seen = excluded.last_seen,
                    status = 'active'
                """,
                (
                    ws["id"],
                    ws["name"],
                    (now - timedelta(days=7)).isoformat(),
                    (now - timedelta(seconds=random.randint(5, 45))).isoformat(),
                ),
            )

            # Create sessions and telemetry windows across last 8 hours
            session_id = f"SESS-{ws['id']}-20261008"
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, device_id, start_time, end_time, duration, created_at)
                VALUES (?, ?, ?, ?, 28800.0, ?)
                """,
                (
                    session_id,
                    ws["id"],
                    (now - timedelta(hours=8)).isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

            # Generate windows spaced every 15 minutes over the last 8 hours (32 windows per node)
            for i in range(32):
                win_time = now - timedelta(hours=8) + timedelta(minutes=15 * i)
                win_end = win_time + timedelta(minutes=5)
                win_id = f"WIN-{ws['id']}-{i:03d}"

                # Calculate hourly variation: higher fatigue & RULA mid-afternoon (approx window 20-26)
                fatigue_factor = 0.8 if (18 <= i <= 26) else 0.0
                curr_rula = round(min(7.0, max(1.0, ws["base_rula"] + fatigue_factor + random.uniform(-0.4, 0.4))), 1)
                curr_reba = round(min(8.0, max(1.0, ws["base_reba"] + fatigue_factor + random.uniform(-0.3, 0.3))), 1)
                max_rula = min(7, int(round(curr_rula + random.choice([0, 1]))))
                max_reba = min(8, int(round(curr_reba + random.choice([0, 1]))))

                high_risk = ws["high_risk_pct"] + (15.0 if fatigue_factor > 0 else 0.0) + random.uniform(-3, 3)
                high_risk = round(max(0.0, min(100.0, high_risk)), 1)

                breaks_rec = 1 if (i in [8, 16, 24]) else 0
                breaks_ack = 1 if (breaks_rec and random.random() > 0.3) else 0

                # Insert window
                conn.execute(
                    """
                    INSERT OR REPLACE INTO telemetry_windows (
                        window_id, device_id, session_id, window_start, window_end,
                        created_at, breaks_recommended, breaks_acknowledged
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        win_id,
                        ws["id"],
                        session_id,
                        win_time.isoformat(),
                        win_end.isoformat(),
                        win_end.isoformat(),
                        breaks_rec,
                        breaks_ack,
                    ),
                )

                # Posture metrics
                conn.execute(
                    """
                    INSERT OR REPLACE INTO posture_metrics (
                        metric_id, window_id, average_rula, maximum_rula, average_reba, maximum_reba,
                        high_risk_percentage, dominant_posture
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"PM-{win_id}",
                        win_id,
                        curr_rula,
                        max_rula,
                        curr_reba,
                        max_reba,
                        high_risk,
                        ws["dominant"] if random.random() > 0.25 else "NEUTRAL",
                    ),
                )

                # Expression metrics
                conn.execute(
                    """
                    INSERT OR REPLACE INTO expression_metrics (
                        metric_id, window_id, neutral_percentage, positive_percentage,
                        negative_percentage, reduced_expression_percentage
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"EM-{win_id}",
                        win_id,
                        ws["neutral_pct"],
                        ws["positive_pct"],
                        ws["negative_pct"],
                        ws["reduced_pct"],
                    ),
                )

        # Seed realistic alerts in events table
        sample_alerts = [
            (
                "NODE-004",
                "ALERT",
                json.dumps({
                    "condition": "POSTURE",
                    "risk_level": "VERY_HIGH",
                    "rula_score": 6.5,
                    "posture": "SLOUCHING",
                    "message": "Persistent severe slouching detected (>25s). Immediate postural reset advised.",
                }),
                (now - timedelta(minutes=14)).isoformat(),
            ),
            (
                "NODE-002",
                "ALERT",
                json.dumps({
                    "condition": "POSTURE",
                    "risk_level": "HIGH",
                    "rula_score": 5.4,
                    "posture": "TRUNK_FLEXION",
                    "message": "Continuous forward trunk lean (>20s). Adjust monitor height and chair lumbar support.",
                }),
                (now - timedelta(minutes=32)).isoformat(),
            ),
            (
                "NODE-001",
                "ALERT",
                json.dumps({
                    "condition": "BREAK",
                    "risk_level": "MODERATE",
                    "message": "Recommended 3-minute ergonomic stretch break. 90 minutes of continuous screen work.",
                }),
                (now - timedelta(minutes=58)).isoformat(),
            ),
            (
                "NODE-004",
                "ALERT",
                json.dumps({
                    "condition": "FATIGUE",
                    "risk_level": "HIGH",
                    "message": "Reduced facial expressiveness and progressive trunk fatigue detected.",
                }),
                (now - timedelta(hours=1, minutes=20)).isoformat(),
            ),
            (
                "NODE-002",
                "ALERT",
                json.dumps({
                    "condition": "POSTURE",
                    "risk_level": "HIGH",
                    "rula_score": 5.6,
                    "posture": "TRUNK_FLEXION",
                    "message": "Elevated RULA Action Level 3: Further ergonomic investigation required promptly.",
                }),
                (now - timedelta(hours=2, minutes=10)).isoformat(),
            ),
        ]

        for dev_id, ev_type, ev_val, ts in sample_alerts:
            conn.execute(
                """
                INSERT OR IGNORE INTO events (
                    event_id, device_id, session_id, timestamp, event_type, event_value, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ALERT-{uuid.uuid4().hex[:8]}",
                    dev_id,
                    f"SESS-{dev_id}-20261008",
                    ts,
                    ev_type,
                    ev_val,
                    ts,
                ),
            )

    print("[OK] Presentation database seeding successfully completed!")
    print(f"    - Total Nodes: {len(workstations)}")
    print(f"    - Total Windows: {len(workstations) * 32}")
    print(f"    - Total Alerts: {len(sample_alerts)}")

if __name__ == "__main__":
    seed_database()
