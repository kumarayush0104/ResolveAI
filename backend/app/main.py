import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings, PROJECT_ROOT
from backend.app.db.session import init_db_sync
from backend.app.db.seed import seed_users_sync
from backend.app.services.reconciliation import reconciler_background_loop
from backend.app.healthz import router as health_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.orders import router as orders_router
from backend.app.api.routes.cases import router as cases_router
from backend.app.api.routes.webhooks import router as webhooks_router
from backend.app.api.routes.transactions import router as transactions_router
from backend.app.api.routes.metrics import router as metrics_router
from backend.app.api.routes.lab import router as lab_router
from backend.app.api.routes.stream import router as stream_router
from backend.app.api.routes.config_route import router as config_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB tables
    init_db_sync()

    # 2. Seed demo users
    seed_users_sync()

    # 3. Start background reconciler loop
    reconciler_task = asyncio.create_task(reconciler_background_loop(interval_seconds=30))

    yield

    # Teardown
    reconciler_task.cancel()
    try:
        await reconciler_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="ResolveAI API",
        description="Autonomous PayPal dispute, chargeback, and stuck-payment resolution engine.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration (allow all origins in sandbox demo mode)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers with /api prefix
    app.include_router(auth_router, prefix="/api")
    app.include_router(orders_router, prefix="/api")
    app.include_router(cases_router, prefix="/api")
    app.include_router(stream_router, prefix="/api")
    app.include_router(webhooks_router, prefix="/api")
    app.include_router(transactions_router, prefix="/api")
    app.include_router(metrics_router, prefix="/api")
    app.include_router(lab_router, prefix="/api")
    app.include_router(config_router, prefix="/api")

    # Mount health probe at root
    app.include_router(health_router)

    # Serve static frontend in production if built
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    if frontend_dist.exists() and frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
