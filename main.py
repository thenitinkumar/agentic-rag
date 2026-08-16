#!/usr/bin/env python3
"""
CLI entrypoint for the Earnings Intelligence pipeline.

Usage:
    python main.py seed              # fetch real S&P 500 data + build SQLite DB
    python main.py ingest            # build the vector index from data/docs/
    python main.py ask "question"    # run the full agentic pipeline
    python main.py eval              # run the eval harness

Server:
    python -m uvicorn backend.app.main:app --reload --port 8000
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from backend.pipeline.config import SETTINGS
from backend.pipeline.ingestion import build_vector_index
from backend.pipeline.seed_data import seed_all


def cmd_seed(_args):
    seed_all()


def cmd_ingest(_args):
    n = build_vector_index()
    print(f"Indexed {n} chunks.")


def cmd_ask(args):
    from backend.pipeline.orchestrator import AgenticRAGPipeline
    if SETTINGS.mock_llm:
        print(
            "[note] No ANTHROPIC_API_KEY found — running with MockLLM.\n"
            "Set ANTHROPIC_API_KEY in .env for real model output.\n",
            file=sys.stderr,
        )
    pipeline = AgenticRAGPipeline()
    trace = pipeline.run(args.question)
    print(trace.pretty())


def cmd_eval(_args):
    from backend.pipeline.orchestrator import AgenticRAGPipeline
    from backend.pipeline.eval import run_eval, print_report
    pipeline = AgenticRAGPipeline()
    results = run_eval(pipeline)
    print_report(results)


def main():
    parser = argparse.ArgumentParser(description="Earnings Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Fetch S&P 500 financials + build SQLite DB").set_defaults(func=cmd_seed)
    sub.add_parser("ingest", help="Build the vector index from data/docs/").set_defaults(func=cmd_ingest)

    ask_parser = sub.add_parser("ask", help="Ask a question through the pipeline")
    ask_parser.add_argument("question", type=str)
    ask_parser.set_defaults(func=cmd_ask)

    sub.add_parser("eval", help="Run the evaluation harness").set_defaults(func=cmd_eval)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
