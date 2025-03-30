"""
Manual API testing script.
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"

def test_fetch_content():
    """Test the fetch-content endpoint."""
    url = f"{BASE_URL}/fetch-content"
    payload = {
        "url": "https://example.com"
    }

    logger.info("Testing fetch-content endpoint...")
    response = requests.post(url, json=payload)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
    return response


def test_report_generation():
    """Test the report generation endpoint."""
    url = f"{BASE_URL}/report"
    payload = {
        "selected_results": [
            {
                "url": "https://example.com",
                "title": "Test Article",
                "content": "Sample content for testing"
            }
        ],
        "sources": [
            {
                "id": "1",
                "url": "https://example.com",
                "name": "Example Source"
            }
        ],
        "prompt": "Generate a report about enrichment activities",
        "platform_model": "google__gemini-flash"
    }

    logger.info("Testing report generation endpoint...")
    response = requests.post(url, json=payload)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
    return response


if __name__ == "__main__":
    # Start the server first using: python run.py
    test_fetch_content()
    test_report_generation()