"""Pipeline orchestration shared by the CLI and the web UI.

`run_pipeline` is the single entry point: read docs -> extract candidates ->
detect conflicts -> write artifacts. It accepts a progress callback so callers
can stream status (the web UI) or print it (the CLI).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from llm import make_client

from . import conflicts as conflicts_mod
from . import docx_reader
from . import extractor
from .models import (
    RunArtifacts,
    RunConfig,
    utcnow_iso,
    write_artifacts,
)

Progress = Callable[[str], None]


def run_pipeline(
    config: RunConfig,
    *,
    progress: Progress = print,
) -> RunArtifacts:
    """Run the full extraction pipeline and write artifacts to ``config.out``."""
    input_path = Path(config.input)
    out_dir = Path(config.out)
    run = RunArtifacts(
        run_id=uuid.uuid4().hex[:12],
        started_at=utcnow_iso(),
        config=config,
    )

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    # 1. Read source documents into verbatim spans.
    doc_paths = docx_reader.collect_docx_paths(input_path, limit=config.limit)
    if not doc_paths:
        raise FileNotFoundError(f"No .docx files found under: {input_path}")
    progress(f"Found {len(doc_paths)} document(s)")
    run.docs = [p.name for p in doc_paths]

    spans = []
    for path in doc_paths:
        doc_spans = docx_reader.read_docx(path)
        progress(f"Read {path.name}: {len(doc_spans)} paragraph(s)")
        spans.extend(doc_spans)
    run.span_count = len(spans)

    # 2. Extract rule candidates (the only stage that needs the LLM, plus 3).
    progress(f"Using backend '{config.backend}' (model: {config.model})")
    client = make_client(config.backend, model=config.model)

    candidates = extractor.extract_candidates(spans, client, progress=progress)
    run.candidate_count = len(candidates)

    # 3. Detect conflicts between candidates.
    if config.detect_conflicts:
        conflicts = conflicts_mod.detect_conflicts(
            candidates, client, progress=progress
        )
    else:
        conflicts = []
        run.notes.append("Conflict detection skipped (--no-conflicts).")
    run.conflict_count = len(conflicts)

    # 4. Persist artifacts.
    run.finished_at = utcnow_iso()
    write_artifacts(
        out_dir,
        spans=spans,
        candidates=candidates,
        conflicts=conflicts,
        run=run,
    )
    progress(f"Wrote artifacts to {out_dir.resolve()}")
    return run
