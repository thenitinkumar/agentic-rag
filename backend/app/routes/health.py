from fastapi import APIRouter

from backend.pipeline.config import SETTINGS

from ..dependencies import pipeline_ready
from ..schemas import HealthOut
from ..services.data import load_companies

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["meta"])
def health():
    companies = load_companies()
    return HealthOut(
        status="ok",
        mock_llm=SETTINGS.mock_llm,
        vector_index_ready=pipeline_ready(),
        companies_loaded=len(companies),
    )
