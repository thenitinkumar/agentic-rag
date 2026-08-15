#!/usr/bin/env python3
"""
CLI entrypoint for the agentic RAG pipeline.

Usage:
    python main.py seed              # generate demo docs + SQLite DB
    python main.py ingest            # build the vector index from data/docs
    python main.py ask "question"    # run the full agentic pipeline
    python main.py eval              # run the eval harness against a small labeled set
"""
import argparse
import sys

from src.config import SETTINGS
from src.ingestion import build_vector_index
from src.seed_data import seed_all


def cmd_seed(_args):
    seed_all()


def cmd_ingest(_args):
    n = build_vector_index()
    print(f"Indexed {n} chunks.")


def cmd_ask(args):
    from src.orchestrator import AgenticRAGPipeline
    if SETTINGS.mock_llm:
        print("[note] No ANTHROPIC_API_KEY found (or RAG_MOCK_LLM=1) -- running with "
              "the deterministic MockLLM. Routing/decomposition logic still runs for "
              "real; only the language-model calls are stubbed. Set ANTHROPIC_API_KEY "
              "for real model output.\n", file=sys.stderr)
    pipeline = AgenticRAGPipeline()
    trace = pipeline.run(args.question)
    print(trace.pretty())


def cmd_eval(_args):
    from src.orchestrator import AgenticRAGPipeline
    from src.eval import run_eval, print_report
    pipeline = AgenticRAGPipeline()
    results = run_eval(pipeline)
    print_report(results)


def main():
    parser = argparse.ArgumentParser(description="Agentic RAG pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Generate demo documents + SQLite DB").set_defaults(func=cmd_seed)
    sub.add_parser("ingest", help="Build the vector index").set_defaults(func=cmd_ingest)

    ask_parser = sub.add_parser("ask", help="Ask a question through the pipeline")
    ask_parser.add_argument("question", type=str)
    ask_parser.set_defaults(func=cmd_ask)

    sub.add_parser("eval", help="Run the evaluation harness").set_defaults(func=cmd_eval)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
