"""
Tests target the parts of the pipeline that don't require downloading an
embedding model or hitting a real LLM API (network-restricted / no-API-key
environments, like CI, should still be able to prove the plumbing works).

Run from the project root:
    pytest -q
"""
import os
import sqlite3

os.environ["RAG_MOCK_LLM"] = "1"

from backend.pipeline.ingestion import split_text, load_documents
from backend.pipeline.seed_data import seed_all
from backend.pipeline.llm import MockLLM
from backend.pipeline.router import QueryRouter
from backend.pipeline.decomposer import QueryDecomposer
from backend.pipeline.retrievers import SQLRetriever
from backend.pipeline.config import SQLITE_PATH, DOCS_DIR


def setup_module(_module):
    seed_all()


def test_seed_creates_docs_and_db():
    assert SQLITE_PATH.exists(), "SQLite DB not created by seed_all()"
    md_files = list(DOCS_DIR.glob("*.md"))
    assert len(md_files) > 0, "No markdown docs written to data/docs/"

    conn = sqlite3.connect(SQLITE_PATH)
    rows = conn.execute("SELECT COUNT(*) FROM financials").fetchone()[0]
    conn.close()
    assert rows > 0, "financials table is empty after seed_all()"


def test_split_text_respects_chunk_size_roughly():
    long_text = ("Paragraph one. " * 20 + "\n\n") * 3
    chunks = split_text(long_text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) >= 2
    assert all(len(c) <= 260 for c in chunks)


def test_split_text_handles_short_text():
    chunks = split_text("Just one short paragraph.", chunk_size=800, chunk_overlap=100)
    assert chunks == ["Just one short paragraph."]


def test_load_documents_returns_docs():
    docs = load_documents()
    assert len(docs) > 0
    for doc in docs:
        assert "source" in doc and "text" in doc


def test_sql_retriever_generates_and_executes_valid_sql():
    retriever = SQLRetriever(MockLLM())
    result = retriever.retrieve("What is the revenue of each company?")
    assert result.error is None
    assert result.generated_sql.strip().lower().startswith("select")
    assert len(result.chunks) > 0


def test_sql_retriever_rejects_unsafe_sql(monkeypatch):
    retriever = SQLRetriever(MockLLM())
    monkeypatch.setattr(retriever, "_generate_sql", lambda q: "DROP TABLE financials;")
    result = retriever.retrieve("anything")
    assert result.error is not None
    assert result.chunks == []


def test_router_routes_structured_query_to_sql():
    decision = QueryRouter(MockLLM()).route("What is Apple's revenue and EPS last quarter?")
    assert "sql" in decision.routes


def test_router_routes_narrative_query_to_vector():
    decision = QueryRouter(MockLLM()).route("What did NVIDIA say about AI demand in their call?")
    assert "vector" in decision.routes


def test_router_flags_multihop_for_decomposition():
    decision = QueryRouter(MockLLM()).route(
        "Which companies had revenue growth above 20% and what did they say about it?"
    )
    assert decision.requires_decomposition is True


def test_decomposer_produces_ordered_subquestions():
    subqs = QueryDecomposer(MockLLM()).decompose(
        "Which companies had revenue growth above 20% and what did they say about it?"
    )
    assert len(subqs) >= 1
    ids = [sq.id for sq in subqs]
    for sq in subqs:
        for dep in sq.depends_on:
            assert dep in ids[: ids.index(sq.id)]


def test_decomposer_fails_safe_on_bad_llm_output(monkeypatch):
    llm = MockLLM()
    monkeypatch.setattr(llm, "complete", lambda **kwargs: "not json at all")
    subqs = QueryDecomposer(llm).decompose("some query")
    assert len(subqs) == 1
    assert subqs[0].question == "some query"
