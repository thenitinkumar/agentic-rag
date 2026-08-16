"""Pydantic request/response models for the Earnings Intelligence API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class StepOut(BaseModel):
    id: str
    question: str
    routes: list[str]
    intermediate_answer: str
    sources: list[str]
    sql: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    decomposed: bool
    routing_reasoning: str
    steps: list[StepOut]
    all_sources: list[str]
    all_sql: list[str]


class CompanyOut(BaseModel):
    ticker: str
    name: str
    sector: str
    quarters_available: int


class HealthOut(BaseModel):
    status: str
    mock_llm: bool
    vector_index_ready: bool
    companies_loaded: int
