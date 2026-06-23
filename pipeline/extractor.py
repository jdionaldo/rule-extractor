"""Rule extraction: turn Spans into traceable RuleCandidates via the LLM.

Spans are grouped per document and chunked to a manageable size. Each chunk is
sent to the model, which returns rule candidates that reference the span ids
they were derived from — preserving end-to-end traceability.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from llm import LLMClient

from .models import Modality, RuleCandidate, Span

Progress = Callable[[str], None]

# Roughly how much source text to send per LLM call. Small enough to keep the
# model focused; large enough to capture multi-paragraph rules.
CHUNK_CHAR_BUDGET = 6000

_SYSTEM = """You are a meticulous policy analyst. You extract discrete, \
enforceable rules from policy and regulatory documents.

Rules for extraction:
- Extract only rules actually stated in the provided text. Never invent rules.
- Each rule is ONE clear, self-contained sentence.
- For every rule, list the span_id(s) of the source paragraph(s) it came from.
  Only use span_ids that appear in the provided text.
- Classify modality: must, must_not, should, should_not, may.
- Where the text makes it clear, fill in actor (who must comply), condition \
(when it applies), topic (a short tag), and rationale (why).
- confidence is your 0-1 certainty that this is a real, correctly-captured rule.
- If a paragraph states no rule, produce nothing for it."""

# JSON schema for structured output. Kept within structured-output limits:
# every object sets additionalProperties:false and lists required fields.
_EXTRACTION_SCHEMA: Dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "statement": {"type": "string"},
                    "source_span_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "modality": {
                        "type": "string",
                        "enum": [
                            "must",
                            "must_not",
                            "should",
                            "should_not",
                            "may",
                        ],
                    },
                    "actor": {"type": ["string", "null"]},
                    "condition": {"type": ["string", "null"]},
                    "topic": {"type": ["string", "null"]},
                    "rationale": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "statement",
                    "source_span_ids",
                    "modality",
                    "actor",
                    "condition",
                    "topic",
                    "rationale",
                    "confidence",
                ],
            },
        }
    },
    "required": ["rules"],
}


def _chunk_spans(spans: List[Span], budget: int = CHUNK_CHAR_BUDGET) -> List[List[Span]]:
    """Group consecutive spans into chunks under a character budget."""
    chunks: List[List[Span]] = []
    current: List[Span] = []
    size = 0
    for span in spans:
        span_len = len(span.text) + len(span.span_id) + 8
        if current and size + span_len > budget:
            chunks.append(current)
            current, size = [], 0
        current.append(span)
        size += span_len
    if current:
        chunks.append(current)
    return chunks


def _render_chunk(spans: List[Span]) -> str:
    lines = [
        "Extract rules from the following paragraphs. Each is prefixed with its "
        "span_id in [brackets].\n"
    ]
    for span in spans:
        if span.heading:
            lines.append(f"(section: {span.heading})")
        lines.append(f"[{span.span_id}] {span.text}")
    return "\n".join(lines)


def _coerce_modality(value: str) -> Modality:
    value = (value or "").strip().lower().replace(" ", "_")
    if value in {"must", "must_not", "should", "should_not", "may"}:
        return value  # type: ignore[return-value]
    return "must"


def extract_candidates(
    spans: List[Span],
    client: LLMClient,
    *,
    progress: Progress = lambda _msg: None,
) -> List[RuleCandidate]:
    """Extract rule candidates from all spans, grouped per document."""
    by_doc: Dict[str, List[Span]] = {}
    for span in spans:
        by_doc.setdefault(span.doc, []).append(span)

    candidates: List[RuleCandidate] = []
    counter = 0

    for doc, doc_spans in by_doc.items():
        valid_ids = {s.span_id for s in doc_spans}
        chunks = _chunk_spans(doc_spans)
        progress(f"Extracting from {doc}: {len(chunks)} chunk(s)")
        for i, chunk in enumerate(chunks, start=1):
            progress(f"  {doc} chunk {i}/{len(chunks)}")
            result = client.generate_json(
                system=_SYSTEM,
                prompt=_render_chunk(chunk),
                schema=_EXTRACTION_SCHEMA,
            )
            for raw in result.get("rules", []):
                statement = (raw.get("statement") or "").strip()
                if not statement:
                    continue
                # Keep only span references that actually exist in this doc.
                refs = [
                    sid
                    for sid in raw.get("source_span_ids", [])
                    if sid in valid_ids
                ]
                if not refs:
                    # Fall back to the chunk's spans so the rule stays traceable.
                    refs = [s.span_id for s in chunk]
                counter += 1
                candidates.append(
                    RuleCandidate(
                        rule_id=f"R-{counter:04d}",
                        statement=statement,
                        doc=doc,
                        source_span_ids=refs,
                        modality=_coerce_modality(raw.get("modality", "must")),
                        actor=raw.get("actor") or None,
                        condition=raw.get("condition") or None,
                        topic=raw.get("topic") or None,
                        rationale=raw.get("rationale") or None,
                        confidence=float(raw.get("confidence", 0.0) or 0.0),
                    )
                )
    progress(f"Extracted {len(candidates)} candidate rule(s)")
    return candidates
