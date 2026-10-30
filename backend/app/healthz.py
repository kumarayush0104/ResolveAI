from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check():
    """Liveness check for deployment health probes."""
    return {"status": "ok", "version": "1.0.0"}
