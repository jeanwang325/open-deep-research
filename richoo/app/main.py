"""
Main FastAPI application that combines all API endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi


from richoo.app.api.analyze_results import router as analyze_router
from richoo.app.api.search import router as search_router
from richoo.app.api.fetch_content import router as fetch_router
from richoo.app.api.report import router as report_router
from richoo.app.api.optimize_query import router as optimize_router

app = FastAPI(
    title="Deep Research API",
    description="API for fetching and analyzing content",
    version="1.0.0"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add example values for common parameters
    for path in openapi_schema["paths"].values():
        for method in path.values():
            if "requestBody" in method:
                schema = method["requestBody"]["content"]["application/json"]["schema"]
                if "SearchRequest" in str(schema):
                    method["requestBody"]["content"]["application/json"]["example"] = {
                        "query": "math enrichment activities",
                        "time_filter": "month",
                        "provider": "google",
                        "is_test_query": False
                    }
                elif "ContentRequest" in str(schema):
                    method["requestBody"]["content"]["application/json"]["example"] = {
                        "url": "https://example.com/article",
                        "fetch_sublinks": True
                    }
                elif "AnalyzeRequest" in str(schema):
                    method["requestBody"]["content"]["application/json"]["example"] = {
                        "prompt": "Find high-quality math enrichment resources",
                        "results": [
                            {
                                "title": "Math Learning Center",
                                "snippet": "Interactive math activities for K-5 students",
                                "url": "https://example.com/math",
                                "content": "Full article content here..."
                            }
                        ],
                        "platform_model": "google__gemini-flash"
                    }
                elif "ReportRequest" in str(schema):
                    method["requestBody"]["content"]["application/json"]["example"] = {
                        "selected_results": [
                            {
                                "url": "https://example.com/article",
                                "title": "Sample Article",
                                "content": "Article content here..."
                            }
                        ],
                        "sources": [
                            {
                                "id": "1",
                                "url": "https://example.com/article",
                                "name": "Sample Source"
                            }
                        ],
                        "prompt": "Analyze math enrichment activities",
                        "platform_model": "google__gemini-flash"
                    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(optimize_router, prefix="/api", tags=["optimize_query"])
app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(analyze_router, prefix="/api", tags=["analyze"])
app.include_router(fetch_router, prefix="/api", tags=["fetch_content"])
app.include_router(report_router, prefix="/api", tags=["report"])
