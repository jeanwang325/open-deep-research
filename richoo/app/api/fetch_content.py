"""
API route handler for fetching content from URLs.

This module provides an endpoint that:
- Validates incoming URL requests
- Implements rate limiting
- Fetches content from URLs using Jina AI
- Handles sub-page content fetching
"""

import json
import time
from typing import Dict, Any, Optional
from urllib.parse import quote

from pydantic import BaseModel
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi import APIRouter

from richoo.lib.redis import fetch_content_ratelimit
from richoo.lib.config import CONFIG

# Replace FastAPI() with APIRouter()
router = APIRouter()

class ContentRequest(BaseModel):
    """ContentFetching request schema."""
    url: str

@router.post("/fetch-content")
async def fetch_content(request: ContentRequest) -> JSONResponse:
    """
    Handle POST requests to fetch content from a given URL.

    Args:
        request: The incoming FastAPI request object.

    Returns:
        JSONResponse: The fetched content or error message.

    Raises:
        HTTPException: For invalid requests or rate limit violations.
    """
    try:
        
        url = request.url

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        print(f"Received URL: {url}")
        # Check rate limit if enabled
        if CONFIG["rateLimits"]["enabled"]:
            print("begin")
            success = fetch_content_ratelimit.limit(url)
            print("Rate limit check:", success)
            if not success:
                raise HTTPException(status_code=429, detail="Too many requests")
        print("start trying")
        try:
            print(f"Fetching content for URL: {url}")
            response = requests.get(
                f"https://r.jina.ai/{quote(url)}",
                headers={
                    "X-With-Links-Summary": "true",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()

            jina_output = response.json()
            print("Jina response json:", jina_output)
            
            links = jina_output.get("data", {}).get("links", {})
            main_title = jina_output.get("data", {}).get("title", "")
            main_content = jina_output.get("data", {}).get("content", "")
            content = f"# Main Page: {main_title}\n{main_content}"

            if links and isinstance(links, dict):
                for key, value in links.items():
                    print(f"Processing link key: {key}, value: {value}")
                    
                    if value in [url, f"{url}/", f"{url}/#page"]:
                        print(f"Skipping link as it matches the original URL: {value}")
                        continue

                    if value.startswith(url):
                        try:
                            sub_response = requests.get(
                                f"https://r.jina.ai/{quote(value)}",
                                headers={
                                    "X-Engine": "direct",
                                    "X-Retain-Images": "none",
                                    "X-Remove-Selector": "header, a, .class, #id",
                                    "X-Token-Budget": "1000",
                                    "Accept": "application/json",
                                },
                            )
                            if not sub_response.ok:
                                print(f"Failed to fetch content for sub-website {value}: {sub_response.status_code}")
                                if sub_response.status_code == 429:
                                    print("Rate limit exceeded. Sleeping for 1 minute...")
                                    time.sleep(60)
                                continue

                            sub_jina_output = sub_response.json()
                            sub_title = sub_jina_output.get("data", {}).get("title", "")
                            sub_content = sub_jina_output.get("data", {}).get("content", "")
                            content += f"\n\n---\n\n# Sub-Page: {sub_title}\n{sub_content}"
                        except Exception as error:
                            print(f"Error fetching content for sub-website {value}: {error}")
                    else:
                        print(f"Skipping link as it does not start with the main URL: {value}")

            print(f"**********************\nJina response main content:\n{content}\n**********************")
            return JSONResponse(content={"content": content})

        except requests.RequestException as error:
            print(f"Error fetching content for {url}: {error}")
            raise HTTPException(status_code=500, detail="Failed to fetch content")

    except json.JSONDecodeError as error:
        print("Content fetching error:", error)
        raise HTTPException(status_code=400, detail="Invalid request")