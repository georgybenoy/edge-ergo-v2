"""
EdgeErgo — Edge Agent Entry Point

Orchestrates camera capture, vision analysis, ergonomic scoring,
expression classification, local storage, server sync, and the
desktop overlay feedback loop.

Privacy invariant: raw video frames and face crops NEVER leave this
process's memory.  Only anonymized JSON telemetry summaries are
persisted or transmitted.
"""

# TODO: Phase 2+ — wire up the main event loop


def main() -> None:
    """Launch the Edge Agent."""
    raise NotImplementedError("Edge Agent main loop — implemented in Phase 2+")


if __name__ == "__main__":
    main()
