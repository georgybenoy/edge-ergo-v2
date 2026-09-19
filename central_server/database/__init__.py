"""
EdgeErgo — Central Server Database Package (PRD §48).
"""

from central_server.database.database import CENTRAL_SCHEMA_SQL, CentralDatabase

__all__ = ["CentralDatabase", "CENTRAL_SCHEMA_SQL"]
