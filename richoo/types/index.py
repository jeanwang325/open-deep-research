"""
Type definitions for the application's data models.

This module defines the core data structures used throughout the application,
including reports, search results, and flow node configurations.
"""

from typing import Dict, List, Literal, Optional, Union, Any
from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    """Section of a report containing a title and content."""

    title: str
    content: str


class ReportSource(BaseModel):
    """Source reference for a report."""

    id: str
    url: str
    name: str


class Report(BaseModel):
    """Complete report structure with sections and sources."""

    title: str
    summary: str
    sections: List[ReportSection]
    sources: List[ReportSource]
    used_sources: Optional[List[int]] = Field(
        None, description="Array of source indices that were actually used/cited"
    )


class Article(BaseModel):
    """Article data structure."""

    url: str
    title: str
    content: str

class Source(BaseModel):
    """Source data structure for articles."""

    url: str
    name: str

class KnowledgeBaseReport(BaseModel):
    """Knowledge base entry containing a report and metadata."""

    id: str
    timestamp: int
    query: str
    report: Report


class SearchResult(BaseModel):
    """Search result with metadata."""

    id: str
    url: str
    name: str
    snippet: str
    is_custom_url: Optional[bool] = None
    score: Optional[float] = None
    content: Optional[str] = None


class RankingResult(BaseModel):
    """Result of ranking process."""

    url: str
    score: float
    reasoning: str


class PlatformModel(BaseModel):
    """Model configuration for AI platforms."""

    value: str
    label: str
    platform: str
    disabled: bool


ModelVariant = Literal[
    "google__gemini-flash",
    "google__gemini-flash-lite",
    "google__gemini-flash-thinking",
    "google__gemini-exp",
    "gpt-4o",
    "o1-mini",
    "o1",
    "claude-3-7-sonnet-latest",
    "claude-3-5-haiku-latest",
    "deepseek__chat",
    "deepseek__reasoner",
    "ollama__llama3.2",
    "ollama__deepseek-r1:14b",
    "openrouter__auto",
]


class FetchStatus(BaseModel):
    """Status of content fetching operations."""

    total: int
    successful: int
    fallback: int
    source_statuses: Dict[str, Literal["fetched", "preview"]]


class Status(BaseModel):
    """Overall application status."""

    loading: bool
    generating_report: bool
    agent_step: Literal["idle", "processing", "searching", "analyzing", "generating"]
    fetch_status: FetchStatus
    agent_insights: List[str]
    search_queries: List[str]


class State(BaseModel):
    """Application state."""

    original_query: str
    query: str
    time_filter: str
    results: List[SearchResult]
    selected_results: List[str]
    report_prompt: str
    report: Optional[Report] = None
    error: Optional[str] = None
    new_url: str
    is_sources_open: bool
    selected_model: str
    is_agent_mode: bool
    sidebar_open: bool
    active_tab: str
    status: Status


class BaseNodeData(BaseModel):
    """Base class for flow node data."""

    id: Optional[str] = None
    loading: Optional[bool] = None
    error: Optional[str] = None
    parent_id: Optional[str] = None
    child_ids: Optional[List[str]] = None


class SearchNodeData(BaseNodeData):
    """Search node specific data."""

    query: str
    on_file_upload: Optional[dict] = None  # Placeholder for callback


class SelectionNodeData(BaseNodeData):
    """Selection node specific data."""

    results: List[SearchResult]
    on_generate_report: Optional[dict] = None  # Placeholder for callback


class ReportNodeData(BaseNodeData):
    """Report node specific data."""

    report: Optional[Report] = None
    is_selected: Optional[bool] = None
    on_select: Optional[dict] = None  # Placeholder for callback
    is_consolidated: Optional[bool] = None
    is_consolidating: Optional[bool] = None


class SearchTermsNodeData(BaseNodeData):
    """Search terms node specific data."""

    search_terms: Optional[List[str]] = None
    on_approve: Optional[dict] = None  # Placeholder for callback


class FlowNodeData(BaseNodeData):
    """Combined flow node data with all possible properties."""

    query: Optional[str] = None
    results: Optional[List[SearchResult]] = None
    report: Optional[Report] = None
    search_terms: Optional[List[str]] = None
    question: Optional[str] = None
    on_generate_report: Optional[dict] = None  # Placeholder for callback
    on_approve: Optional[dict] = None  # Placeholder for callback
    on_consolidate: Optional[dict] = None  # Placeholder for callback
    has_children: Optional[bool] = None
    is_selected: Optional[bool] = None
    on_select: Optional[dict] = None  # Placeholder for callback
    is_consolidated: Optional[bool] = None
    is_consolidating: Optional[bool] = None
    on_file_upload: Optional[dict] = None  # Placeholder for callback
    additional_properties: Dict[str, Any] = Field(default_factory=dict)


class NodeConfig(BaseModel):
    """Configuration for node styling."""

    z_index: int
    style: Optional[Dict[str, Union[str, int, float]]] = None