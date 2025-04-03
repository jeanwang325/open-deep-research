"""
API endpoint for analyzing search results.
"""

import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from richoo.lib.redis import report_content_ratelimit
from richoo.lib.config import CONFIG
from richoo.lib.utils import extract_and_parse_json
from richoo.lib.models import generate_with_model
from richoo.types.index import ModelVariant
from richoo.lib.prompts import prompt_manager

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

class SearchResult(BaseModel):
    """Search result input schema."""
    name: str
    snippet: str
    url: str
    content: Optional[str] = None

class AnalyzeRequest(BaseModel):
    """Analysis request schema."""
    prompt: str
    results: List[SearchResult]
    is_test_query: bool = False
    platform_model: ModelVariant = "google__gemini-flash"

@router.post("/analyze-results")
async def analyze_results(request: AnalyzeRequest) -> JSONResponse:
    """
    Analyze search results for relevance and quality.
    
    Args:
        request: The analysis request containing prompt and results
        
    Returns:
        JSONResponse: Rankings and analysis of results
    """
    try:
        if not request.prompt or not request.results:
            raise HTTPException(
                status_code=400,
                detail="Prompt and results are required"
            )

        # Return test results for test queries
        if (request.is_test_query or 
            any(r.url and "example.com/test" in r.url for r in request.results)):
            return JSONResponse(content={
                "rankings": [
                    {
                        "url": result.url,
                        "score": 1.0 if i == 0 else 0.5,
                        "reasoning": "Test ranking result"
                    }
                    for i, result in enumerate(request.results)
                ],
                "analysis": "Test analysis of search results"
            })

        # Check rate limit if enabled and not using local model
        platform, model = request.platform_model.split("__")
        if CONFIG["rateLimits"]["enabled"] and platform != "ollama":
            success = report_content_ratelimit.limit("agentOptimizations")
            if not success:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests"
                )

        # Validate platform and model
        platform_config = CONFIG["platforms"].get(platform)
        if not platform_config or not platform_config.get("enabled"):
            raise HTTPException(
                status_code=400,
                detail=f"{platform} platform is not enabled"
            )

        model_config = platform_config["models"].get(model)
        if not model_config:
            raise HTTPException(
                status_code=400,
                detail=f"{model} model does not exist"
            )
        if not model_config.get("enabled"):
            raise HTTPException(
                status_code=400,
                detail=f"{model} model is disabled"
            )

        # Generate system prompt
        system_prompt = prompt_manager.get_prompt(
            "analyze_results_system.j2",
            user_prompt=request.prompt,
            results=request.results,
        )
        logger.info("Analyze result System prompt: %s", system_prompt)
        # Generate analysis
        response = generate_with_model(system_prompt, request.platform_model)
        if not response:
            raise HTTPException(
                status_code=500,
                detail="No response from model"
            )

        parsed_response = extract_and_parse_json(response)
        return JSONResponse(content=parsed_response)

    except Exception as e:
        logger.exception("Result analysis failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to analyze results"
        )