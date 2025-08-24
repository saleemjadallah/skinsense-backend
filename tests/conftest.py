import pytest
import asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.database import db
from app.config import settings

# Test database URL
TEST_DB_URL = "mongodb://localhost:27017/skinsense_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def test_db():
    """Create test database connection"""
    # Connect to test database
    test_client = AsyncIOMotorClient(TEST_DB_URL)
    test_database = test_client.skinsense_test
    
    # Override database connection
    db.database = test_database
    
    yield test_database
    
    # Cleanup after test
    await test_client.drop_database("skinsense_test")
    test_client.close()

@pytest.fixture
async def client(test_db):
    """Create test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def auth_headers(client):
    """Create authenticated user and return headers"""
    # Register user
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123"
        }
    )
    
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )
    
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}