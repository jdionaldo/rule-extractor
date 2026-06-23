#!/usr/bin/env python3
"""rule-extractor — local CLI.

Run the full pipeline entirely on your machine. The only outbound network call
is to the chosen LLM provider (and none at all with `--backend ollama`).

Examples
--------
    # Anthropic backend (default). Needs ANTHROPIC_API_KEY.
    python extract.py --input ./docs --out ./output

    # Fully offline with a local Ollama model.
    python extract.py --input ./docs --out ./output --backend ollama --model llama3.1

    # Process only the first 3 documents.
    python extract.py --input ./docs --out ./output --limit 3
"""

from __future__ import annotations

import argparse
import sys

from llm import LLMError
from pipeline.models import RunConfig
from pipeline.runner import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract traceable rule candidates from .docx documents.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--input",
        required=True,
        help="Path to a .docx file or a directory of .docx files.",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Directory to write JSON artifacts (spans, candidates, conflicts).",
    )
    p.add_argument(
        "--backend",
        choices=["anthropic", "ollama"],
        default="anthropic",
        help="LLM backend. 'ollama' runs fully offline.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Model id. Defaults: anthropic=claude-opus-4-8, ollama=llama3.1.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of documents to process.",
    )
    p.add_argument(
        "--no-conflicts",
        action="store_true",
        help="Skip the conflict-detection stage.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = RunConfig(
        input=args.input,
        out=args.out,
        backend=args.backend,
        model=args.model
        or ("claude-opus-4-8" if args.backend == "anthropic" else "llama3.1"),
        limit=args.limit,
        detect_conflicts=not args.no_conflicts,
    )

    try:
        run = run_pipeline(config, progress=lambda msg: print(msg, flush=True))
    except (LLMError, FileNotFoundError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1

    print(
        f"\nDone. {run.candidate_count} rule(s), "
        f"{run.conflict_count} conflict(s) from {len(run.docs)} document(s)."
    )
    print(f"Browse the results with: python server.py  (then open the output dir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
