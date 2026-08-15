"""
Tests target the parts of the pipeline that don't require downloading an
embedding model or hitting a real LLM API (network-restricted / no-API-key
environments, like CI, should still be able to prove the plumbing works).

Run: pytest -q
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["RAG_MOCK_LLM"] = "1"

from src.ingestion import split_text, load_documents  # noqa: E402
from src.seed_data import seed_all, COMPANIES, ARTICLES  # noqa: E402
from src.llm import MockLLM  # noqa: E402
from src.router import QueryRouter  # noqa: E402
from src.decomposer import QueryDecomposer  # noqa: E402
from src.retrievers import SQLRetriever  # noqa: E402
from src.config import SQLITE_PATH, DOCS_DIR  # noqa: E402


def setup_module(_module):
    seed_all()


def test_seed_creates_docs_and_db():
    assert SQLITE_PATH.exists()
    md_files = list(DOCS_DIR.glob("*.md"))
    assert len(md_files) == len(ARTICLES)

    conn = sqlite3.connect(SQLITE_PATH)
    rows = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    assert rows == len(COMPANIES)


def test_split_text_respects_chunk_size_roughly():
    long_text = ("Paragraph one. " * 20 + "\n\n") + ("Paragraph two. " * 20 + "\n\n") + ("Paragraph three. " * 20)
    chunks = split_text(long_text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) >= 2
    # allow slack for overlap being appended
    assert all(len(c) <= 260 for c in chunks)


def test_split_text_handles_short_text():
    chunks = split_text("Just one short paragraph.", chunk_size=800, chunk_overlap=100)
    assert chunks == ["Just one short paragraph."]


def test_load_documents_extracts_titles():
    docs = load_documents()
    assert len(docs) == len(ARTICLES)
    titles = {d["title"] for d in docs}
    assert any("Nimbusly" in t for t in titles)


def test_sql_retriever_generates_and_executes_valid_sql():
    llm = MockLLM()
    retriever = SQLRetriever(llm)
    result = retriever.retrieve("What is the revenue of each company?")
    assert result.error is None
    assert result.generated_sql.strip().lower().startswith("select")
    assert len(result.chunks) > 0


def test_sql_retriever_rejects_unsafe_sql(monkeypatch):
    llm = MockLLM()
    retriever = SQLRetriever(llm)
    monkeypatch.setattr(retriever, "_generate_sql", lambda q: "DROP TABLE companies;")
    result = retriever.retrieve("anything")
    assert result.error is not None
    assert result.chunks == []


def test_router_routes_structured_query_to_sql():
    router = QueryRouter(MockLLM())
    decision = router.route("What is Nimbusly's revenue and founded year?")
    assert "sql" in decision.routes


def test_router_routes_news_query_to_vector():
    router = QueryRouter(MockLLM())
    decision = router.route("Why did Nimbusly have an outage recently?")
    assert "vector" in decision.routes


def test_router_flags_multihop_for_decomposition():
    router = QueryRouter(MockLLM())
    decision = router.route(
        "Which companies founded before 2015 had a recall, and what was their revenue?"
    )
    assert decision.requires_decomposition is True


def test_decomposer_produces_ordered_subquestions_with_dependencies():
    decomposer = QueryDecomposer(MockLLM())
    subqs = decomposer.decompose(
        "Which companies founded before 2015 had a recall, and what was their revenue?"
    )
    assert len(subqs) >= 1
    ids = [sq.id for sq in subqs]
    for sq in subqs:
        for dep in sq.depends_on:
            assert dep in ids[: ids.index(sq.id)]  # dependency must come earlier


def test_decomposer_fails_safe_on_garbage_llm_output(monkeypatch):
    llm = MockLLM()
    monkeypatch.setattr(llm, "complete", lambda **kwargs: "not json at all")
    decomposer = QueryDecomposer(llm)
    subqs = decomposer.decompose("some query")
    assert len(subqs) == 1
    assert subqs[0].question == "some query"
