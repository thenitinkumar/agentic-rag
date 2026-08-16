# Earnings Intelligence Analyst

> An agentic RAG system that routes, decomposes, retrieves, and synthesizes answers over real S&P 500 earnings data — with a full inspection trace on every query.

---

## What this is

Most RAG demos do one thing: embed a query, fetch top-k chunks, stuff them into a prompt. This project replaces that single step with an **agentic reasoning layer** that decides *how* to answer before answering:

- Which source does this query actually need — structured financial data (SQL), unstructured earnings transcripts (vector), or both?
- Is this a multi-hop question that needs to be broken into ordered sub-questions before retrieval can even begin?

The pipeline then executes that plan, resolves inter-step dependencies, and synthesizes a grounded final answer — returning a full, inspectable trace of every routing decision, generated SQL query, and retrieved source along the way.

A React frontend (built to feel like a chat app, not a demo page) exposes all of this through a conversational UI where answers stream in character by character, collapsible panels reveal the reasoning trace, and the entire experience works offline with a local LLM.

---

## Architecture

```
User Question
     │
     ▼
 QueryRouter ──────────────────────────────────────────────────
     │                                                          │
     │  {"routes": ["sql","vector"],                           │
     │   "requires_decomposition": true/false,                 │
     │   "reasoning": "..."}                                   │
     │                                                          │
     ├── simple (no decomposition) ────────────────────┐       │
     │                                                  │       │
     └── complex ──► QueryDecomposer                   │       │
                          │                            │       │
                          ▼                            ▼       │
               ordered sub-questions          single question  │
               with dependency IDs            (original)       │
                          │                            │       │
                          └──────────────┬─────────────┘       │
                                         │                     │
                          for each sub-question:               │
                          ┌──────────────────────┐            │
                          │  re-route (may need  │            │
                          │  different sources   │            │
                          │  than top-level)     │            │
                          │         │            │            │
                          │   ┌─────┴──────┐     │            │
                          │   │            │     │            │
                          │  SQL       Vector    │            │
                          │ Retriever  Retriever │            │
                          │   │            │     │            │
                          │   └─────┬──────┘     │            │
                          │         │            │            │
                          │  intermediate answer │            │
                          │  (injected as context│            │
                          │   into next step)    │            │
                          └──────────────────────┘            │
                                         │                     │
                                         ▼                     │
                                    Synthesizer ───────────────┘
                                         │
                                         ▼
                              final answer + full trace
                         (routing, SQL, sources, steps)
```

---

## What makes this different from naive RAG

| Naive RAG | Earnings Intelligence |
|---|---|
| Always fetches top-k from one index | Routes each query to the source(s) it actually needs — SQL, vector, or both |
| Single retrieval pass, always | Detects multi-hop questions and decomposes them into a dependency-ordered sub-question chain before retrieval |
| SQL generation, if present at all, is unguarded | Text-to-SQL includes an explicit guardrail layer: generated SQL is validated as a single read-only `SELECT` before execution |
| Black-box output | Every run returns a full trace: routing reasoning, generated SQL, matched document sources, and each intermediate answer |
| Test coverage is an afterthought | LLM-judge evaluation harness scores faithfulness, groundedness, and source recall@k against a fixed question set |
| Tied to one LLM provider | Priority chain: Anthropic → Groq → Ollama → MockLLM. No code changes needed to switch |
| API key required to demo | `MockLLM` runs the full orchestration logic with deterministic stubs — routing, decomposition, retrieval, guardrails — no key or network needed |

---

## Tech stack

**Backend**
- Python 3.10+
- FastAPI (modular: routers / services / dependency injection)
- ChromaDB — local vector store, persisted to `data/chroma_index/`
- SQLite — structured financials, accessed via `data/company.db`
- `sentence-transformers` — local embedding model (no API key needed for indexing)
- Anthropic, Groq, Ollama — LLM backends (priority waterfall, all optional)
- Pydantic v2 — request/response schema validation
- Uvicorn — ASGI server

**Frontend**
- React 18 + Vite 5
- Zero UI framework dependencies — custom CSS with CSS custom properties
- Inter 900 display typography, monochrome design system (light + dark)
- Streaming text animation, shimmer skeleton loading, animated accordion panels

---

## Project layout

```
agentic-rag/
│
├── main.py                        # CLI: seed / ingest / ask / eval
│
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app factory (lifespan, CORS, static serving)
│   │   ├── schemas.py             # Pydantic models: QueryRequest, QueryResponse, etc.
│   │   ├── dependencies.py        # Pipeline singleton: get_pipeline(), set_pipeline()
│   │   ├── routes/
│   │   │   ├── health.py          # GET /api/health
│   │   │   ├── companies.py       # GET /api/companies
│   │   │   └── query.py           # POST /api/query
│   │   └── services/
│   │       └── data.py            # load_companies() — queries SQLite
│   │
│   └── pipeline/
│       ├── config.py              # Central settings (models, paths, thresholds)
│       ├── llm.py                 # LLMClient interface + all backends + MockLLM
│       ├── router.py              # QueryRouter: classify source(s) + decomposition need
│       ├── decomposer.py          # QueryDecomposer: multi-hop → ordered sub-questions
│       ├── retrievers.py          # VectorRetriever, SQLRetriever (text-to-SQL + guardrail)
│       ├── synthesizer.py         # Combine evidence blocks into final answer
│       ├── orchestrator.py        # AgenticRAGPipeline: ties everything together + trace
│       ├── ingestion.py           # Chunk + embed docs → Chroma index
│       ├── seed_data.py           # Fetch/generate corpus + SQLite DB
│       └── eval.py                # LLM-judge harness: faithfulness, groundedness, recall@k
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Central state machine (messages, loading, health)
│   │   ├── index.css              # Design system (tokens, animations, layout)
│   │   └── components/
│   │       ├── Topbar.jsx         # Brand + live pipeline status indicator
│   │       ├── Hero.jsx           # Empty-state landing with category pills
│   │       ├── Thread.jsx         # Message list with auto-scroll
│   │       ├── Message.jsx        # Streaming text, skeleton, animated panels
│   │       ├── InputBar.jsx       # Auto-resizing textarea with forwardRef
│   │       └── Logo.jsx           # SVG chart-mark logo (currentColor, invertible)
│   ├── index.html                 # Vite entry (loads Google Inter font)
│   ├── vite.config.js             # Dev proxy: /api → localhost:8000
│   └── dist/                      # Built output served by FastAPI StaticFiles
│
└── data/
    ├── docs/                      # Earnings call transcripts + news docs (Markdown)
    ├── company.db                 # SQLite: `financials` table, one row per company-quarter
    └── chroma_index/              # Persisted vector index (built by `ingest`)
```

---

## Data

The `data/` folder is the backbone of the pipeline. Without it, neither the SQL retriever nor the vector retriever has anything to query.

### `data/docs/` — Unstructured corpus
Markdown documents fed into ChromaDB. Includes:
- **Earnings call transcripts** for AAPL, MSFT, NVDA, META, GOOGL across 8 quarters (Q4 2024 – Q3 2026)
- **Synthetic news articles** about fictional tech companies covering outages, recalls, funding rounds, regulatory news, and partnerships — designed to require combining both SQL and vector sources to answer multi-hop questions

### `data/company.db` — Structured financials
SQLite database with a single `financials` table. Schema:

| Column | Type | Description |
|---|---|---|
| `ticker` | TEXT | Stock ticker (e.g. `AAPL`) |
| `company_name` | TEXT | Full name |
| `sector` | TEXT | e.g. Technology, Financials |
| `quarter` | TEXT | Calendar label, e.g. `Q1 2024` |
| `fiscal_year` | INTEGER | |
| `fiscal_quarter` | INTEGER | 1–4 |
| `revenue_musd` | REAL | Quarterly revenue, millions USD |
| `gross_margin_pct` | REAL | Gross margin % |
| `operating_margin_pct` | REAL | Operating margin % |
| `net_income_musd` | REAL | Net income, millions USD |
| `eps` | REAL | Earnings per share (basic) |
| `yoy_revenue_growth_pct` | REAL | Year-over-year revenue growth % |

### `data/chroma_index/` — Vector index
Built from `data/docs/` by the `ingest` command. Persisted locally — no rebuild needed between server restarts.

---

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- At least one of the following (all optional — see Mock mode):
  - `ANTHROPIC_API_KEY` — Anthropic Claude
  - `GROQ_API_KEY` — Groq (free tier at console.groq.com)
  - Ollama running locally with a model pulled

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd agentic-rag

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

The first `ingest` run will download the sentence-transformers embedding model from Hugging Face (~90 MB). This happens once and is cached locally.

### 3. Configure your LLM

Create a `.env` file in the project root. Add whichever key(s) you have — the pipeline uses the first one it finds, in priority order:

```env
# Option 1: Anthropic Claude (recommended for best results)
ANTHROPIC_API_KEY=sk-ant-...

# Option 2: Groq — free tier, fast inference
GROQ_API_KEY=gsk_...

# Option 3: Ollama — fully local, no account needed
OLLAMA_MODEL=llama3.2
# OLLAMA_BASE_URL=http://localhost:11434/v1  (default, change if needed)
```

Leave the file empty or omit it entirely to run in **Mock mode** — the full pipeline runs without any LLM calls (see below).

### 4. Build the data pipeline

```bash
# Step 1: Seed the database + docs corpus (run once)
python main.py seed

# Step 2: Chunk, embed, and index the docs into ChromaDB (run once)
python main.py ingest
```

### 5. Build the frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 6. Start the server

```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

Open `http://localhost:8000` — the React app is served directly by FastAPI from `frontend/dist/`.

---

## Running

### Web app

```bash
# Terminal 1 — backend
python -m uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — frontend dev server (optional, for hot reload during UI work)
cd frontend && npm run dev
# → opens at http://localhost:3000, proxies /api to :8000
```

### CLI

You can run the pipeline directly from the terminal without the web server:

```bash
# Ask a single question
python main.py ask "What did NVIDIA say about data center demand in their last earnings call?"

# Run the evaluation harness
python main.py eval
```

---

## LLM providers

The factory in `backend/pipeline/llm.py` checks for credentials in this order:

| Priority | Provider | Env var | Notes |
|---|---|---|---|
| 1 | Anthropic Claude | `ANTHROPIC_API_KEY` | Best routing + SQL generation quality |
| 2 | Groq | `GROQ_API_KEY` | Free tier at console.groq.com, fast inference |
| 3 | Ollama | `OLLAMA_MODEL` | Fully local, no account needed — pull a model first |
| 4 | MockLLM | *(none)* | Deterministic stubs, no network access |

**Ollama quick start:**
```bash
# Install from https://ollama.com, then:
ollama pull llama3.2
# Set in .env:
# OLLAMA_MODEL=llama3.2
```

---

## Mock mode

When no API key is configured (or `RAG_MOCK_LLM=1` is set), the pipeline runs with `MockLLM` — a deterministic, rule-based stub that produces well-formed output for every pipeline step:

- The **routing, decomposition, retrieval, guardrails, and orchestration** all run for real
- Only the LLM steps (route classification, SQL generation, answer synthesis) are replaced with keyword-heuristic stubs
- The test suite (`pytest -q`) runs entirely in mock mode — no API key or network needed
- Swap in a real key at any time; no code changes required

---

## API reference

The FastAPI server exposes three endpoints under `/api`:

### `GET /api/health`

Returns pipeline readiness and configuration status.

```json
{
  "status": "ok",
  "mock_llm": false,
  "vector_index_ready": true,
  "companies_loaded": 47
}
```

### `GET /api/companies`

Lists all companies available in the financial database.

```json
[
  { "ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "quarters_available": 8 },
  { "ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology", "quarters_available": 8 }
]
```

### `POST /api/query`

Runs the full agentic pipeline on a question. Returns the answer, the reasoning trace, and all retrieved evidence.

**Request:**
```json
{ "question": "Compare Apple and Microsoft operating margins over the last two quarters" }
```

**Response:**
```json
{
  "answer": "Apple maintained an operating margin of 31.2% in Q2 2026...",
  "decomposed": false,
  "routing_reasoning": "Requires structured financial data (margins) → routed to SQL only.",
  "steps": [
    {
      "id": "sq1",
      "question": "Compare Apple and Microsoft operating margins...",
      "routes": ["sql"],
      "intermediate_answer": "...",
      "sources": [],
      "sql": "SELECT ticker, quarter, operating_margin_pct FROM financials WHERE ticker IN ('AAPL','MSFT') ORDER BY fiscal_year DESC, fiscal_quarter DESC LIMIT 4;"
    }
  ],
  "all_sources": ["aapl_Q2_2026_transcript.md"],
  "all_sql": ["SELECT ticker, ..."]
}
```

---

## How the pipeline works

### 1. Query routing

Every question is classified by `QueryRouter` into a routing decision:

- **`sql`** — structured facts: revenue, margins, EPS, headcount, fiscal year comparisons
- **`vector`** — unstructured context: what executives said, strategic guidance, product launches, incidents
- **`both`** — multi-source questions that need financial data *and* narrative context
- **`requires_decomposition`** — true when answering requires first resolving one condition and then using its result to look up something else (multi-hop)

The router fails safe: if the LLM output can't be parsed as valid JSON, it defaults to broad retrieval across both sources rather than crashing.

### 2. Query decomposition

If `requires_decomposition` is true, `QueryDecomposer` breaks the question into an ordered chain of sub-questions with explicit dependency IDs. Each sub-question declares which earlier answers it depends on, and the orchestrator injects those intermediate answers as context before the next retrieval step.

Example:
> *"Which companies founded before 2015 had a product recall, and what was their revenue that quarter?"*

Decomposes into:
1. `sq1`: Which companies in the database were founded before 2015? → SQL
2. `sq2`: Which of {sq1 results} had a product recall? → Vector
3. `sq3`: What was the quarterly revenue for {sq2 results}? → SQL

### 3. SQL retrieval with guardrails

`SQLRetriever` asks the LLM to translate the sub-question into SQL, then validates it before execution:

- Must start with `SELECT` (single statement)
- Must not contain `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, or `PRAGMA`
- Executed against a read-only SQLite connection

If validation fails, the retriever returns an error string in the trace rather than executing the query.

### 4. Vector retrieval

`VectorRetriever` embeds the sub-question using a local sentence-transformers model and queries ChromaDB for the top-k most similar chunks from `data/docs/`. Results carry source filenames and similarity scores.

### 5. Synthesis

After all sub-questions are answered, `Synthesizer` receives all evidence blocks (SQL results + document chunks) and the original query, and produces a final grounded answer in natural language.

### 6. Trace

The `PipelineTrace` returned by every pipeline run contains:
- Top-level routing decision (routes chosen, reasoning, decomposition flag)
- Each step's sub-question, re-routing decision, retrieved evidence, and intermediate answer
- The final answer
- All SQL queries executed and all document sources matched

The UI exposes this as collapsible panels (Sources, SQL, Reasoning) on every answer card.

---

## Evaluation

```bash
python main.py eval
```

`eval.py` runs a fixed question set through the full pipeline and scores each answer using an LLM judge on two dimensions:

| Metric | What it measures |
|---|---|
| **Faithfulness** | Does the answer stay within what the retrieved evidence actually says? |
| **Groundedness** | Is every factual claim in the answer supported by a specific retrieved source? |
| **Source recall@k** | Did the vector retriever surface the expected source documents? |

The evaluation harness also runs in mock mode — the judge stub returns a fixed score so the harness structure can be tested without API credits.

---

## Design notes

**Guardrailed text-to-SQL** — Generated SQL is validated against an allowlist pattern before execution. Minimal but real: it prevents the most obvious LLM-generated destructive queries without requiring a full SQL parser or sandbox.

**Fail-safe parsing everywhere** — Router and decomposer JSON parsing failures degrade gracefully (broad retrieval / treat-as-single-question) rather than propagating exceptions up the stack.

**Linear-chain decomposition** — Sub-questions form a dependency-ordered chain, not an arbitrary DAG. This covers the realistic multi-hop case (resolve entities → look up something about them) while staying simple enough to read from the trace.

**Swappable backends** — `LLMClient` is an abstract base class with a single `complete()` method. Adding a new provider means implementing one method; no changes to routing, decomposition, or orchestration.

**Evaluation is a first-class citizen** — Most portfolio RAG projects stop at "it returned an answer." The eval harness here measures whether that answer is actually faithful to the retrieved evidence — the part that matters in production.

---

## Known limitations

- Decomposition produces a single-level linear chain, not a general dependency graph. Deeply nested multi-hop questions (more than 3–4 levels) may not decompose optimally.
- The SQL guardrail uses a regex allowlist, not a proper SQL parser or sandbox. Sufficient for a demo; not a replacement for row-level security in a production deployment.
- `WebRetriever` is a stub — the retriever interface is pluggable, but web search is not wired into the router by default.
- Embedding model download requires network access to Hugging Face on first run. Subsequent runs use the local cache.
- The vector index must be rebuilt (`python main.py ingest`) whenever `data/docs/` changes.
