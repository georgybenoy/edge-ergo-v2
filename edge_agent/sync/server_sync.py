"""
Server synchronisation client.

Drains the local sync_queue and POSTs anonymized telemetry-window
JSON summaries to the Central Server.  Falls back gracefully when
the server is unreachable — summaries stay queued and are retried
with exponential backoff.

Privacy invariant: only the telemetry window JSON shape is ever
transmitted; never raw frames, face crops, or landmark images.
"""

# TODO: Phase 9 — implement ServerSync class
