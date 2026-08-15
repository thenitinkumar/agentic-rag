"""
Thin LLM client wrapper.

Two implementations behind one interface (`LLMClient.complete`):
  - AnthropicLLM: real calls to the Anthropic Messages API.
  - MockLLM: deterministic, keyword-driven stand-in used when no API key is
    configured. This keeps the rest of the pipeline (router, decomposer,
    orchestrator, tests) runnable and demoable without network access or
    API cost -- useful in CI and for reviewers who just want to see the
    pipeline execute end to end.

Everything downstream depends only on `LLMClient`, never on which
implementation is active.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Optional

from .config import SETTINGS


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Return the model's raw text completion for a single-turn prompt."""
        raise NotImplementedError


class AnthropicLLM(LLMClient):
    def __init__(self, api_key: str, model: str):
        import anthropic  # imported lazily so mock mode has no hard dependency

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")


class MockLLM(LLMClient):
    """
    A rule-based stand-in for an LLM used only when RAG_MOCK_LLM=1 or no
    API key is configured. It is intentionally simple -- it is NOT trying
    to imitate model quality, only to return well-formed, task-shaped
    output so the surrounding orchestration logic can be exercised.
    """

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        task = self._detect_task(system)
        if task == "route":
            return self._mock_route(user)
        if task == "decompose":
            return self._mock_decompose(user)
        if task == "sql":
            return self._mock_sql(user)
        if task == "synthesize":
            return self._mock_synthesize(user)
        if task == "judge":
            return self._mock_judge(user)
        if task == "intermediate":
            return self._mock_intermediate(user)
        return "[mock-llm] no rule matched for this task; returning empty completion."

    @staticmethod
    def _detect_task(system: str) -> str:
        s = system.lower()
        if "classify" in s and "route" in s:
            return "route"
        if "decompose" in s:
            return "decompose"
        if "synthesize" in s or "final-answer" in s or "final answer" in s:
            return "synthesize"
        if "judge" in s or "faithfulness" in s:
            return "judge"
        if "answer the sub-question" in s:
            return "intermediate"
        if "translate" in s and "sql" in s:
            return "sql"
        return "unknown"

    @staticmethod
    def _mock_route(user: str) -> str:
        q = user.lower()
        needs_sql = any(k in q for k in ["revenue", "founded", "employees", "headquarter", "sector", "how many", "growth"])
        needs_vector = any(k in q for k in ["news", "said", "announce", "controvers", "coverage", "why", "product", "launch", "recall", "outage", "delay"])
        is_multihop = (" and " in q or "which" in q) and needs_sql and needs_vector
        routes = []
        if needs_sql:
            routes.append("sql")
        if needs_vector or not routes:
            routes.append("vector")
        return json.dumps({
            "routes": routes,
            "requires_decomposition": is_multihop,
            "reasoning": "[mock] keyword heuristic: revenue/financial terms -> sql, "
                         "news/product/opinion terms -> vector; both present -> decompose.",
        })

    @staticmethod
    def _mock_decompose(user: str) -> str:
        m = re.search(r"QUESTION:\s*(.+)", user, re.IGNORECASE | re.DOTALL)
        q = m.group(1).strip() if m else user.strip()
        subqs = [
            {"id": "sq1", "question": f"Which entities satisfy the factual/structured condition in: {q}", "depends_on": []},
            {"id": "sq2", "question": f"What do news/document sources say about the entities found in sq1, relevant to: {q}", "depends_on": ["sq1"]},
        ]
        return json.dumps({"subquestions": subqs})

    @staticmethod
    def _mock_sql(user: str) -> str:
        q = user.lower()
        if "revenue" in q:
            return "SELECT name, sector, revenue_musd, founded_year FROM companies ORDER BY revenue_musd DESC LIMIT 5;"
        if "employee" in q:
            return "SELECT name, employees FROM companies ORDER BY employees DESC LIMIT 5;"
        if "founded" in q or "sector" in q:
            return "SELECT name, sector, founded_year FROM companies;"
        return "SELECT * FROM companies LIMIT 5;"

    @staticmethod
    def _mock_intermediate(user: str) -> str:
        return ("[mock-llm intermediate answer] Summarized from the retrieved evidence above for this "
                "sub-question. (Set ANTHROPIC_API_KEY for a real, evidence-grounded natural-language answer.)")

    @staticmethod
    def _mock_synthesize(user: str) -> str:
        return ("[mock-llm synthesis] Based on the retrieved SQL rows and document snippets above, "
                "here is a combined answer. (Run with a real ANTHROPIC_API_KEY to get an actual "
                "natural-language synthesis grounded in the retrieved context.)")

    @staticmethod
    def _mock_judge(user: str) -> str:
        return json.dumps({"faithfulness": 0.8, "groundedness": 0.8,
                            "notes": "[mock] static placeholder score; use real LLM for a meaningful judge."})


def get_llm_client() -> LLMClient:
    if SETTINGS.mock_llm:
        return MockLLM()
    return AnthropicLLM(api_key=SETTINGS.anthropic_api_key, model=SETTINGS.llm_model)
