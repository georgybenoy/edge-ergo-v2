"""
Central SQLite Database & Repository Layer (PRD §11, §13, §48).

Stores anonymized telemetry-window summaries, device registrations,
and aggregated reports. Contains ONLY summary data — never raw frames,
face crops, or landmark images.

Design notes:
  - Uses raw sqlite3 (stdlib) to keep dependency footprint minimal and SQL explicit.
  - Abstracted repository pattern so that swapping SQLite for PostgreSQL later
    does not require rewriting callers (PRD §13 modularity).
  - ACID transactions with automatic rollback on any failure.
  - WAL journal mode enabled for concurrency.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Generator, Optional, Sequence, Tuple, Union
import uuid

logger = logging.getLogger(__name__)


# ── SQL Schema Definitions ───────────────────────────────────────────────────

CENTRAL_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    software_version TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    last_seen TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    camera_detected INTEGER NOT NULL DEFAULT 1,
    camera_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS telemetry_windows (
    window_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    created_at TEXT NOT NULL,
    breaks_recommended INTEGER NOT NULL DEFAULT 0,
    breaks_acknowledged INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE(device_id, session_id, window_start)
);

CREATE TABLE IF NOT EXISTS posture_metrics (
    metric_id TEXT PRIMARY KEY,
    window_id TEXT NOT NULL,
    average_rula REAL NOT NULL,
    maximum_rula INTEGER NOT NULL,
    average_reba REAL NOT NULL,
    maximum_reba INTEGER NOT NULL,
    high_risk_percentage REAL NOT NULL,
    dominant_posture TEXT NOT NULL,
    FOREIGN KEY (window_id) REFERENCES telemetry_windows(window_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS expression_metrics (
    metric_id TEXT PRIMARY KEY,
    window_id TEXT NOT NULL,
    neutral_percentage REAL NOT NULL,
    positive_percentage REAL NOT NULL,
    negative_percentage REAL NOT NULL,
    reduced_expression_percentage REAL NOT NULL,
    FOREIGN KEY (window_id) REFERENCES telemetry_windows(window_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    session_id TEXT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    data_json TEXT NOT NULL
);

-- Indices for rapid query performance on dashboard endpoints
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);
CREATE INDEX IF NOT EXISTS idx_sessions_device ON sessions(device_id, start_time);
CREATE INDEX IF NOT EXISTS idx_windows_device ON telemetry_windows(device_id, window_start);
CREATE INDEX IF NOT EXISTS idx_windows_session ON telemetry_windows(session_id);
CREATE INDEX IF NOT EXISTS idx_posture_window ON posture_metrics(window_id);
CREATE INDEX IF NOT EXISTS idx_expression_window ON expression_metrics(window_id);
CREATE INDEX IF NOT EXISTS idx_events_device ON events(device_id, timestamp);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── CentralDatabase Repository ────────────────────────────────────────────────

class CentralDatabase:
    """Central repository managing Edge Node data persistence and querying."""

    def __init__(
        self,
        db_path: Union[str, Path] = "central_server.db",
        auto_init: bool = True,
    ) -> None:
        self.db_path = Path(db_path) if isinstance(db_path, str) and db_path != ":memory:" else db_path
        self._is_memory = str(self.db_path) == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self._is_memory:
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        elif isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if auto_init:
            self.init_db()

    def _get_raw_connection(self) -> sqlite3.Connection:
        if self._is_memory:
            assert self._mem_conn is not None
            return self._mem_conn

        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a connection with transaction management (auto commit / rollback)."""
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if not self._is_memory:
                conn.close()

    def init_db(self) -> None:
        """Create schema tables and indices if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript(CENTRAL_SCHEMA_SQL)
        logger.debug("Initialized CentralDatabase schema at %s", self.db_path)

    def close(self) -> None:
        if self._mem_conn:
            try:
                self._mem_conn.close()
            except Exception:
                pass
            self._mem_conn = None

    # ── Device Operations (PRD §42, §46) ──────────────────────────────────────

    def get_next_node_id(self) -> str:
        """Generate next sequential node identifier: NODE-001, NODE-002, etc."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT device_id FROM devices WHERE device_id LIKE 'NODE-%'")
            rows = cursor.fetchall()

        max_num = 0
        for r in rows:
            did = r["device_id"]
            try:
                num = int(did.split("-")[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                continue

        return f"NODE-{max_num + 1:03d}"

    def register_device(
        self,
        device_name: str,
        software_version: str,
        camera_detected: bool = True,
        camera_index: int = 0,
        assigned_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register a new device or re-register an existing device."""
        now_ts = _now_iso()
        with self.get_connection() as conn:
            # Check if device with this name already exists
            existing = conn.execute(
                "SELECT * FROM devices WHERE device_name = ?", (device_name,)
            ).fetchone()
            if existing:
                device_id = existing["device_id"]
                conn.execute(
                    """
                    UPDATE devices SET
                        software_version = ?,
                        last_seen = ?,
                        status = 'active',
                        camera_detected = ?,
                        camera_index = ?
                    WHERE device_id = ?
                    """,
                    (software_version, now_ts, 1 if camera_detected else 0, camera_index, device_id),
                )
            else:
                device_id = assigned_id or self.get_next_node_id()
                conn.execute(
                    """
                    INSERT INTO devices (
                        device_id, device_name, software_version, registered_at,
                        last_seen, status, camera_detected, camera_index
                    ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        device_id,
                        device_name,
                        software_version,
                        now_ts,
                        now_ts,
                        1 if camera_detected else 0,
                        camera_index,
                    ),
                )

        return self.get_device(device_id) or {
            "device_id": device_id,
            "device_name": device_name,
            "software_version": software_version,
            "registered_at": now_ts,
            "status": "active",
        }

    def get_device(self, device_id: str) -> Optional[dict[str, Any]]:
        """Retrieve device record by device_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            return dict(row) if row else None

    def list_devices(self) -> list[dict[str, Any]]:
        """List all registered devices."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM devices ORDER BY registered_at ASC")
            return [dict(r) for r in cursor.fetchall()]

    def update_heartbeat(
        self,
        device_id: str,
        software_version: str,
        status: str = "active",
        heartbeat_time: Optional[str] = None,
    ) -> bool:
        """Update last_seen timestamp and status for a device."""
        now_ts = heartbeat_time or _now_iso()
        with self.get_connection() as conn:
            res = conn.execute(
                """
                UPDATE devices SET
                    last_seen = ?,
                    status = ?,
                    software_version = ?
                WHERE device_id = ?
                """,
                (now_ts, status, software_version, device_id),
            )
            return res.rowcount > 0

    # ── Telemetry Window Operations (PRD §40, §48, §89) ──────────────────────

    def is_duplicate_window(self, device_id: str, session_id: str, window_start: str) -> bool:
        """Check if this telemetry window has already been persisted."""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM telemetry_windows
                WHERE device_id = ? AND session_id = ? AND window_start = ?
                """,
                (device_id, session_id, window_start),
            ).fetchone()
            return row is not None

    def save_telemetry_window(self, payload: dict[str, Any]) -> Tuple[bool, str]:
        """Atomically persist a verified telemetry window payload.

        Returns:
            (is_new: bool, window_id: str)
            If window already exists, returns (False, window_id).
        """
        device_id = payload["device_id"]
        session_id = payload["session_id"]
        window_start = payload["window_start"]
        window_end = payload["window_end"]

        # Check duplicate
        if self.is_duplicate_window(device_id, session_id, window_start):
            # Compute existing window_id
            existing = self.get_window_by_start(device_id, session_id, window_start)
            wid = existing["window_id"] if existing else f"{session_id}_{window_start}"
            logger.info("Ignoring duplicate telemetry window: device=%s session=%s start=%s", device_id, session_id, window_start)
            return False, wid

        window_id = payload.get("window_id") or f"{session_id}_{window_start}"
        now_ts = _now_iso()

        ergo = payload.get("ergonomics", {})
        expr = payload.get("facial_expression", {})
        brk = payload.get("breaks", {})

        with self.get_connection() as conn:
            # 1. Ensure device exists (auto-register if absent for robust testing/integration)
            conn.execute(
                """
                INSERT OR IGNORE INTO devices (device_id, device_name, software_version, registered_at, last_seen)
                VALUES (?, ?, '0.1.0', ?, ?)
                """,
                (device_id, f"Auto-{device_id}", now_ts, now_ts),
            )

            # 2. Ensure session exists
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, device_id, start_time, end_time, duration, created_at)
                VALUES (?, ?, ?, ?, 300.0, ?)
                """,
                (session_id, device_id, window_start, window_end, now_ts),
            )

            # 3. Insert telemetry_windows
            conn.execute(
                """
                INSERT INTO telemetry_windows (
                    window_id, device_id, session_id, window_start, window_end,
                    created_at, breaks_recommended, breaks_acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    window_id,
                    device_id,
                    session_id,
                    window_start,
                    window_end,
                    now_ts,
                    int(brk.get("breaks_recommended", 0)),
                    int(brk.get("breaks_acknowledged", 0)),
                ),
            )

            # 4. Insert posture_metrics
            metric_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO posture_metrics (
                    metric_id, window_id, average_rula, maximum_rula,
                    average_reba, maximum_reba, high_risk_percentage, dominant_posture
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric_id,
                    window_id,
                    float(ergo.get("average_rula", 1.0)),
                    int(ergo.get("maximum_rula", 1)),
                    float(ergo.get("average_reba", 1.0)),
                    int(ergo.get("maximum_reba", 1)),
                    float(ergo.get("high_risk_percentage", 0.0)),
                    str(ergo.get("dominant_posture", "NEUTRAL")),
                ),
            )

            # 5. Insert expression_metrics
            expr_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO expression_metrics (
                    metric_id, window_id, neutral_percentage, positive_percentage,
                    negative_percentage, reduced_expression_percentage
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    expr_id,
                    window_id,
                    float(expr.get("neutral_percentage", 100.0)),
                    float(expr.get("positive_percentage", 0.0)),
                    float(expr.get("negative_percentage", 0.0)),
                    float(expr.get("reduced_expression_percentage", 0.0)),
                ),
            )

            # 6. Update device last_seen
            conn.execute("UPDATE devices SET last_seen = ? WHERE device_id = ?", (now_ts, device_id))

        logger.info("Persisted telemetry window %s for device %s", window_id, device_id)
        return True, window_id

    def get_window_by_start(self, device_id: str, session_id: str, window_start: str) -> Optional[dict[str, Any]]:
        """Find telemetry window by composite start key."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM telemetry_windows WHERE device_id = ? AND session_id = ? AND window_start = ?",
                (device_id, session_id, window_start),
            ).fetchone()
            return dict(row) if row else None

    def get_telemetry_window(self, window_id: str) -> Optional[dict[str, Any]]:
        """Retrieve full details of a single telemetry window with posture and expression metrics."""
        with self.get_connection() as conn:
            w_row = conn.execute(
                "SELECT * FROM telemetry_windows WHERE window_id = ?", (window_id,)
            ).fetchone()
            if not w_row:
                return None

            data = dict(w_row)
            p_row = conn.execute(
                "SELECT * FROM posture_metrics WHERE window_id = ?", (window_id,)
            ).fetchone()
            e_row = conn.execute(
                "SELECT * FROM expression_metrics WHERE window_id = ?", (window_id,)
            ).fetchone()

            data["posture"] = dict(p_row) if p_row else None
            data["expression"] = dict(e_row) if e_row else None
            return data

    def list_telemetry_windows(
        self, device_id: Optional[str] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List telemetry windows optionally filtered by device."""
        with self.get_connection() as conn:
            if device_id:
                cursor = conn.execute(
                    """
                    SELECT w.*, p.average_rula, p.maximum_rula, p.average_reba, p.maximum_reba,
                           p.high_risk_percentage, p.dominant_posture
                    FROM telemetry_windows w
                    LEFT JOIN posture_metrics p ON w.window_id = p.window_id
                    WHERE w.device_id = ?
                    ORDER BY w.window_start DESC
                    LIMIT ?
                    """,
                    (device_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT w.*, p.average_rula, p.maximum_rula, p.average_reba, p.maximum_reba,
                           p.high_risk_percentage, p.dominant_posture
                    FROM telemetry_windows w
                    LEFT JOIN posture_metrics p ON w.window_id = p.window_id
                    ORDER BY w.window_start DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            return [dict(r) for r in cursor.fetchall()]
