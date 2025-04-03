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
        "platform_model": "google__gemini-flash-lite"
    }

    logger.info("Testing report generation endpoint...")
    response = requests.post(url, json=payload)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
    return response

def test_search():
    """Test the search endpoint."""
    url = f"{BASE_URL}/search"
    payload = {
        "query": "Camp Riverbend",
        "time_filter": "month",
        "provider": "google",
        "is_test_query": "false",
    }

    logger.info("Testing search endpoint...")
    response = requests.post(url, json=payload)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
    return response

def test_analyze_results(search_results):
    """Test the analyze-results endpoint."""
    url = f"{BASE_URL}/analyze-results"
    payload = {
        "prompt": "Find high-quality resources for Camp Riverbend",
        "results": search_results,
        "platform_model": "google__gemini-flash-lite",
        "is_test_query": False
    }

    logger.info("Testing analyze-results endpoint...")
    response = requests.post(url, json=payload)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
    return response

def test_optimize_query():
    """Test the optimize-query endpoint."""
    url = f"{BASE_URL}/optimize-query"
    payload = {
        "prompt": "Impact of after school enrichment programs on student development",
        "platform_model": "google__gemini-flash-lite"
    }

    logger.info("Testing optimize-query endpoint...")
    response = requests.post(url, json=payload)
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
    return response


if __name__ == "__main__":
    # # Test search and analysis flow
    # search_results = test_search()
    # test_analyze_results(search_results.json()["webPages"]["value"])

    # Test query optimization
    test_optimize_query()
    # test_fetch_content()
    # test_report_generation()