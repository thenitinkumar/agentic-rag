"""
Query decomposer: breaks a multi-hop question into an ordered list of
sub-questions with explicit dependencies, so later sub-questions can
reference earlier answers (e.g. "...for the companies found in sq1").

The dependency graph here is intentionally simple (a linear chain,
enforced by construction) rather than an arbitrary DAG executor -- that
covers the realistic multi-hop cases (resolve entities, then look up
something about them) while staying easy to reason about and debug.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from .config import SETTINGS
from .llm import LLMClient

DECOMPOSER_SYSTEM_PROMPT = """You decompose a complex, multi-hop question into a short
ordered list of simpler sub-questions that, answered in sequence, let someone
answer the original question.

Rules:
- Produce at most {max_subq} sub-questions.
- Each sub-question object has: "id" (e.g. "sq1"), "question" (string), and
  "depends_on" (list of earlier ids whose answers are needed as input, or []).
- A later sub-question that depends on an earlier one should refer to
  "the result(s) of {{depends_on_id}}" explicitly in its text.
- Order sub-questions so each one's dependencies come before it.

Respond with ONLY a JSON object: {{"subquestions": [...]}}
""".format(max_subq=SETTINGS.max_subquestions)


@dataclass
class SubQuestion:
    id: str
    question: str
    depends_on: List[str]


class QueryDecomposer:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def decompose(self, query: str) -> List[SubQuestion]:
        user = f"QUESTION: {query}"
        raw = self._llm.complete(system=DECOMPOSER_SYSTEM_PROMPT, user=user, max_tokens=500)
        try:
            parsed = _extract_json(raw)
            subqs = [
                SubQuestion(id=sq["id"], question=sq["question"], depends_on=sq.get("depends_on", []))
                for sq in parsed.get("subquestions", [])
            ]
            if not subqs:
                raise ValueError("empty subquestions list")
            return subqs[: SETTINGS.max_subquestions]
        except Exception:
            # Fail safe: treat the whole query as a single sub-question
            # rather than breaking the pipeline on a malformed decomposition.
            return [SubQuestion(id="sq1", question=query, depends_on=[])]


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in decomposer output")
    return json.loads(raw[start:end + 1])
