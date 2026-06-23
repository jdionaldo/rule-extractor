"""Conflict detection across extracted rule candidates.

Given the full set of candidates, ask the model to identify pairs that
contradict, overlap, or otherwise can't both hold. Only pairs referencing real
rule_ids are kept.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Set, Tuple

from llm import LLMClient

from .models import Conflict, RuleCandidate

Progress = Callable[[str], None]

# Cap how many candidates go into a single detection call so we stay within a
# reasonable context size for both backends.
DETECTION_BATCH = 60

_SYSTEM = """You are a policy consistency reviewer. You are given a list of \
rules, each with an id. Identify pairs of rules that CONFLICT.

A conflict is when two rules cannot both be satisfied, materially overlap in a \
contradictory way, disagree on a threshold/number, or apply to the same actor \
and situation with incompatible requirements.

For each conflicting pair return both rule ids, a kind, a severity, and a one- \
sentence explanation. Do not report a rule as conflicting with itself. Do not \
invent conflicts — if rules are merely about the same topic but compatible, \
do not report them."""

_CONFLICT_SCHEMA: Dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rule_id_a": {"type": "string"},
                    "rule_id_b": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [
                            "contradiction",
                            "overlap",
                            "ambiguous_scope",
                            "threshold_mismatch",
                        ],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "explanation": {"type": "string"},
                },
                "required": [
                    "rule_id_a",
                    "rule_id_b",
                    "kind",
                    "severity",
                    "explanation",
                ],
            },
        }
    },
    "required": ["conflicts"],
}


def _render_rules(candidates: List[RuleCandidate]) -> str:
    lines = ["Rules:"]
    for c in candidates:
        meta = []
        if c.actor:
            meta.append(f"actor={c.actor}")
        if c.condition:
            meta.append(f"when={c.condition}")
        suffix = f"  ({'; '.join(meta)})" if meta else ""
        lines.append(f"[{c.rule_id}] ({c.modality}) {c.statement}{suffix}")
    return "\n".join(lines)


def _batches(candidates: List[RuleCandidate], size: int):
    for i in range(0, len(candidates), size):
        yield candidates[i : i + size]


def detect_conflicts(
    candidates: List[RuleCandidate],
    client: LLMClient,
    *,
    progress: Progress = lambda _msg: None,
) -> List[Conflict]:
    """Detect conflicting pairs among candidates."""
    if len(candidates) < 2:
        progress("Not enough rules to compare; skipping conflict detection")
        return []

    valid_ids = {c.rule_id for c in candidates}
    seen: Set[Tuple[str, str]] = set()
    conflicts: List[Conflict] = []
    counter = 0

    batches = list(_batches(candidates, DETECTION_BATCH))
    progress(f"Checking conflicts across {len(candidates)} rule(s)")
    for i, batch in enumerate(batches, start=1):
        progress(f"  conflict batch {i}/{len(batches)}")
        result = client.generate_json(
            system=_SYSTEM,
            prompt=_render_rules(batch),
            schema=_CONFLICT_SCHEMA,
        )
        for raw in result.get("conflicts", []):
            a = (raw.get("rule_id_a") or "").strip()
            b = (raw.get("rule_id_b") or "").strip()
            if a == b or a not in valid_ids or b not in valid_ids:
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            counter += 1
            conflicts.append(
                Conflict(
                    conflict_id=f"C-{counter:04d}",
                    rule_id_a=key[0],
                    rule_id_b=key[1],
                    kind=raw.get("kind", "contradiction"),
                    severity=raw.get("severity", "medium"),
                    explanation=(raw.get("explanation") or "").strip(),
                )
            )
    progress(f"Found {len(conflicts)} conflict(s)")
    return conflicts
