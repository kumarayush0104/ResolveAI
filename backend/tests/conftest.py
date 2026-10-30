import os
import tempfile
import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Ensure environment variables for tests
os.environ["PAYPAL_ENV"] = "sandbox"
os.environ["PAYPAL_CLIENT_ID"] = os.environ.get("PAYPAL_CLIENT_ID", "mock_client_id")
os.environ["PAYPAL_CLIENT_SECRET"] = os.environ.get("PAYPAL_CLIENT_SECRET", "mock_client_secret")
os.environ["PAYPAL_WEBHOOK_ID"] = os.environ.get("PAYPAL_WEBHOOK_ID", "mock_webhook_id")
os.environ["JWT_SECRET"] = "test-jwt-secret-key-at-least-32-characters"
os.environ["ENABLE_LAB"] = "true"
os.environ["AI_PROVIDER"] = "offline"

from backend.app.config import settings
from backend.app.db.models import Base, User, Order, Case, PaymentAttempt, CaseEvent
from backend.app.db.session import get_db
from backend.app.db.seed import DEMO_USERS
from backend.app.security.auth import create_access_token
from backend.app.main import app


# Test database setup with SQLite in-memory StaticPool
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_async_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Create fresh tables for every test function and seed demo users."""
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        for u in DEMO_USERS:
            user = User(
                id=u["id"],
                email=u["email"],
                role=u["role"],
                display_name=u["display_name"],
                is_active=True,
            )
            session.add(user)
        await session.commit()

    yield

    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Async DB session fixture for direct database interaction in tests."""
    async with TestAsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client():
    """Async test HTTP client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def auth_tokens():
    """Generate JWT auth headers for all 3 demo roles."""
    buyer_token = create_access_token({"sub": DEMO_USERS[0]["id"], "email": DEMO_USERS[0]["email"], "role": "buyer"})
    seller_token = create_access_token({"sub": DEMO_USERS[1]["id"], "email": DEMO_USERS[1]["email"], "role": "seller"})
    admin_token = create_access_token({"sub": DEMO_USERS[2]["id"], "email": DEMO_USERS[2]["email"], "role": "admin"})

    return {
        "buyer": {"Authorization": f"Bearer {buyer_token}"},
        "seller": {"Authorization": f"Bearer {seller_token}"},
        "admin": {"Authorization": f"Bearer {admin_token}"},
    }


@pytest_asyncio.fixture
async def client(async_client):
    """Alias for async_client."""
    return async_client


@pytest.fixture
def buyer_headers(auth_tokens):
    """Direct fixture for buyer headers."""
    return auth_tokens["buyer"]
