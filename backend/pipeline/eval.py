"""
Lightweight evaluation harness.

Most portfolio RAG projects stop at "it returns an answer." This module
runs a small labeled eval set through the pipeline and scores each answer
with an LLM-as-judge for:
  - groundedness: is every claim in the answer supported by the retrieved
    evidence (vs. invented)?
  - faithfulness: does the answer avoid contradicting the evidence?

It also checks retrieval quality directly: for vector-routed questions,
did the expected source document actually get retrieved (recall@k)?

This is intentionally simple (no external eval framework) so the scoring
logic is fully visible and explainable, e.g. in an interview.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .llm import LLMClient
from .orchestrator import AgenticRAGPipeline, PipelineTrace

JUDGE_SYSTEM_PROMPT = """You are a strict judge scoring whether an answer is grounded
in and faithful to the provided evidence. Score two things from 0.0 to 1.0:
  - "faithfulness": does the answer avoid contradicting the evidence?
  - "groundedness": is every factual claim in the answer traceable to the evidence
    (no invented facts)?
Respond with ONLY JSON: {"faithfulness": 0.0-1.0, "groundedness": 0.0-1.0, "notes": "..."}
"""


@dataclass
class EvalCase:
    query: str
    expected_sources: List[str]  # doc filenames that SHOULD be retrieved, if any


@dataclass
class EvalResult:
    query: str
    final_answer: str
    faithfulness: float
    groundedness: float
    retrieved_sources: List[str]
    expected_sources: List[str]
    source_recall: Optional[float]
    judge_notes: str


DEFAULT_EVAL_SET: List[EvalCase] = [
    EvalCase(query="What happened during Nimbusly's recent outage?",
             expected_sources=["nimbusly_outage.md"]),
    EvalCase(query="What is Aviform Aerospace's revenue and why was its engine program delayed?",
             expected_sources=["aviform_delay.md"]),
    EvalCase(query="Which companies were founded before 2015, and which of those had a product recall or outage?",
             expected_sources=["nimbusly_outage.md", "verdant_recall.md", "ferrotype_supply.md"]),
    EvalCase(query="What is Solace Health AI's employee count and what did its recent regulatory news say?",
             expected_sources=["solace_fda.md"]),
]


def _judge(llm: LLMClient, trace: PipelineTrace) -> tuple[float, float, str]:
    evidence = "\n\n".join(step.intermediate_answer for step in trace.steps)
    user = f"ANSWER:\n{trace.final_answer}\n\nEVIDENCE USED:\n{evidence}"
    raw = llm.complete(system=JUDGE_SYSTEM_PROMPT, user=user, max_tokens=300)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[start:end + 1])
        return float(parsed.get("faithfulness", 0.0)), float(parsed.get("groundedness", 0.0)), parsed.get("notes", "")
    except Exception:
        return 0.0, 0.0, f"[judge parse failed] raw={raw!r}"


def run_eval(pipeline: AgenticRAGPipeline, cases: List[EvalCase] = None) -> List[EvalResult]:
    cases = cases or DEFAULT_EVAL_SET
    results = []
    for case in cases:
        trace = pipeline.run(case.query)
        retrieved = sorted({
            c.source
            for step in trace.steps
            for r in step.retrievals
            for c in r.chunks
            if r.route == "vector"
        })
        recall = None
        if case.expected_sources:
            hit = len(set(case.expected_sources) & set(retrieved))
            recall = hit / len(case.expected_sources)
        faithfulness, groundedness, notes = _judge(pipeline.llm, trace)
        results.append(EvalResult(
            query=case.query,
            final_answer=trace.final_answer,
            faithfulness=faithfulness,
            groundedness=groundedness,
            retrieved_sources=retrieved,
            expected_sources=case.expected_sources,
            source_recall=recall,
            judge_notes=notes,
        ))
    return results


def print_report(results: List[EvalResult]) -> None:
    print(f"{'query':<70} {'faith':>6} {'ground':>7} {'recall':>7}")
    print("-" * 95)
    for r in results:
        recall_str = f"{r.source_recall:.2f}" if r.source_recall is not None else "n/a"
        q = (r.query[:67] + "...") if len(r.query) > 70 else r.query
        print(f"{q:<70} {r.faithfulness:>6.2f} {r.groundedness:>7.2f} {recall_str:>7}")
    if results:
        avg_f = sum(r.faithfulness for r in results) / len(results)
        avg_g = sum(r.groundedness for r in results) / len(results)
        recalls = [r.source_recall for r in results if r.source_recall is not None]
        avg_r = sum(recalls) / len(recalls) if recalls else None
        print("-" * 95)
        print(f"{'AVERAGE':<70} {avg_f:>6.2f} {avg_g:>7.2f} {(f'{avg_r:.2f}' if avg_r is not None else 'n/a'):>7}")
