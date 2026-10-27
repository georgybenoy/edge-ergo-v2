"""
Utility script to reset ergonomic telemetry data in Central Server and Edge Agent databases.
Preserves device registrations and configurations while clearing telemetry windows, sessions, assessments, and reports.
"""

import argparse
import os
from pathlib import Path
import sqlite3
import sys

def reset_central_db(db_path: Path, reset_devices: bool = False) -> None:
    if not db_path.exists():
        print(f"[-] Central database not found at {db_path} (skipping)")
        return

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM expression_metrics;")
        conn.execute("DELETE FROM posture_metrics;")
        conn.execute("DELETE FROM telemetry_windows;")
        conn.execute("DELETE FROM sessions;")
        conn.execute("DELETE FROM reports;")
        conn.execute("DELETE FROM events;")
        if reset_devices:
            conn.execute("DELETE FROM devices;")
        conn.commit()
        conn.execute("VACUUM;")
        print(f"[+] Successfully cleared telemetry tables in {db_path.name}")
    except Exception as e:
        print(f"[!] Error resetting {db_path.name}: {e}", file=sys.stderr)
        conn.rollback()
    finally:
        conn.close()

def reset_local_db(db_path: Path, reset_device: bool = False) -> None:
    if not db_path.exists():
        print(f"[-] Local database not found at {db_path} (skipping)")
        return

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM assessment;")
        conn.execute("DELETE FROM sync_queue;")
        conn.execute("DELETE FROM session;")
        conn.execute("DELETE FROM events;")
        if reset_device:
            conn.execute("DELETE FROM device;")
        conn.commit()
        conn.execute("VACUUM;")
        print(f"[+] Successfully cleared telemetry and sync queue in {db_path.name}")
    except Exception as e:
        print(f"[!] Error resetting {db_path.name}: {e}", file=sys.stderr)
        conn.rollback()
    finally:
        conn.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="Reset EdgeErgo telemetry data.")
    parser.add_argument("--central-only", action="store_true", help="Only clear central_server.db")
    parser.add_argument("--local-only", action="store_true", help="Only clear edgeergo_local.db")
    parser.add_argument("--reset-devices", action="store_true", help="Also clear registered devices and pairings")
    args = parser.parse_args()

    central_db = Path("central_server.db")
    local_db = Path("edgeergo_local.db")

    if not args.local_only:
        reset_central_db(central_db, reset_devices=args.reset_devices)
    if not args.central_only:
        reset_local_db(local_db, reset_device=args.reset_devices)

    print("\n[Done] Telemetry reset complete. Refresh your dashboard to see 0 windows.")

if __name__ == "__main__":
    main()
