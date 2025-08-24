import pytest
from httpx import AsyncClient
import pymongo
from app.main import app
from app.database import db, get_database
from app.config import settings
from unittest.mock import MagicMock
import os

# Test database URL - use local MongoDB for tests
TEST_DB_URL = os.getenv("TEST_MONGODB_URL", "mongodb://localhost:27017/skinsense_test")

@pytest.fixture(scope="function")
def test_db():
    """Create test database connection using PyMongo"""
    # Connect to test database
    test_client = pymongo.MongoClient(TEST_DB_URL)
    test_database = test_client.skinsense_test
    
    # Clear test database before tests
    for collection_name in test_database.list_collection_names():
        test_database[collection_name].drop()
    
    # Override database connection in app
    original_db = db.database
    db.database = test_database
    
    yield test_database
    
    # Cleanup after test
    test_client.drop_database("skinsense_test")
    db.database = original_db
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

@pytest.fixture
def mock_orbo_service():
    """Mock ORBO AI service for tests"""
    mock = MagicMock()
    mock.analyze_skin.return_value = {
        "overall_skin_health_score": 85,
        "hydration": 75,
        "smoothness": 80,
        "radiance": 90,
        "dark_spots": 70,
        "firmness": 85,
        "fine_lines_wrinkles": 80,
        "acne": 95,
        "dark_circles": 75,
        "redness": 85
    }
    return mock

@pytest.fixture
def mock_openai_service():
    """Mock OpenAI service for tests"""
    mock = MagicMock()
    mock.generate_feedback.return_value = {
        "feedback": "Your skin looks great! Keep up the good routine.",
        "recommendations": ["Use sunscreen daily", "Stay hydrated"]
    }
    return mock