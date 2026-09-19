"""
EdgeErgo — Central Server Entry Point (PRD §11, §88, §90).

FastAPI application serving the REST API for Edge Nodes and the
admin dashboard. In production, also serves the React dashboard static build.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Union

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from central_server.api.edge import router as edge_router
from central_server.database.database import CentralDatabase

# PRD §90: Configure central logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("central_server")


def create_app(
    db_path: Optional[Union[str, Path]] = None,
    database: Optional[CentralDatabase] = None,
) -> FastAPI:
    """Application factory for Central Server."""

    # 1. Initialize Central Database repository
    if database is not None:
        db = database
    elif db_path is not None:
        db = CentralDatabase(db_path=db_path, auto_init=True)
    else:
        db = CentralDatabase(db_path="central_server.db", auto_init=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup logic
        logger.info("EdgeErgo Central Server starting up. Database initialized.")
        app.state.db = db
        yield
        # Shutdown logic
        logger.info("EdgeErgo Central Server shutting down.")
        db.close()

    app = FastAPI(
        title="EdgeErgo Central Server",
        description="Privacy-Preserving Distributed Edge AI Ergonomic & Expression Monitoring Server",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Attach database to state directly as well (for immediate access in tests)
    app.state.db = db

    # 2. CORS Middleware (PRD §11 for future React Dashboard in Phase 14)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Mount Edge-facing API Router
    app.include_router(edge_router)

    # 4. System Health Check Endpoint
    @app.get(
        "/api/v1/health",
        tags=["System"],
        status_code=status.HTTP_200_OK,
        summary="Server Health",
    )
    def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "server": "EdgeErgo Central Server",
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


# Default module-level application instance for uvicorn
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("central_server.main:app", host="0.0.0.0", port=8000, reload=True)
