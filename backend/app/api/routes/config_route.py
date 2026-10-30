from fastapi import APIRouter
from backend.app.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/public")
async def get_public_config():
    """Returns safe, public configuration parameters required by the frontend client."""
    ai_online = bool(settings.GEMINI_API_KEY and settings.AI_PROVIDER != "offline")
    return {
        "paypal_client_id": settings.PAYPAL_CLIENT_ID,
        "paypal_env": settings.PAYPAL_ENV,
        "ai_online": ai_online,
        "enable_lab": settings.ENABLE_LAB,
        "default_currency": settings.DEFAULT_CURRENCY,
    }
