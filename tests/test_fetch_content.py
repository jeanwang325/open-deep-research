"""
Tests for the fetch_content endpoint.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_fetch_content_success(test_client, mock_jina_response):
    """Test successful content fetching."""
    response = test_client.post(
        "/fetch-content",
        json={"url": "https://example.com"}
    )
    print(response.json())
    assert response.status_code == 200
    # with patch("requests.get") as mock_get:
    #     # Configure the mock
    #     mock_response = MagicMock()
    #     mock_response.ok = True
    #     mock_response.json.return_value = mock_jina_response
    #     mock_get.return_value = mock_response
        
    #     response = test_client.post(
    #         "/fetch-content",
    #         json={"url": "https://example.com"}
    #     )

    #     assert response.status_code == 200
    #     assert "content" in response.json()
    #     assert "Test Title" in response.json()["content"]
    #     assert "Test Content" in response.json()["content"]


def test_fetch_content_missing_url(test_client):
    """Test error handling for missing URL."""
    response = test_client.post(
        "/fetch-content",  # Remove http://test prefix
        json={}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "URL is required"


def test_fetch_content_rate_limit(test_client):
    """Test rate limiting."""
    with patch("richoo.lib.redis.fetch_content_ratelimit.limit") as mock_limit:
        # Configure the mock to simulate rate limit exceeded
        mock_limit.return_value = AsyncMock(return_value=False)()
        
        response = test_client.post(
            "/fetch-content",
            json={"url": "https://example.com"}
        )
        
        assert response.status_code == 429
        assert response.json()["detail"] == "Too many requests"
        mock_limit.assert_called_once_with("https://example.com")