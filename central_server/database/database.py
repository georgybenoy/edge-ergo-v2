"""
Central SQLite database.

Stores anonymized telemetry-window summaries, device registrations,
and aggregated reports.  Contains ONLY summary data — never raw
frames, face crops, or landmark images.

Design note: uses raw sqlite3 (stdlib) to keep the dependency
footprint minimal and the SQL explicit.  The schema is kept
Postgres-compatible for a future migration path.
"""

# TODO: Phase 10 — implement CentralDatabase class
