"""API-level auth tests using an in-memory SQLite database.

Only the users table is created; endpoints touching pgvector tables are
exercised in CI against a real PostgreSQL service instead."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.session import get_db
from app.main import app
from app.models.user import User


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: User.__table__.create(sync_conn))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_register_login_me_flow(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ops@example.com", "password": "sup3r-secret", "full_name": "Ops Person"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == "ops@example.com"
    assert body["user"]["is_admin"] is True  # first user

    # Duplicate registration rejected
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ops@example.com", "password": "sup3r-secret"},
    )
    assert resp.status_code == 409

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ops@example.com", "password": "sup3r-secret"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "ops@example.com"


async def test_wrong_password_rejected(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "a@b.co", "password": "password-123"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "a@b.co", "password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bogus"})
    assert resp.status_code == 401
