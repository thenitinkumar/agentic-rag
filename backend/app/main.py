"""
FastAPI application factory for the Earnings Intelligence pipeline.

Run from the project root:
    python -m uvicorn backend.app.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.pipeline.orchestrator import AgenticRAGPipeline

from .dependencies import set_pipeline
from .routes import companies, health, query

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        set_pipeline(AgenticRAGPipeline())
        print("[startup] pipeline ready")
    except RuntimeError as e:
        set_pipeline(None)
        print(f"[startup] pipeline not ready: {e}")
        print("[startup] run `python main.py ingest` then restart the server")
    yield


app = FastAPI(
    title="Earnings Intelligence API",
    description="Agentic RAG over real S&P 500 earnings data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(query.router, prefix="/api")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    print(f"[warn] Frontend not built. Run: cd frontend && npm install && npm run build")
