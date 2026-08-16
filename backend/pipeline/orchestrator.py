"""
The agentic orchestrator. This is the piece that makes this "agentic RAG"
rather than "RAG": for each query it decides a plan (route, and whether to
decompose), executes that plan step by step -- resolving dependencies
between sub-questions -- and returns both the final answer and a full,
inspectable trace of every decision and retrieval along the way.

    query
      -> QueryRouter.route()                 (decide sources + decompose?)
      -> [if complex] QueryDecomposer.decompose()
      -> for each (sub)question, in dependency order:
            - re-route it individually (a sub-question may need only one source)
            - retrieve from the chosen source(s)
            - produce an intermediate grounded answer
      -> Synthesizer.synthesize()             (combine into final answer)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .decomposer import QueryDecomposer, SubQuestion
from .llm import LLMClient, get_llm_client
from .retrievers import RetrievalResult, SQLRetriever, VectorRetriever
from .router import QueryRouter, RoutingDecision
from .synthesizer import EvidenceBlock, Synthesizer

INTERMEDIATE_ANSWER_SYSTEM_PROMPT = """Answer the sub-question using only the
retrieved evidence provided. Be concise (2-4 sentences). If the evidence
doesn't answer it, say so explicitly.
"""


@dataclass
class StepTrace:
    subquestion_id: str
    question: str
    routing: RoutingDecision
    retrievals: List[RetrievalResult] = field(default_factory=list)
    intermediate_answer: str = ""


@dataclass
class PipelineTrace:
    original_query: str
    top_level_routing: RoutingDecision
    decomposed: bool
    steps: List[StepTrace] = field(default_factory=list)
    final_answer: str = ""

    def pretty(self) -> str:
        lines = [f"QUERY: {self.original_query}", ""]
        lines.append(f"[router] routes={self.top_level_routing.routes} "
                      f"decompose={self.top_level_routing.requires_decomposition}")
        lines.append(f"[router] reasoning: {self.top_level_routing.reasoning}")
        lines.append("")
        for step in self.steps:
            lines.append(f"--- sub-question {step.subquestion_id}: {step.question}")
            lines.append(f"    routes={step.routing.routes}")
            for r in step.retrievals:
                if r.route == "sql":
                    lines.append(f"    [sql] query: {r.generated_sql or '(none)'}"
                                 + (f"  ERROR: {r.error}" if r.error else ""))
                else:
                    src_list = ", ".join(sorted({c.source for c in r.chunks})) or "(none)"
                    lines.append(f"    [vector] matched sources: {src_list}"
                                 + (f"  ERROR: {r.error}" if r.error else ""))
            lines.append(f"    intermediate answer: {step.intermediate_answer}")
            lines.append("")
        lines.append("=== FINAL ANSWER ===")
        lines.append(self.final_answer)
        return "\n".join(lines)


class AgenticRAGPipeline:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or get_llm_client()
        self.router = QueryRouter(self.llm)
        self.decomposer = QueryDecomposer(self.llm)
        self.synthesizer = Synthesizer(self.llm)
        self.vector_retriever = VectorRetriever()
        self.sql_retriever = SQLRetriever(self.llm)

    def _retrieve_for_routes(self, question: str, routes: List[str]) -> List[RetrievalResult]:
        results = []
        if "sql" in routes:
            results.append(self.sql_retriever.retrieve(question))
        if "vector" in routes:
            results.append(self.vector_retriever.retrieve(question))
        return results

    def _answer_subquestion(self, question: str, retrievals: List[RetrievalResult]) -> str:
        context = "\n\n".join(r.as_context_block() for r in retrievals)
        user = f"SUB-QUESTION: {question}\n\nRETRIEVED EVIDENCE:\n{context}"
        return self.llm.complete(system=INTERMEDIATE_ANSWER_SYSTEM_PROMPT, user=user, max_tokens=400)

    def run(self, query: str) -> PipelineTrace:
        top_routing = self.router.route(query)
        trace = PipelineTrace(
            original_query=query,
            top_level_routing=top_routing,
            decomposed=top_routing.requires_decomposition,
        )

        if not top_routing.requires_decomposition:
            subqs = [SubQuestion(id="sq1", question=query, depends_on=[])]
        else:
            subqs = self.decomposer.decompose(query)

        answers: Dict[str, str] = {}
        evidence_blocks: List[EvidenceBlock] = []

        for sq in subqs:
            resolved_question = sq.question
            for dep_id in sq.depends_on:
                if dep_id in answers:
                    resolved_question += f" (result of {dep_id}: {answers[dep_id]})"

            sq_routing = (top_routing if not top_routing.requires_decomposition
                          else self.router.route(resolved_question))
            retrievals = self._retrieve_for_routes(resolved_question, sq_routing.routes)
            intermediate = self._answer_subquestion(resolved_question, retrievals)
            answers[sq.id] = intermediate

            for r in retrievals:
                evidence_blocks.append(EvidenceBlock(
                    label=f"{sq.id} [{r.route}]",
                    content=r.as_context_block(),
                ))

            trace.steps.append(StepTrace(
                subquestion_id=sq.id,
                question=resolved_question,
                routing=sq_routing,
                retrievals=retrievals,
                intermediate_answer=intermediate,
            ))

        trace.final_answer = self.synthesizer.synthesize(query, evidence_blocks)
        return trace
