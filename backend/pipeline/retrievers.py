"""
Retrieval backends. Each retriever exposes `.retrieve(query) -> RetrievalResult`
so the orchestrator can treat them uniformly regardless of source type.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .config import SETTINGS, CHROMA_DIR, SQLITE_PATH
from .llm import LLMClient

SQL_SCHEMA = """
Table: financials
Columns:
  ticker                  TEXT    -- stock ticker symbol, e.g. 'AAPL'
  company_name            TEXT    -- full company name, e.g. 'Apple Inc.'
  sector                  TEXT    -- e.g. 'Technology', 'Financials', 'Healthcare'
  quarter                 TEXT    -- calendar quarter label, e.g. 'Q1 2024'
  fiscal_year             INTEGER -- e.g. 2024
  fiscal_quarter          INTEGER -- 1, 2, 3, or 4
  revenue_musd            REAL    -- quarterly revenue in millions USD
  gross_margin_pct        REAL    -- gross margin as a percentage, e.g. 43.5
  operating_margin_pct    REAL    -- operating margin as a percentage, e.g. 30.1
  net_income_musd         REAL    -- quarterly net income in millions USD
  eps                     REAL    -- earnings per share (basic)
  yoy_revenue_growth_pct  REAL    -- year-over-year revenue growth %, e.g. 12.3

Each row is ONE quarter for ONE company. To compare companies, use GROUP BY or
subqueries. To find the most recent quarter, use MAX(fiscal_year, fiscal_quarter).
"""

# Only allow read-only, single-statement SELECTs against the known table --
# a minimal but real guardrail against a text-to-SQL step generating
# destructive or multi-statement SQL.
_SAFE_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|PRAGMA)\b", re.IGNORECASE)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float = 0.0


@dataclass
class RetrievalResult:
    route: str  # "vector" | "sql"
    query: str
    chunks: List[RetrievedChunk] = field(default_factory=list)
    generated_sql: str | None = None
    error: str | None = None

    def as_context_block(self) -> str:
        if self.error:
            return f"[{self.route} retrieval error: {self.error}]"
        if self.route == "sql":
            header = f"SQL executed: {self.generated_sql}\n"
            rows = "\n".join(c.text for c in self.chunks) or "(no rows returned)"
            return header + rows
        lines = [f"[{c.source}] {c.text}" for c in self.chunks]
        return "\n\n".join(lines) if lines else "(no matching chunks found)"


class VectorRetriever:
    def __init__(self, persist_dir: Path = CHROMA_DIR, top_k: int = SETTINGS.vector_top_k):
        import chromadb
        from chromadb.utils import embedding_functions

        self._top_k = top_k
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=SETTINGS.embedding_model
        )
        client = chromadb.PersistentClient(path=str(persist_dir))
        try:
            self._collection = client.get_collection("docs", embedding_function=embed_fn)
        except Exception as e:
            raise RuntimeError(
                "Vector index not found. Run `python main.py ingest` first."
            ) from e

    def retrieve(self, query: str) -> RetrievalResult:
        result = self._collection.query(query_texts=[query], n_results=self._top_k)
        chunks = []
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0] if "distances" in result else [0.0] * len(docs)
        for text, meta, dist in zip(docs, metas, dists):
            chunks.append(RetrievedChunk(text=text, source=meta.get("source", "unknown"), score=1 - dist))
        return RetrievalResult(route="vector", query=query, chunks=chunks)


class SQLRetriever:
    """Text-to-SQL retriever: asks the LLM to translate a natural-language
    question into a SELECT against the `financials` schema, validates it
    against a small allow-list of guardrails, executes it, and returns
    the rows as retrieval chunks."""

    def __init__(self, llm: LLMClient, db_path: Path = SQLITE_PATH):
        self._llm = llm
        self._db_path = db_path

    def _generate_sql(self, query: str) -> str:
        system = (
            "You translate natural-language questions into a single read-only SQL "
            "SELECT statement against the schema below. Return ONLY the SQL statement, "
            "no explanation, no markdown fences.\n" + SQL_SCHEMA
        )
        raw = self._llm.complete(system=system, user=query, max_tokens=200)
        sql = raw.strip().strip("`").strip()
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        return sql

    def _validate(self, sql: str) -> None:
        if not _SAFE_SELECT_RE.match(sql):
            raise ValueError("Generated SQL must start with SELECT.")
        if _FORBIDDEN_RE.search(sql):
            raise ValueError("Generated SQL contains a forbidden keyword.")
        if ";" in sql.strip().rstrip(";"):
            raise ValueError("Only a single SQL statement is allowed.")

    def retrieve(self, query: str) -> RetrievalResult:
        try:
            sql = self._generate_sql(query)
            self._validate(sql)
        except Exception as e:
            return RetrievalResult(route="sql", query=query, generated_sql=None, error=str(e))

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql)
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            return RetrievalResult(route="sql", query=query, generated_sql=sql, error=f"SQL execution failed: {e}")

        chunks = [RetrievedChunk(text=str(dict(row)), source="financials.db") for row in rows]
        return RetrievalResult(route="sql", query=query, chunks=chunks, generated_sql=sql)


class WebRetriever:
    """Stub extension point. In this offline demo it is not wired into the
    router by default -- included to show the retriever interface is meant
    to be pluggable (e.g. swap in a real search API in production)."""

    def retrieve(self, query: str) -> RetrievalResult:
        return RetrievalResult(
            route="web", query=query, chunks=[],
            error="WebRetriever is a stub in this demo -- plug in a real search API here.",
        )
