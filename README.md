# Agentic RAG: Query Routing & Decomposition

A RAG pipeline that goes beyond "embed query → top-k retrieve → generate" by
adding an **agentic layer** that decides, per query:

1. **Which source(s)** to retrieve from — a vector store of unstructured
   documents, a SQL database of structured facts, or both.
2. **Whether the query needs decomposition** — some questions require
   resolving one condition before answering the next part (multi-hop),
   rather than a single retrieval pass.

It then executes that plan step by step, carrying answers from earlier
sub-questions into later ones, and synthesizes a final grounded answer —
returning a full, inspectable trace of every routing decision and
retrieval along the way.

```
query
  │
  ▼
QueryRouter ──────► routes: [sql | vector], requires_decomposition?
  │
  ├─ simple ─────────────────────────────┐
  │                                      │
  └─ complex ──► QueryDecomposer         │
                   │                     │
                   ▼                     ▼
        ordered sub-questions   single "sub-question"
        (with dependencies)     (the original query)
                   │                     │
                   └──────────┬──────────┘
                              ▼
            for each sub-question (dependency order):
              - re-route individually
              - retrieve (VectorRetriever and/or SQLRetriever)
              - generate an intermediate grounded answer
                              │
                              ▼
                         Synthesizer ──► final answer + trace
```

## Why this is more than a tutorial RAG demo

| Naive RAG | This pipeline |
|---|---|
| Always retrieves top-k from one index | Routes each query to the source(s) it actually needs |
| Single retrieval pass | Decomposes multi-hop questions into a dependency-ordered sub-question chain |
| Free-text SQL generation, if any | Text-to-SQL with an explicit guardrail (single read-only `SELECT`, forbidden-keyword check) before execution |
| "It returned an answer" = done | Includes an LLM-judge eval harness scoring faithfulness/groundedness + retrieval recall@k |
| Black-box output | Every run returns a full trace: routing reasoning, generated SQL, matched doc sources, intermediate answers |

## Demo dataset

To make this runnable out of the box, `seed` generates a small synthetic
corpus with **deliberate overlap** between two sources, so realistic
multi-hop questions require combining both:

- `data/docs/*.md` — 9 short news-style articles about 8 fictional tech
  companies (outages, recalls, funding, regulatory news, etc.)
- `data/company.db` — a SQLite `companies` table with matching structured
  data (revenue, employees, founded year, sector, headquarters)

Example multi-hop question this enables:
> "Which companies founded before 2015 had a recall or outage, and what is their revenue?"

— answering this requires the SQL retriever (founded year, revenue) *and*
the vector retriever (which companies had a recall/outage), combined.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # optional, see "Mock mode" below

python main.py seed      # generate demo docs + SQLite DB
python main.py ingest    # chunk + embed docs into a local Chroma index
python main.py ask "Which companies founded before 2015 had a recall or outage, and what is their revenue?"
python main.py eval      # run the LLM-judge evaluation harness
```

## Mock mode (no API key required)

If `ANTHROPIC_API_KEY` is not set (or `RAG_MOCK_LLM=1` is exported), the
pipeline runs against a deterministic `MockLLM` instead of a real model call.
**The routing, decomposition, retrieval, and orchestration logic all still
run for real** — only the language-model steps (classification reasoning,
SQL generation, final synthesis) are replaced with simple rule-based stubs.
This means:

- The full test suite (`pytest -q`) runs without any API key or network access.
- You can inspect and demo the *architecture* (routing decisions,
  sub-question dependency chains, guardrails) without spending API credits.
- Swap in a real key at any time to see actual model-generated routing,
  SQL, and synthesis — no code changes needed.

## Project layout

```
src/
  config.py        # central settings (models, paths, thresholds)
  llm.py            # LLM client interface: AnthropicLLM + MockLLM
  seed_data.py       # generates the demo corpus + SQLite DB
  ingestion.py       # chunking + embedding + Chroma index build
  retrievers.py      # VectorRetriever, SQLRetriever (text-to-SQL + guardrails), WebRetriever stub
  router.py          # QueryRouter: decide source(s) + decomposition need
  decomposer.py      # QueryDecomposer: multi-hop -> ordered sub-questions
  synthesizer.py      # combine intermediate answers into a final answer
  orchestrator.py      # AgenticRAGPipeline: ties it all together + full trace
  eval.py             # LLM-judge harness: faithfulness, groundedness, source recall@k
main.py                # CLI: seed / ingest / ask / eval
tests/test_pipeline.py  # unit tests using MockLLM (no network/API key needed)
```

## Design notes / things to point to in an interview

- **Guardrailed text-to-SQL**: generated SQL is validated (must be a single
  `SELECT`, forbidden-keyword check for `INSERT`/`DROP`/etc.) before
  execution — a minimal but real safety layer for LLM-generated queries
  against a live database.
- **Fail-safe parsing everywhere**: router and decomposer JSON parsing
  failures degrade to a sane default (broad retrieval / treat-as-single-question)
  rather than crashing the pipeline.
- **Linear-chain decomposition, not an arbitrary DAG executor**: sub-questions
  are decomposed into a dependency-ordered chain rather than a generic graph.
  This covers the realistic multi-hop case (resolve entities → look up
  something about them) while staying simple enough to debug from the trace.
- **Evaluation is a first-class citizen**: `eval.py` scores faithfulness and
  groundedness via an LLM judge, plus measures whether the vector retriever
  actually surfaced the expected source documents (recall@k) — the part most
  portfolio RAG projects skip.
- **Swappable embedding/LLM backends**: `config.py` centralizes model choices;
  `llm.py`'s `LLMClient` interface means swapping providers doesn't touch
  routing/decomposition/orchestration code.

## Known limitations (good to mention proactively)

- Decomposition is a single-level linear chain, not a general dependency DAG.
- `WebRetriever` is a stub — included to show the retriever interface is
  pluggable, not wired into the router by default.
- The SQL guardrail is a minimal allow-list (single read-only `SELECT`), not
  a full SQL parser/sandbox — sufficient for a demo, not for a
  security-critical production deployment without further hardening.
- Embedding model download (`sentence-transformers`) requires network access
  to Hugging Face at first run.
