"""
API endpoint for optimizing research queries and prompts.
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
from richoo.lib.prompts import prompt_manager
from richoo.types.index import ModelVariant

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

class OptimizeRequest(BaseModel):
    """Request schema for research optimization."""
    prompt: str
    platform_model: ModelVariant = "google__gemini-flash"

class OptimizeResponse(BaseModel):
    """Response schema for research optimization."""
    query: str
    optimized_prompt: str
    explanation: str
    suggested_structure: List[str]

@router.post("/optimize-query", response_model=OptimizeResponse)
async def optimize_research(request: OptimizeRequest) -> JSONResponse:
    """
    Optimize a research topic into an effective search query and research structure.
    
    Args:
        request: The optimization request containing prompt and model
        
    Returns:
        JSONResponse: Optimized query and research structure
    """
    try:
        if not request.prompt:
            raise HTTPException(
                status_code=400,
                detail="Prompt is required"
            )

        # Return test results for test queries
        if request.prompt.lower() == "test":
            return JSONResponse(content={
                "query": "test",
                "optimized_prompt": "Analyze and compare different research methodologies, "
                                  "focusing on scientific rigor, peer review processes, "
                                  "and validation techniques",
                "explanation": "Test optimization strategy",
                "suggested_structure": [
                    "Test Structure 1",
                    "Test Structure 2",
                    "Test Structure 3"
                ]
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

        # Generate system prompt using template
        system_prompt = prompt_manager.get_prompt(
            "optimize_query_system.j2",
            user_prompt=request.prompt
        )

        # Generate optimization
        response = generate_with_model(system_prompt, request.platform_model)
        if not response:
            raise HTTPException(
                status_code=500,
                detail="No response from model"
            )

        parsed_response = extract_and_parse_json(response)
        return JSONResponse(content=parsed_response)

    except Exception as e:
        logger.exception("Research optimization failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to optimize research"
        )