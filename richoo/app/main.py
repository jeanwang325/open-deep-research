"""
Main FastAPI application that combines all API endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from richoo.app.api.fetch_content import router as fetch_router
from richoo.app.api.report import router as report_router

app = FastAPI(
    title="Deep Research API",
    description="API for fetching and analyzing content",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(fetch_router, prefix="/api")
app.include_router(report_router, prefix="/api")