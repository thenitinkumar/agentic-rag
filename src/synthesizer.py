"""
Synthesizer: takes the original question plus the retrieved context for
each (sub)question and produces a final grounded answer, instructed to
cite which source (doc filename or SQL query) each claim comes from.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .llm import LLMClient

SYNTHESIZER_SYSTEM_PROMPT = """You are the final-answer synthesis step of a RAG pipeline.
You will be given the user's original question and a set of retrieved evidence
blocks (each labeled with its source: a document filename or an executed SQL
query). Using ONLY this evidence:

- Write a direct, concise final answer to the original question.
- Do not use outside knowledge not present in the evidence.
- If the evidence is insufficient to fully answer, say so explicitly rather
  than guessing.
- Briefly note which source(s) each key claim relies on.
"""


@dataclass
class EvidenceBlock:
    label: str
    content: str


class Synthesizer:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def synthesize(self, original_query: str, evidence: List[EvidenceBlock]) -> str:
        evidence_text = "\n\n".join(f"### {e.label}\n{e.content}" for e in evidence)
        user = f"ORIGINAL QUESTION: {original_query}\n\nEVIDENCE:\n{evidence_text}"
        return self._llm.complete(system=SYNTHESIZER_SYSTEM_PROMPT, user=user, max_tokens=800)
