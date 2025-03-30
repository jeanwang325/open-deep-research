"""
Pytest configuration and shared fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from typing import Generator, Dict, Any

from richoo.app.api.fetch_content import app
from richoo.lib.config import CONFIG


@pytest.fixture
def test_client() -> TestClient:
    """
    Test client fixture.
    
    Returns:
        TestClient: Configured FastAPI test client
    """
    return TestClient(app)


@pytest.fixture
def mock_jina_response() -> Dict[str, Any]:
    """
    Mock Jina API response.
    
    Returns:
        Dict[str, Any]: Mock response data
    """
    return {
        "data": {
            "title": "Test Title",
            "content": "Test Content",
            "links": {
                "link1": "https://example.com/page1",
                "link2": "https://example.com/page2"
            }
        }
    }


@pytest.fixture(autouse=True)
def mock_config() -> Generator[Dict[str, Any], None, None]:
    """
    Mock configuration with rate limiting enabled.
    This fixture runs automatically for all tests.
    
    Yields:
        Dict[str, Any]: Mocked configuration
    """
    original_config = CONFIG.copy()
    CONFIG["rateLimits"] = {
        "enabled": True,
        "search": 60,
        "contentFetch": 60,
        "reportGeneration": 60
    }
    yield CONFIG
    # Restore original config after test
    CONFIG.update(original_config)