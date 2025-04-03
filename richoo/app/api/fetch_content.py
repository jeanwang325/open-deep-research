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
import logging
from typing import Dict, Any, Optional
from urllib.parse import quote

from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from richoo.lib.redis import fetch_content_ratelimit
from richoo.lib.config import CONFIG
from richoo.types.index import Article

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

class ContentRequest(BaseModel):
    """ContentFetching request schema."""
    url: str
    use_sub_pages: Optional[bool] = True  # Default to True to fetch sub-pages if needed

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
        use_sub_pages = request.use_sub_pages
        articles = []
        sources = []

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        # Check rate limit if enabled
        if CONFIG["rateLimits"]["enabled"]:
            success = fetch_content_ratelimit.limit(url)
            logger.debug("Rate limit check: %s", success)
            if not success:
                raise HTTPException(status_code=429, detail="Too many requests")

        try:
            logger.info("Fetching content for URL: %s", url)
            response = requests.get(
                f"https://r.jina.ai/{quote(url)}",
                headers={
                    "X-With-Links-Summary": "true",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()

            jina_output = response.json()
            logger.debug("Jina response json: %s", jina_output)
            
            links = jina_output.get("data", {}).get("links", {})
            main_title = jina_output.get("data", {}).get("title", "")
            main_content = jina_output.get("data", {}).get("content", "")
            content = f"# Main Page: {main_title}\n{main_content}"

            if use_sub_pages and links and isinstance(links, dict):
                for key, value in links.items():
                    logger.info("Processing link key: %s, value: %s", key, value)
                    
                    if value in [url, f"{url}/", f"{url}/#page"]:
                        logger.info("Skipping link as it matches the original URL: %s", value)
                        continue
                    if value.startswith(url):
                        try:
                            sub_response = requests.get(
                                f"https://r.jina.ai/{quote(value)}",
                                headers={
                                    "X-Engine": "direct",
                                    "X-Retain-Images": "none",
                                    "X-Remove-Selector": "header, a, .class, #id",
                                    "X-Token-Budget": "2000",
                                    "Accept": "application/json",
                                },
                            )
                            if not sub_response.ok:
                                logger.warning(
                                    "Failed to fetch content for sub-website %s: %s",
                                    value,
                                    sub_response.status_code
                                )
                                if sub_response.status_code == 429:
                                    logger.warning("Rate limit exceeded. Sleeping for 1 minute...")
                                    time.sleep(60)
                                continue

                            sub_jina_output = sub_response.json()
                            sub_title = sub_jina_output.get("data", {}).get("title", "")
                            sub_content = sub_jina_output.get("data", {}).get("content", "")
                            content += f"\n\n---\n\n# Sub-Page: {sub_title}\n{sub_content}"
                        except Exception as error:
                            logger.error(
                                "Error fetching content for sub-website %s: %s",
                                value,
                                str(error)
                            )
                    else:
                        logger.info(
                            "Skipping link as it does not start with the main URL. Link: %s",
                            value,
                        )

            logger.info("Content fetching completed successfully")
            logger.debug("Final content length: %d characters", len(content))
            return JSONResponse(content={"content": content})

        except requests.RequestException as error:
            logger.error("Error fetching content for %s: %s", url, str(error))
            raise HTTPException(status_code=500, detail="Failed to fetch content")

    except json.JSONDecodeError as error:
        logger.error("Content fetching error: %s", str(error))
        raise HTTPException(status_code=400, detail="Invalid request")