"""rule-extractor pipeline package.

The pipeline turns .docx policy documents into traceable rule candidates:

    docx files  ->  spans (verbatim paragraphs)
                ->  rule candidates (each linked back to its source spans)
                ->  conflicts (pairs of candidates that contradict)

Every stage writes a plain JSON artifact under the output directory. The CLI
(`extract.py`) and the local web UI (`server.py`) are both thin wrappers over
this package — no extraction logic lives outside it.
"""

from .models import RuleCandidate, Conflict, Span, RunArtifacts, RunConfig

__all__ = ["RuleCandidate", "Conflict", "Span", "RunArtifacts", "RunConfig"]
