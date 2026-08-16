"""
Pipeline dependency — single instance shared across all requests.

`set_pipeline` is called once during app lifespan startup.
`get_pipeline` is a FastAPI dependency that raises 503 if the
pipeline was not successfully initialised (e.g. vector index missing).
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from backend.pipeline.orchestrator import AgenticRAGPipeline

_pipeline: Optional[AgenticRAGPipeline] = None


def set_pipeline(instance: Optional[AgenticRAGPipeline]) -> None:
    global _pipeline
    _pipeline = instance


def pipeline_ready() -> bool:
    return _pipeline is not None


def get_pipeline() -> AgenticRAGPipeline:
    if _pipeline is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Vector index not built. "
                "Run `python main.py ingest` then restart the server."
            ),
        )
    return _pipeline
