"""
Search API endpoint supporting multiple search providers (Bing, Google, Exa).
"""

import logging
from typing_extensions import Literal
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from richoo.lib.redis import search_ratelimit
from richoo.lib.config import CONFIG

import os
import httpx

from richoo.lib.config import CONFIG

from richoo.lib.credentials import load_credentials

# Configure the Gemini API with the API key
load_credentials()

# Configure logging
logger = logging.getLogger(__name__)

# Constants
BING_ENDPOINT = 'https://api.bing.microsoft.com/v7.0/search'
GOOGLE_ENDPOINT = 'https://customsearch.googleapis.com/customsearch/v1'
EXA_ENDPOINT = 'https://api.exa.ai/search'

# Types
TimeFilter = Literal['24h', 'week', 'month', 'year', 'all']

class SearchRequest(BaseModel):
    """Search request schema."""
    query: str
    time_filter: TimeFilter = 'all'
    provider: str = CONFIG["search"]["provider"]
    is_test_query: bool = False

router = APIRouter()

def get_bing_freshness(time_filter: TimeFilter) -> str:
    """Map our time filter to Bing's freshness parameter."""
    return {
        '24h': 'Day',
        'week': 'Week',
        'month': 'Month',
        'year': 'Year'
    }.get(time_filter, '')

def get_google_date_restrict(time_filter: TimeFilter) -> Optional[str]:
    """Map our time filter to Google's dateRestrict parameter."""
    return {
        '24h': 'd1',
        'week': 'w1',
        'month': 'm1',
        'year': 'y1'
    }.get(time_filter)


async def handle_exa_search(request: SearchRequest) -> JSONResponse:
    """Handle Exa search requests."""
    exa_api_key = os.getenv("EXA_API_KEY")
    if not exa_api_key:
        raise HTTPException(
            status_code=500,
            detail="Exa search API is not properly configured"
        )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            EXA_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {exa_api_key}"
            },
            json={
                "query": request.query,
                "type": "auto",
                "numResults": CONFIG["search"]["resultsPerPage"],
                "contents": {"text": {"maxCharacters": 500}}
            }
        )
        
        if response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )
            
        response.raise_for_status()
        data = response.json()
        
        # Transform results
        transformed = {
            "webPages": {
                "value": [
                    {
                        "id": item.get("id", item["url"]),
                        "url": item["url"],
                        "name": item.get("title", "Untitled"),
                        "snippet": item.get("text", ""),
                        "publishedDate": item.get("publishedDate"),
                        "author": item.get("author"),
                        "image": item.get("image"),
                        "favicon": item.get("favicon"),
                        "score": item.get("score")
                    }
                    for item in data["results"]
                ]
            }
        }
        
        return JSONResponse(content=transformed)


async def handle_google_search(request: SearchRequest) -> JSONResponse:
    """Handle Google Custom Search requests."""
    google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    google_cx = os.getenv("GOOGLE_SEARCH_CX")
    
    if not google_api_key or not google_cx:
        raise HTTPException(
            status_code=500,
            detail="Google search API is not properly configured"
        )

    # Build query parameters
    params = {
        "q": request.query,
        "key": google_api_key,
        "cx": google_cx,
        "num": str(CONFIG["search"]["resultsPerPage"]),
        "safe": CONFIG["search"]["safeSearch"]["google"]
    }

    # Add date restriction if specified
    date_restrict = get_google_date_restrict(request.time_filter)
    if date_restrict:
        params["dateRestrict"] = date_restrict

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GOOGLE_ENDPOINT}?{urlencode(params)}"
        )

        if not response.is_success:
            data = response.json()
            if "error" in data and "Quota exceeded" in data["error"].get("message", ""):
                raise HTTPException(
                    status_code=429,
                    detail="Daily search limit reached. Please try again tomorrow."
                )
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to fetch search results"
            )

        data = response.json()
        
        # Transform Google results to match our format
        transformed = {
            "webPages": {
                "value": [
                    {
                        "id": item.get("cacheId", item["link"]),
                        "url": item["link"],
                        "name": item["title"],
                        "snippet": item["snippet"]
                    }
                    for item in data.get("items", [])
                ]
            }
        }
        
        return JSONResponse(content=transformed)


async def handle_bing_search(request: SearchRequest) -> JSONResponse:
    """Handle Bing Search requests."""
    subscription_key = os.getenv("AZURE_SUB_KEY")
    
    if not subscription_key:
        raise HTTPException(
            status_code=500,
            detail="Bing search API is not properly configured"
        )

    # Build query parameters
    params = {
        "q": request.query,
        "count": str(CONFIG["search"]["resultsPerPage"]),
        "mkt": CONFIG["search"]["market"],
        "safeSearch": CONFIG["search"]["safeSearch"]["bing"],
        "textFormat": "HTML",
        "textDecorations": "true"
    }

    # Add freshness parameter if specified
    freshness = get_bing_freshness(request.time_filter)
    if freshness:
        params["freshness"] = freshness

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BING_ENDPOINT}?{urlencode(params)}",
            headers={
                "Ocp-Apim-Subscription-Key": subscription_key,
                "Accept-Language": "en-US"
            }
        )

        if response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="Monthly search quota exceeded. Please try again next month."
            )

        if not response.is_success:
            data = response.json()
            raise HTTPException(
                status_code=response.status_code,
                detail=data.get("message", "Failed to fetch search results")
            )

        # Bing results are already in our desired format
        return JSONResponse(content=response.json())
    
@router.post("/search")
async def search(request: SearchRequest) -> JSONResponse:
    """Handle search requests across multiple providers."""
    try:
        logger.info("Search API request: %s", request)
        
        if not request.query:
            raise HTTPException(
                status_code=400,
                detail="Query parameter is required"
            )

        # Return dummy results for test queries
        if request.query.lower() == 'test' or request.is_test_query:
            return JSONResponse(content={
                "webPages": {
                    "value": [
                        {
                            "id": "test-1",
                            "url": "https://example.com/test-1",
                            "name": "Test Result 1",
                            "snippet": "This is a test search result for testing purposes."
                        },
                        # ...more test results...
                    ]
                }
            })

        # Check rate limit if enabled
        if CONFIG["rateLimits"]["enabled"]:
            success = search_ratelimit.limit(request.query)
            if not success:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment."
                )

        # Handle different search providers
        if request.provider == 'exa':
            return await handle_exa_search(request)
        elif request.provider == 'google':
            return await handle_google_search(request)
        else:
            return await handle_bing_search(request)  # Default

    except Exception as e:
        logger.exception("Search API error: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=str(e) if isinstance(e, HTTPException) else "Unexpected error"
        )