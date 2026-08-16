"""
Central configuration for the agentic RAG pipeline.

Everything that varies between a laptop demo and a "real" deployment
(model names, paths, thresholds) lives here so the rest of the code
never hardcodes it.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

# backend/pipeline/config.py → backend/pipeline/ → backend/ → project root
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
CHROMA_DIR = DATA_DIR / "chroma_index"
SQLITE_PATH = DATA_DIR / "company.db"


@dataclass
class Settings:
    # --- LLM ---
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    llm_model: str = os.environ.get("RAG_LLM_MODEL", "claude-sonnet-4-6")
    # If no API key is present (or RAG_MOCK_LLM=1), fall back to a deterministic
    # rule-based stub so the *plumbing* of the pipeline can be developed,
    # unit-tested, and demoed without burning API credits or requiring a key.
    mock_llm: bool = (
        os.environ.get("RAG_MOCK_LLM", "") == "1"
        or not any([
            os.environ.get("ANTHROPIC_API_KEY"),
            os.environ.get("GROQ_API_KEY"),
            os.environ.get("OLLAMA_MODEL"),
        ])
    )

    # --- Alternative LLM providers (used when ANTHROPIC_API_KEY is absent) ---
    # Groq: free tier at https://console.groq.com (14,400 req/day on Llama 3.3 70B)
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    groq_model: str = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Ollama: local inference — install from https://ollama.com then `ollama pull llama3.2`
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "")
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    # --- Data sources ---
    # Free tier at https://financialmodelingprep.com — 250 requests/day.
    # Without this key, placeholder transcript files are written; the pipeline
    # still runs but vector search returns no real transcript content.
    fmp_api_key: str = field(default_factory=lambda: os.environ.get("FMP_API_KEY", ""))

    # --- Embeddings / retrieval ---
    embedding_model: str = os.environ.get("RAG_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    chunk_size: int = 800
    chunk_overlap: int = 120
    vector_top_k: int = 4

    # --- Orchestration ---
    max_subquestions: int = 5
    max_decomposition_depth: int = 1  # sub-questions are not themselves re-decomposed

    # --- Eval ---
    eval_set_path: Path = DATA_DIR / "eval_set.json"


SETTINGS = Settings()
