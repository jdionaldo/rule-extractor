"""Pydantic data models and artifact (de)serialization.

These models are the contract between the pipeline stages and the two
front-ends. They are intentionally plain so the JSON artifacts are easy to
read, diff, and audit by hand.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Modality = Literal["must", "must_not", "should", "should_not", "may"]

# Artifact filenames written under the output directory.
SPANS_FILE = "spans.json"
CANDIDATES_FILE = "candidates.json"
CONFLICTS_FILE = "conflicts.json"
RUN_FILE = "run.json"


class Span(BaseModel):
    """A verbatim source paragraph — the unit of traceability.

    Every rule candidate points back to one or more spans so a reviewer can
    always see the exact source text a rule was derived from.
    """

    span_id: str = Field(..., description="Stable id, e.g. 'policy.docx::p0042'.")
    doc: str = Field(..., description="Source document filename.")
    index: int = Field(..., description="Zero-based running index within the doc.")
    text: str = Field(..., description="Verbatim paragraph text.")
    heading: Optional[str] = Field(
        None, description="Nearest preceding heading, for context."
    )
    location: Optional[str] = Field(
        None,
        description="Where in the source it came from, e.g. 'page 3', 'slide 2'.",
    )
    style: Optional[str] = Field(None, description="Paragraph style name, if any.")


class RuleCandidate(BaseModel):
    """A single normalized rule extracted from the source text."""

    rule_id: str = Field(..., description="Stable id, e.g. 'R-0001'.")
    statement: str = Field(..., description="The rule, as a single clear sentence.")
    doc: str = Field(..., description="Document the rule was extracted from.")
    source_span_ids: List[str] = Field(
        default_factory=list,
        description="Spans this rule was derived from (verbatim evidence).",
    )
    modality: Modality = Field(
        "must", description="Obligation strength of the rule."
    )
    actor: Optional[str] = Field(None, description="Who the rule applies to.")
    condition: Optional[str] = Field(
        None, description="When/under what circumstances the rule applies."
    )
    topic: Optional[str] = Field(None, description="Short topical tag for grouping.")
    rationale: Optional[str] = Field(
        None, description="Why the rule exists, if stated in the source."
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Extractor confidence (0–1)."
    )


class Conflict(BaseModel):
    """A pair of rule candidates that appear to contradict or overlap."""

    conflict_id: str = Field(..., description="Stable id, e.g. 'C-0001'.")
    rule_id_a: str
    rule_id_b: str
    kind: Literal[
        "contradiction", "overlap", "ambiguous_scope", "threshold_mismatch"
    ] = Field("contradiction", description="Nature of the conflict.")
    severity: Literal["high", "medium", "low"] = "medium"
    explanation: str = Field(..., description="Why these two rules conflict.")


class RunConfig(BaseModel):
    """Inputs and knobs for a single pipeline run."""

    input: str
    out: str
    backend: Literal["anthropic", "ollama"] = "anthropic"
    model: str = "claude-opus-4-8"
    limit: Optional[int] = Field(
        None, description="Max number of docs to process (None = all)."
    )
    detect_conflicts: bool = True


class RunArtifacts(BaseModel):
    """Run-level metadata written to run.json."""

    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    config: RunConfig
    docs: List[str] = Field(default_factory=list)
    span_count: int = 0
    candidate_count: int = 0
    conflict_count: int = 0
    notes: List[str] = Field(default_factory=list)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- artifact IO ------------------------------------------------------------


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_artifacts(
    out_dir: Path,
    *,
    spans: List[Span],
    candidates: List[RuleCandidate],
    conflicts: List[Conflict],
    run: RunArtifacts,
) -> None:
    _write_json(out_dir / SPANS_FILE, [s.model_dump() for s in spans])
    _write_json(out_dir / CANDIDATES_FILE, [c.model_dump() for c in candidates])
    _write_json(out_dir / CONFLICTS_FILE, [c.model_dump() for c in conflicts])
    _write_json(out_dir / RUN_FILE, run.model_dump())


def load_spans(out_dir: Path) -> List[Span]:
    path = out_dir / SPANS_FILE
    if not path.exists():
        return []
    return [Span(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def load_candidates(out_dir: Path) -> List[RuleCandidate]:
    path = out_dir / CANDIDATES_FILE
    if not path.exists():
        return []
    return [RuleCandidate(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def load_conflicts(out_dir: Path) -> List[Conflict]:
    path = out_dir / CONFLICTS_FILE
    if not path.exists():
        return []
    return [Conflict(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def load_run(out_dir: Path) -> Optional[RunArtifacts]:
    path = out_dir / RUN_FILE
    if not path.exists():
        return None
    return RunArtifacts(**json.loads(path.read_text(encoding="utf-8")))
