from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.security.auth import demo_login, get_current_user
from backend.app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class DemoLoginRequest(BaseModel):
    role: str = Field(..., description="Role to assume: 'buyer', 'seller', or 'admin'")


@router.post("/demo-login")
async def login_demo(
    payload: DemoLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Generate authenticated session and JWT bearer token for demo users."""
    role = payload.role.lower().strip()
    if role not in ("buyer", "seller", "admin"):
        raise HTTPException(
            status_code=400,
            detail="Invalid role. Must be 'buyer', 'seller', or 'admin'.",
        )
    return await demo_login(role, session)


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "display_name": current_user.display_name,
    }
