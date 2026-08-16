from fastapi import APIRouter

from ..schemas import CompanyOut
from ..services.data import load_companies

router = APIRouter()


@router.get("/companies", response_model=list[CompanyOut], tags=["data"])
def companies():
    return load_companies()
