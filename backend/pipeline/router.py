"""
Query router: decides which retrieval source(s) a query needs, and whether
it's complex enough to require decomposition into sub-questions before
retrieval. This is the piece that turns "naive RAG" (always retrieve top-k
from one index) into "agentic RAG" (decide the retrieval strategy per query).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from .llm import LLMClient

ROUTER_SYSTEM_PROMPT = """You classify a user question into a retrieval plan.

You must decide which data sources are needed:
  - "sql": use if the question needs structured facts (revenue, employee count,
    founded year, sector, headquarters) that live in a companies database.
  - "vector": use if the question needs unstructured context (news, product
    launches, incidents, opinions, "why"/"what happened" style content) that
    lives in a document corpus.

You must also decide requires_decomposition: true if answering the question
really requires first resolving one condition (e.g. "companies founded after
2015") and then looking up something else about the *result* of that condition
(e.g. "...and what negative news did they have"). Simple single-source lookups
should have requires_decomposition: false.

Classify and route this query. Respond with ONLY a JSON object of the form:
{"routes": ["sql", "vector"], "requires_decomposition": true, "reasoning": "..."}
"""


@dataclass
class RoutingDecision:
    routes: List[str]
    requires_decomposition: bool
    reasoning: str
    raw: str = ""


class QueryRouter:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def route(self, query: str) -> RoutingDecision:
        raw = self._llm.complete(system=ROUTER_SYSTEM_PROMPT, user=query, max_tokens=300)
        try:
            parsed = _extract_json(raw)
            routes = [r for r in parsed.get("routes", []) if r in ("sql", "vector")]
            if not routes:
                routes = ["vector"]
            return RoutingDecision(
                routes=routes,
                requires_decomposition=bool(parsed.get("requires_decomposition", False)),
                reasoning=parsed.get("reasoning", ""),
                raw=raw,
            )
        except Exception:
            # Fail safe: if the router's output can't be parsed, default to a
            # broad single-hop retrieval across both sources rather than
            # crashing the whole pipeline on a formatting slip.
            return RoutingDecision(
                routes=["vector", "sql"],
                requires_decomposition=False,
                reasoning=f"[router parse failed, defaulting to broad retrieval] raw={raw!r}",
                raw=raw,
            )


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in router output")
    return json.loads(raw[start:end + 1])
