"""Read .docx files into verbatim Spans.

This stage does no interpretation — it only extracts paragraph text so that
every downstream rule can be traced back to exact source wording.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from docx import Document

from .models import Span


def _is_heading(style_name: str | None) -> bool:
    return bool(style_name) and style_name.lower().startswith(("heading", "title"))


def read_docx(path: Path) -> List[Span]:
    """Extract non-empty paragraphs from a single .docx file as Spans."""
    doc = Document(str(path))
    doc_name = path.name
    spans: List[Span] = []
    current_heading: str | None = None

    for index, para in enumerate(doc.paragraphs):
        text = (para.text or "").strip()
        if not text:
            continue
        style_name = getattr(getattr(para, "style", None), "name", None)
        if _is_heading(style_name):
            current_heading = text
        spans.append(
            Span(
                span_id=f"{doc_name}::p{index:04d}",
                doc=doc_name,
                index=index,
                text=text,
                heading=current_heading,
                style=style_name,
            )
        )
    return spans


def collect_docx_paths(input_path: Path, limit: int | None = None) -> List[Path]:
    """Resolve an input path (file or directory) to a sorted list of .docx files."""
    if input_path.is_file():
        paths = [input_path] if input_path.suffix.lower() == ".docx" else []
    else:
        paths = sorted(
            p
            for p in input_path.glob("**/*.docx")
            if not p.name.startswith("~$")  # skip Word lock files
        )
    if limit is not None:
        paths = paths[:limit]
    return paths


def read_all(input_path: Path, limit: int | None = None) -> List[Span]:
    """Read every .docx under ``input_path`` into a flat list of Spans."""
    spans: List[Span] = []
    for path in collect_docx_paths(input_path, limit=limit):
        spans.extend(read_docx(path))
    return spans
