"""
Local SQLite database for the Edge Agent (PRD §37, §38, §39).

Stores assessment results, events, sessions, and the sync queue.
Raw video frames, face crops, or landmark images are NEVER stored.

Schema requirements:
  device(device_id, device_name, software_version, registered_at, last_sync)
  session(session_id, device_id, start_time, end_time, duration)
  assessment(assessment_id, session_id, timestamp, rula_score, reba_score, risk_level,
    dominant_posture, expression_category)
  events(event_id, session_id, timestamp, event_type, event_value)
  sync_queue(sync_id, record_id, created_at, status, retry_count, last_attempt)
  configuration(key, value, updated_at)
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Generator, Optional, Sequence, Union
import uuid

logger = logging.getLogger(__name__)


# ── SQL Schema Definitions ───────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS device (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    software_version TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    last_sync TEXT
);

CREATE TABLE IF NOT EXISTS session (
    session_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration REAL NOT NULL,
    FOREIGN KEY (device_id) REFERENCES device(device_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assessment (
    assessment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    rula_score INTEGER NOT NULL,
    reba_score INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    dominant_posture TEXT NOT NULL,
    expression_category TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_value TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session(session_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sync_queue (
    sync_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_attempt TEXT
);

CREATE TABLE IF NOT EXISTS configuration (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_session_start ON session(start_time);
CREATE INDEX IF NOT EXISTS idx_assessment_session ON assessment(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status, created_at);
"""


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class LocalDatabase:
    """Local SQLite database manager for the Edge Agent.

    Guarantees:
      1. Parameterized queries throughout (SQL injection immune).
      2. Multi-table operations wrapped in ACID transactions with automatic rollback.
      3. WAL journal mode enabled for durability and concurrent reads.
      4. Complete offline operation — writes buffer in sync_queue when network is down.
      5. Zero storage of raw frames, crops, or landmarks.
    """

    def __init__(
        self,
        db_path: Union[str, Path] = "edgeergo_local.db",
        auto_init: bool = True,
    ) -> None:
        self.db_path = Path(db_path) if isinstance(db_path, str) and db_path != ":memory:" else db_path
        self._is_memory = str(self.db_path) == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self._is_memory:
            # Persistent connection for in-memory SQLite so tables persist across method calls
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        elif isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if auto_init:
            self.init_db()

    def _get_raw_connection(self) -> sqlite3.Connection:
        """Obtain a SQLite connection configured with proper pragmas."""
        if self._is_memory:
            assert self._mem_conn is not None
            return self._mem_conn

        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a connection with transaction management.

        Commits automatically on normal exit, rolls back on any exception.
        """
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
        """Create all tables and indexes if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.debug("Initialized EdgeErgo local SQLite database schema at %s", self.db_path)

    def close(self) -> None:
        """Close any open persistent in-memory connection."""
        if self._mem_conn:
            try:
                self._mem_conn.close()
            except Exception:
                pass
            self._mem_conn = None

    # ── Device Helpers ────────────────────────────────────────────────────────

    def register_device(
        self,
        device_id: str,
        device_name: str = "EdgeWorkstation",
        software_version: str = "0.1.0",
        registered_at: Optional[str] = None,
        last_sync: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register or update the local edge agent device record."""
        reg_time = registered_at or _now_iso()
        query = """
            INSERT INTO device (device_id, device_name, software_version, registered_at, last_sync)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                device_name = excluded.device_name,
                software_version = excluded.software_version,
                last_sync = COALESCE(excluded.last_sync, device.last_sync)
        """
        with self.get_connection() as conn:
            conn.execute(query, (device_id, device_name, software_version, reg_time, last_sync))

        return {
            "device_id": device_id,
            "device_name": device_name,
            "software_version": software_version,
            "registered_at": reg_time,
            "last_sync": last_sync,
        }

    def get_device(self, device_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Retrieve device registration information."""
        with self.get_connection() as conn:
            if device_id:
                row = conn.execute("SELECT * FROM device WHERE device_id = ?", (device_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM device ORDER BY registered_at DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def update_device_sync(self, device_id: str, sync_time: Optional[str] = None) -> None:
        """Update the last_sync timestamp for a registered device."""
        st = sync_time or _now_iso()
        with self.get_connection() as conn:
            conn.execute("UPDATE device SET last_sync = ? WHERE device_id = ?", (st, device_id))

    # ── Session & Assessment Storage ──────────────────────────────────────────

    def record_session(
        self,
        session_id: str,
        device_id: str,
        start_time: str,
        end_time: str,
        duration: float,
    ) -> None:
        """Insert a single session record."""
        query = """
            INSERT INTO session (session_id, device_id, start_time, end_time, duration)
            VALUES (?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            conn.execute(query, (session_id, device_id, start_time, end_time, duration))

    def record_assessment(
        self,
        assessment_id: str,
        session_id: str,
        timestamp: str,
        rula_score: int,
        reba_score: int,
        risk_level: str,
        dominant_posture: str,
        expression_category: str,
    ) -> None:
        """Insert an assessment record."""
        query = """
            INSERT INTO assessment (
                assessment_id, session_id, timestamp, rula_score, reba_score,
                risk_level, dominant_posture, expression_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            conn.execute(
                query,
                (
                    assessment_id,
                    session_id,
                    timestamp,
                    rula_score,
                    reba_score,
                    risk_level,
                    dominant_posture,
                    expression_category,
                ),
            )

    def record_event(
        self,
        event_id: str,
        session_id: Optional[str],
        timestamp: str,
        event_type: str,
        event_value: str,
    ) -> None:
        """Insert a system or ergonomic event log."""
        query = """
            INSERT INTO events (event_id, session_id, timestamp, event_type, event_value)
            VALUES (?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            conn.execute(query, (event_id, session_id, timestamp, event_type, event_value))

    def enqueue_sync(
        self,
        record_id: str,
        sync_id: Optional[str] = None,
        created_at: Optional[str] = None,
        status: str = "PENDING",
    ) -> str:
        """Add an entry to the sync_queue for eventual transmission to Central Server."""
        s_id = sync_id or str(uuid.uuid4())
        c_at = created_at or _now_iso()
        query = """
            INSERT INTO sync_queue (sync_id, record_id, created_at, status, retry_count, last_attempt)
            VALUES (?, ?, ?, ?, 0, NULL)
        """
        with self.get_connection() as conn:
            conn.execute(query, (s_id, record_id, c_at, status))
        return s_id

    # ── High-Level Atomic Write Path (Temporal Engine Integration) ───────────

    def save_session_analysis(
        self,
        device_id: str,
        session_stats: Any,  # SessionStats from edge_agent.temporal.analyzer
        expression_category: str = "Neutral",
        session_events: Optional[Sequence[dict[str, Any]]] = None,
    ) -> str:
        """Persist a completed monitoring session atomically (PRD §37, §38, §39).

        In a single ACID transaction:
          1. Ensures device exists (auto-registers default if absent).
          2. Inserts session row from session_stats.
          3. Inserts summary assessment row with aggregated scores and dominant posture.
          4. Inserts all alert events and custom events into events table.
          5. Enqueues a sync record in sync_queue.

        If any error occurs mid-write, the entire transaction is rolled back,
        preventing any corrupted or partial local state.

        Returns:
            The generated sync_id for the sync_queue entry.
        """
        session_id = str(getattr(session_stats, "session_id", uuid.uuid4()))
        start_time_iso = (
            datetime.fromtimestamp(session_stats.start_time, timezone.utc).isoformat()
            if isinstance(session_stats.start_time, (int, float))
            else str(session_stats.start_time)
        )
        end_time_iso = (
            datetime.fromtimestamp(session_stats.end_time, timezone.utc).isoformat()
            if isinstance(session_stats.end_time, (int, float))
            else str(session_stats.end_time)
        )
        duration = float(getattr(session_stats, "duration_sec", 0.0))

        # Risk level assessment determination
        avg_rula = float(getattr(session_stats, "avg_rula", 1.0))
        avg_reba = float(getattr(session_stats, "avg_reba", 1.0))
        dominant_posture = str(getattr(session_stats, "dominant_posture", "NEUTRAL"))

        # Map average score to RiskLevel category
        max_score = max(avg_rula, avg_reba)
        if max_score >= 8:
            risk_level = "VERY_HIGH"
        elif max_score >= 5:
            risk_level = "HIGH"
        elif max_score >= 3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        assessment_id = str(uuid.uuid4())
        sync_id = str(uuid.uuid4())
        now_ts = _now_iso()

        with self.get_connection() as conn:
            # 1. Device check / auto-upsert
            conn.execute(
                """
                INSERT OR IGNORE INTO device (device_id, device_name, software_version, registered_at, last_sync)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (device_id, f"Workstation-{device_id[:6]}", "0.1.0", now_ts),
            )

            # 2. Insert session
            conn.execute(
                """
                INSERT INTO session (session_id, device_id, start_time, end_time, duration)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, device_id, start_time_iso, end_time_iso, duration),
            )

            # 3. Insert summary assessment
            conn.execute(
                """
                INSERT INTO assessment (
                    assessment_id, session_id, timestamp, rula_score, reba_score,
                    risk_level, dominant_posture, expression_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    session_id,
                    end_time_iso,
                    round(avg_rula),
                    round(avg_reba),
                    risk_level,
                    dominant_posture,
                    expression_category,
                ),
            )

            # 4. Insert alert events
            alerts = getattr(session_stats, "alerts_triggered", [])
            for alert in alerts:
                event_id = str(uuid.uuid4())
                alert_ts = (
                    datetime.fromtimestamp(alert.timestamp, timezone.utc).isoformat()
                    if isinstance(alert.timestamp, (int, float))
                    else str(alert.timestamp)
                )
                event_val = json.dumps(
                    {
                        "condition": getattr(alert, "condition", "UNKNOWN"),
                        "risk_level": getattr(alert, "risk_level", "HIGH"),
                        "rula_score": getattr(alert, "rula_score", 0),
                        "reba_score": getattr(alert, "reba_score", 0),
                        "duration_sec": getattr(alert, "duration_sec", 0.0),
                        "message": getattr(alert, "message", ""),
                    }
                )
                conn.execute(
                    """
                    INSERT INTO events (event_id, session_id, timestamp, event_type, event_value)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (event_id, session_id, alert_ts, "ALERT", event_val),
                )

            # Insert optional custom events
            if session_events:
                for evt in session_events:
                    conn.execute(
                        """
                        INSERT INTO events (event_id, session_id, timestamp, event_type, event_value)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            evt.get("event_id", str(uuid.uuid4())),
                            session_id,
                            evt.get("timestamp", now_ts),
                            evt.get("event_type", "CUSTOM"),
                            evt.get("event_value", ""),
                        ),
                    )

            # 5. Enqueue sync_queue record
            conn.execute(
                """
                INSERT INTO sync_queue (sync_id, record_id, created_at, status, retry_count, last_attempt)
                VALUES (?, ?, ?, 'PENDING', 0, NULL)
                """,
                (sync_id, session_id, now_ts),
            )

        logger.info("Persisted session %s and enqueued sync item %s", session_id, sync_id)
        return sync_id

    # ── Read & Query Helpers ──────────────────────────────────────────────────

    def get_latest_assessment(self, session_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Retrieve the latest assessment record (used by overlay & status indicators)."""
        with self.get_connection() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT * FROM assessment WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM assessment ORDER BY timestamp DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a specific session by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM session WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def get_session_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve recent session history for local review/debugging."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT s.session_id, s.device_id, s.start_time, s.end_time, s.duration,
                       a.rula_score, a.reba_score, a.risk_level, a.dominant_posture, a.expression_category,
                       (SELECT COUNT(*) FROM events e WHERE e.session_id = s.session_id) as event_count
                FROM session s
                LEFT JOIN assessment a ON s.session_id = a.session_id
                ORDER BY s.start_time DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_events_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all events recorded during a given session."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_sync_records(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve pending sync queue entries (used by Phase 10 Server Sync)."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sync_queue
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_sync_status(
        self,
        sync_id: str,
        status: str,
        retry_increment: bool = False,
        last_attempt: Optional[str] = None,
    ) -> None:
        """Update the status of a sync_queue record."""
        attempt_time = last_attempt or _now_iso()
        with self.get_connection() as conn:
            if retry_increment:
                conn.execute(
                    """
                    UPDATE sync_queue
                    SET status = ?, retry_count = retry_count + 1, last_attempt = ?
                    WHERE sync_id = ?
                    """,
                    (status, attempt_time, sync_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE sync_queue
                    SET status = ?, last_attempt = ?
                    WHERE sync_id = ?
                    """,
                    (status, attempt_time, sync_id),
                )

    def get_sync_status_summary(self) -> dict[str, int]:
        """Return counts of sync records by status (PENDING, SYNCED, FAILED).

        Directly feeds the desktop overlay's sync badge (Synced vs Pending N).
        """
        summary = {"PENDING": 0, "IN_PROGRESS": 0, "SYNCED": 0, "FAILED": 0, "TOTAL": 0}
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT status, COUNT(*) as count FROM sync_queue GROUP BY status")
            for row in cursor.fetchall():
                st = row["status"]
                cnt = row["count"]
                if st in summary:
                    summary[st] = cnt
                summary["TOTAL"] += cnt
        return summary

    # ── Configuration Store ───────────────────────────────────────────────────

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value in local storage."""
        val_str = json.dumps(value)
        now_ts = _now_iso()
        query = """
            INSERT INTO configuration (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """
        with self.get_connection() as conn:
            conn.execute(query, (key, val_str, now_ts))

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from local storage."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT value FROM configuration WHERE key = ?", (key,)).fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
            return default

    def get_all_config(self) -> dict[str, Any]:
        """Return all configuration key/value pairs."""
        configs = {}
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM configuration")
            for row in cursor.fetchall():
                try:
                    configs[row["key"]] = json.loads(row["value"])
                except Exception:
                    configs[row["key"]] = row["value"]
        return configs
