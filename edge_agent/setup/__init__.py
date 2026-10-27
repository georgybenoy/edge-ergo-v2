"""
EdgeErgo — Interactive Workstation Setup & Connectivity Verification Package.
"""

from edge_agent.setup.interactive import (
    check_server_health,
    get_default_workstation_name,
    normalize_server_url,
    run_interactive_setup,
)

__all__ = [
    "check_server_health",
    "get_default_workstation_name",
    "normalize_server_url",
    "run_interactive_setup",
]
