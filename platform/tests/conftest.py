"""
Test configuration and fixtures
"""
import pytest
import tempfile
import os
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.models import Base
from app.db import get_db
from app.services.auth import get_password_hash
from app.services.security import security_service


@pytest.fixture(scope="session")
def test_db():
    """Create a temporary database for testing"""
    # Use SQLite in-memory database for tests
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    test_db_url = f"sqlite:///{db_path}"
    
    # Create engine and session
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    yield TestingSessionLocal, engine
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def db_session(test_db):
    """Create a database session for testing"""
    TestingSessionLocal, engine = test_db
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db):
    """Create a test client with test database"""
    TestingSessionLocal, engine = test_db
    
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from app.db.models import User
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_tokens(client, test_user):
    """Get tokens for test user"""
    login_data = {
        "username": "testuser",
        "password": "testpassword123"
    }
    response = client.post("/api/users/login", data=login_data)
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def auth_headers(test_user_tokens):
    """Get authentication headers"""
    return {"Authorization": f"Bearer {test_user_tokens['access_token']}"}


@pytest.fixture
def mock_request():
    """Mock request object for testing"""
    class MockRequest:
        def __init__(self):
            self.headers = {"User-Agent": "Test Browser", "X-Real-IP": "127.0.0.1"}
            self.client = type('obj', (object,), {'host': '127.0.0.1'})
    
    return MockRequest()


@pytest.fixture(autouse=True)
def reset_security_service():
    """Reset security service state between tests"""
    # Reset any internal state that might exist
    try:
        if hasattr(security_service, 'rate_limit_storage'):
            security_service.rate_limit_storage.clear()
        if hasattr(security_service, 'blocked_tokens'):
            security_service.blocked_tokens.clear()
    except AttributeError:
        pass  # Service may not have these attributes
    yield
