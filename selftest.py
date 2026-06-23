#!/usr/bin/env python3
"""Zero-cost self-test for the pipeline.

Runs the FULL pipeline (ingestion -> extraction -> conflict detection ->
artifacts) against a built-in fake LLM backend. No API key, no network, no
Ollama required — it just proves the plumbing works end to end and that rules
stay traceable to their source spans.

    python selftest.py
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from pipeline import runner
from pipeline.models import (
    RunConfig,
    load_candidates,
    load_conflicts,
    load_spans,
)


class _FakeLLM:
    """Deterministic stand-in for a real LLM backend (no cost, no network)."""

    model = "fake"

    def generate_json(self, *, system, prompt, schema):
        if "CONFLICT" in system:
            return {
                "conflicts": [
                    {
                        "rule_id_a": "R-0001",
                        "rule_id_b": "R-0002",
                        "kind": "contradiction",
                        "severity": "high",
                        "explanation": "fake conflict for the self-test",
                    }
                ]
            }
        # Extraction: cite the first span id seen and emit two rules per chunk
        # so the conflict-detection stage has something to compare.
        ids = re.findall(r"\[([^\]]+::\d+)\]", prompt)
        ref = [ids[0]] if ids else []
        return {
            "rules": [
                {
                    "statement": "Self-test rule A.",
                    "source_span_ids": ref,
                    "modality": "must",
                    "actor": None,
                    "condition": None,
                    "topic": "selftest",
                    "rationale": None,
                    "confidence": 0.9,
                },
                {
                    "statement": "Self-test rule B.",
                    "source_span_ids": ref,
                    "modality": "may",
                    "actor": None,
                    "condition": None,
                    "topic": "selftest",
                    "rationale": None,
                    "confidence": 0.8,
                },
            ]
        }


def main() -> int:
    # Ensure a sample document exists to ingest.
    sample_dir = Path(__file__).resolve().parent / "sample_docs"
    sample_dir.mkdir(exist_ok=True)
    if not list(sample_dir.glob("*.docx")):
        import make_sample

        make_sample.main()

    # Build an isolated input dir (docx + a second format) so the repo is
    # never touched, then run the pipeline into a temp output dir.
    work = Path(tempfile.mkdtemp())
    in_dir = work / "input"
    in_dir.mkdir()
    for docx in sample_dir.glob("*.docx"):
        shutil.copy(docx, in_dir / docx.name)
    (in_dir / "extra.txt").write_text(
        "Staff must complete security training annually.\n", encoding="utf-8"
    )
    out = work / "output"

    # Swap in the fake backend, then run exactly what the CLI/server run.
    runner.make_client = lambda backend, model=None: _FakeLLM()
    runner.run_pipeline(
        RunConfig(input=str(in_dir), out=str(out)),
        progress=lambda m: print("  " + m),
    )

    spans = load_spans(out)
    candidates = load_candidates(out)
    conflicts = load_conflicts(out)
    span_ids = {s.span_id for s in spans}

    checks = [
        ("ingested more than one format", len({s.doc for s in spans}) >= 2),
        ("spans written", len(spans) > 0),
        ("candidates written", len(candidates) > 0),
        ("conflicts written", len(conflicts) > 0),
        (
            "every rule traces to a real span",
            all(
                any(sid in span_ids for sid in c.source_span_ids)
                for c in candidates
            ),
        ),
        ("artifacts on disk", (out / "candidates.json").exists()),
    ]

    print()
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print()
    print("SELF-TEST PASSED ✓" if ok else "SELF-TEST FAILED ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
