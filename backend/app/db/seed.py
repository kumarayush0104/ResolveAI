from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from backend.app.config import settings
from backend.app.db.models import User

DEMO_USERS = [
    {
        "id": "11111111-1111-4111-8111-111111111111",
        "email": "buyer@demo.com",
        "role": "buyer",
        "display_name": "Demo Buyer",
        "is_active": True,
    },
    {
        "id": "22222222-2222-4222-8222-222222222222",
        "email": "seller@demo.com",
        "role": "seller",
        "display_name": "Demo Seller",
        "is_active": True,
    },
    {
        "id": "33333333-3333-4333-8333-333333333333",
        "email": "admin@demo.com",
        "role": "admin",
        "display_name": "Merchant Admin",
        "is_active": True,
    },
]


async def seed_users(session: AsyncSession) -> None:
    """Seed demo users into database if they do not exist."""
    for u_data in DEMO_USERS:
        result = await session.execute(select(User).where(User.email == u_data["email"]))
        existing = result.scalar_one_or_none()
        if not existing:
            user = User(
                id=u_data["id"],
                email=u_data["email"],
                role=u_data["role"],
                display_name=u_data["display_name"],
                is_active=u_data["is_active"],
            )
            session.add(user)
    await session.commit()


def seed_users_sync() -> None:
    """Synchronous seed helper for initial setup or testing."""
    sync_url = settings.DATABASE_URL
    if sync_url.startswith("sqlite+aiosqlite://"):
        sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
    sync_connect_args = {}
    if "sqlite" in sync_url:
        sync_connect_args["check_same_thread"] = False

    engine = create_engine(sync_url, connect_args=sync_connect_args)
    with Session(engine) as session:
        for u_data in DEMO_USERS:
            existing = session.query(User).filter_by(email=u_data["email"]).first()
            if not existing:
                user = User(
                    id=u_data["id"],
                    email=u_data["email"],
                    role=u_data["role"],
                    display_name=u_data["display_name"],
                    is_active=u_data["is_active"],
                )
                session.add(user)
        session.commit()


if __name__ == "__main__":
    from backend.app.db.session import init_db_sync
    init_db_sync()
    seed_users_sync()
    print("Seed complete.")
