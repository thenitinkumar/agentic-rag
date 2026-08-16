"""
Thin LLM client wrapper.

Implementations behind one interface (`LLMClient.complete`):
  - AnthropicLLM       — Anthropic Claude (ANTHROPIC_API_KEY)
  - OpenAICompatibleLLM — any OpenAI-compatible endpoint, covers:
        Groq  (GROQ_API_KEY)  — free tier at console.groq.com
        Ollama (OLLAMA_MODEL) — fully local, no account needed
  - MockLLM            — deterministic stub, no API key required

Priority in get_llm_client():
  ANTHROPIC_API_KEY → GROQ_API_KEY → OLLAMA_MODEL → MockLLM
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


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicLLM(LLMClient):
    def __init__(self, api_key: str, model: str):
        import anthropic
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


# ---------------------------------------------------------------------------
# OpenAI-compatible (Groq, Ollama, Together, etc.)
# ---------------------------------------------------------------------------

class OpenAICompatibleLLM(LLMClient):
    """
    Works with any OpenAI-compatible /v1/chat/completions endpoint.

    Groq  — base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY
    Ollama — base_url="http://localhost:11434/v1",      api_key="ollama"
    """

    def __init__(self, model: str, base_url: str, api_key: str):
        from openai import OpenAI
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Mock (no API key required)
# ---------------------------------------------------------------------------

class MockLLM(LLMClient):
    """
    Rule-based stand-in used when RAG_MOCK_LLM=1 or no API key is configured.
    Returns well-formed, task-shaped output so the orchestration logic runs
    end-to-end without any network access or API cost.
    """

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        task = self._detect_task(system)
        if task == "route":       return self._mock_route(user)
        if task == "decompose":   return self._mock_decompose(user)
        if task == "sql":         return self._mock_sql(user)
        if task == "synthesize":  return self._mock_synthesize(user)
        if task == "judge":       return self._mock_judge(user)
        if task == "intermediate":return self._mock_intermediate(user)
        return "[mock-llm] no rule matched for this task."

    @staticmethod
    def _detect_task(system: str) -> str:
        s = system.lower()
        if "classify" in s and "route" in s:    return "route"
        if "decompose" in s:                     return "decompose"
        if "synthesize" in s or "final" in s:   return "synthesize"
        if "judge" in s or "faithfulness" in s: return "judge"
        if "answer the sub-question" in s:       return "intermediate"
        if "translate" in s and "sql" in s:      return "sql"
        return "unknown"

    @staticmethod
    def _mock_route(user: str) -> str:
        q = user.lower()
        needs_sql    = any(k in q for k in ["revenue", "margin", "eps", "growth", "income", "how many", "sector"])
        needs_vector = any(k in q for k in ["said", "call", "transcript", "announce", "why", "strategy", "guidance"])
        is_multihop  = (" and " in q or "which" in q) and needs_sql and needs_vector
        routes = []
        if needs_sql:               routes.append("sql")
        if needs_vector or not routes: routes.append("vector")
        return json.dumps({
            "routes": routes,
            "requires_decomposition": is_multihop,
            "reasoning": "[mock] keyword heuristic: financial terms -> sql, narrative terms -> vector.",
        })

    @staticmethod
    def _mock_decompose(user: str) -> str:
        m = re.search(r"QUESTION:\s*(.+)", user, re.IGNORECASE | re.DOTALL)
        q = m.group(1).strip() if m else user.strip()
        return json.dumps({"subquestions": [
            {"id": "sq1", "question": f"What structured financial data is relevant to: {q}", "depends_on": []},
            {"id": "sq2", "question": f"What do earnings call transcripts say about: {q}",  "depends_on": ["sq1"]},
        ]})

    @staticmethod
    def _mock_sql(user: str) -> str:
        q = user.lower()
        if "revenue" in q or "growth" in q:
            return "SELECT ticker, company_name, sector, quarter, revenue_musd, yoy_revenue_growth_pct FROM financials ORDER BY revenue_musd DESC LIMIT 10;"
        if "margin" in q:
            return "SELECT ticker, company_name, quarter, gross_margin_pct, operating_margin_pct FROM financials ORDER BY operating_margin_pct DESC LIMIT 10;"
        if "eps" in q:
            return "SELECT ticker, company_name, quarter, eps FROM financials ORDER BY eps DESC LIMIT 10;"
        return "SELECT ticker, company_name, sector, quarter, revenue_musd FROM financials LIMIT 10;"

    @staticmethod
    def _mock_intermediate(user: str) -> str:
        return ("[mock-llm] Summarized from retrieved evidence. "
                "Set a real API key in .env for a grounded natural-language answer.")

    @staticmethod
    def _mock_synthesize(user: str) -> str:
        return ("[mock-llm] Combined answer from SQL rows and document snippets. "
                "Set a real API key in .env for a full natural-language synthesis.")

    @staticmethod
    def _mock_judge(user: str) -> str:
        return json.dumps({"faithfulness": 0.8, "groundedness": 0.8,
                           "notes": "[mock] static placeholder score."})


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    if SETTINGS.mock_llm:
        return MockLLM()

    if SETTINGS.anthropic_api_key:
        return AnthropicLLM(api_key=SETTINGS.anthropic_api_key, model=SETTINGS.llm_model)

    if SETTINGS.groq_api_key:
        return OpenAICompatibleLLM(
            model=SETTINGS.groq_model,
            base_url="https://api.groq.com/openai/v1",
            api_key=SETTINGS.groq_api_key,
        )

    if SETTINGS.ollama_model:
        return OpenAICompatibleLLM(
            model=SETTINGS.ollama_model,
            base_url=SETTINGS.ollama_base_url,
            api_key="ollama",
        )

    return MockLLM()
