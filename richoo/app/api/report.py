"""
API endpoint for generating reports from selected articles.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from richoo.lib.redis import report_content_ratelimit
from richoo.lib.config import CONFIG
from richoo.lib.utils import extract_and_parse_json
from richoo.lib.models import generate_with_model
from richoo.types.index import Article, ModelVariant
from richoo.lib.prompts import prompt_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReportRequest(BaseModel):
    """Report generation request schema."""
    selected_results: List[Article]
    sources: List[dict]
    prompt: str
    platform_model: ModelVariant = "google-gemini-flash"


router = APIRouter()


@router.post("/report")
async def generate_report(request: ReportRequest) -> JSONResponse:
    """
    Generate a report from selected articles.

    Args:
        request: The report generation request containing articles and configuration

    Returns:
        JSONResponse: Generated report or error message

    Raises:
        HTTPException: For rate limits, invalid models, or generation errors
    """
    try:
        platform, model = request.platform_model.split("__")

        # Check rate limit for non-Ollama platforms
        if CONFIG["rateLimits"]["enabled"] and platform != "ollama":
            success = report_content_ratelimit.limit("report")
            if not success:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests"
                )

        # Validate platform
        platform_config = CONFIG["platforms"].get(platform)
        if not platform_config or not platform_config.get("enabled"):
            raise HTTPException(
                status_code=400,
                detail=f"{platform} platform is not enabled"
            )

        # Validate model
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

        # Generate report using template
        system_prompt = prompt_manager.get_prompt(
            "provider_insights_system.j2",
            articles=request.selected_results,
            user_prompt=request.prompt
        )
        
        logger.info("Using model: %s", model)
        logger.debug("System prompt: %s", system_prompt)
        
        response = generate_with_model(system_prompt, request.platform_model)
        if not response:
            raise HTTPException(
                status_code=500,
                detail="No response from model"
            )

        report_data = extract_and_parse_json(response)
        report_data["sources"] = request.sources
        
        logger.debug("Parsed report data: %s", report_data)
        return JSONResponse(content=report_data)

    except ValueError as e:
        logger.error("Report generation error: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate report"
        )

    except Exception as e:
        logger.exception("Unexpected error while generating report: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )