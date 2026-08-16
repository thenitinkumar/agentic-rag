from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.pipeline.orchestrator import AgenticRAGPipeline, PipelineTrace

from ..dependencies import get_pipeline
from ..schemas import QueryRequest, QueryResponse, StepOut

router = APIRouter()


def _trace_to_response(trace: PipelineTrace) -> QueryResponse:
    """Flatten a PipelineTrace into the API response shape."""
    steps_out: list[StepOut] = []
    all_sources: list[str] = []
    all_sql: list[str] = []

    for step in trace.steps:
        sources: list[str] = []
        sql: Optional[str] = None

        for r in step.retrievals:
            if r.route == "sql" and r.generated_sql:
                sql = r.generated_sql
                if r.generated_sql not in all_sql:
                    all_sql.append(r.generated_sql)
            elif r.route == "vector":
                for chunk in r.chunks:
                    if chunk.source not in sources:
                        sources.append(chunk.source)
                    if chunk.source not in all_sources:
                        all_sources.append(chunk.source)

        steps_out.append(StepOut(
            id=step.subquestion_id,
            question=step.question,
            routes=step.routing.routes,
            intermediate_answer=step.intermediate_answer,
            sources=sources,
            sql=sql,
        ))

    return QueryResponse(
        answer=trace.final_answer,
        decomposed=trace.decomposed,
        routing_reasoning=trace.top_level_routing.reasoning,
        steps=steps_out,
        all_sources=all_sources,
        all_sql=all_sql,
    )


@router.post("/query", response_model=QueryResponse, tags=["pipeline"])
def query(
    req: QueryRequest,
    pipeline: AgenticRAGPipeline = Depends(get_pipeline),
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        trace = pipeline.run(req.question.strip())
        return _trace_to_response(trace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
