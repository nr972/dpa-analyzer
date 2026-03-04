"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dpa_app.api.routes import analyses as analyses_router
from dpa_app.api.routes import matrices as matrices_router
from dpa_app.config import settings
from dpa_app.database import Base, SessionLocal, engine
from dpa_app.services.seed import seed_matrices


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Ensure data directories exist
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.matrices_dir.mkdir(parents=True, exist_ok=True)

    # Seed preset requirements matrices
    db = SessionLocal()
    try:
        seed_matrices(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(matrices_router.router, prefix="/api/matrices", tags=["matrices"])
app.include_router(analyses_router.router, prefix="/api/analyses", tags=["analyses"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/shutdown")
def shutdown() -> dict[str, str]:
    """Initiate graceful shutdown of the application."""
    import os
    import signal
    import threading

    def _shutdown() -> None:
        os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)

    threading.Timer(1.5, _shutdown).start()
    return {"status": "shutting_down"}
