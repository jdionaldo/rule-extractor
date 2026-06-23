#!/usr/bin/env python3
"""rule-extractor — local web UI.

A thin, localhost-only presentation layer over the SAME pipeline modules used
by the CLI. No extraction logic lives here: routes either kick off a run or
read the JSON artifacts the pipeline writes.

Run it:
    python server.py                       # binds 127.0.0.1:8765
    uvicorn server:app --host 127.0.0.1 --port 8765

Then open http://localhost:8765

Privacy: single-user local use only. Binds loopback unless --allow-lan is
passed explicitly. Uploaded docs stay under ./output/uploads; nothing is sent
anywhere except the LLM call.
"""

from __future__ import annotations

import argparse
import queue
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pipeline import ingest
from pipeline.models import (
    RunConfig,
    load_candidates,
    load_conflicts,
    load_run,
    load_spans,
)
from pipeline.runner import run_pipeline

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"

app = FastAPI(title="rule-extractor")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _common(request: Request) -> dict:
    """Context shared by every page (nav + latest-run summary)."""
    run = load_run(OUTPUT_DIR)
    return {"request": request, "run": run}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    ctx = _common(request)
    ctx["default_source"] = str((BASE_DIR / "sample_docs"))
    return templates.TemplateResponse(request, "index.html", ctx)


@app.post("/run")
async def run(
    backend: str = Form("anthropic"),
    model: str = Form(""),
    limit: str = Form(""),
    source_path: str = Form(""),
    detect_conflicts: str = Form("on"),
    files: List[UploadFile] = File(default=[]),
):
    """Run the pipeline on uploaded files (preferred) or a selected path.

    Streams progress lines back to the browser as plain text.
    """
    # Persist any uploads under ./output/uploads and use that as the input.
    valid = [
        u
        for u in files
        if u.filename and u.filename.lower().endswith(ingest.SUPPORTED_EXTENSIONS)
    ]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if valid:
        # Fresh upload set: clear prior uploads so they aren't re-ingested.
        for old in UPLOAD_DIR.iterdir():
            if old.is_file():
                old.unlink()
    saved = 0
    for upload in valid:
        dest = UPLOAD_DIR / Path(upload.filename).name  # strip any path traversal
        dest.write_bytes(await upload.read())
        saved += 1

    input_path = str(UPLOAD_DIR) if saved else (source_path or str(BASE_DIR / "sample_docs"))

    config = RunConfig(
        input=input_path,
        out=str(OUTPUT_DIR),
        backend=backend,
        model=model.strip()
        or ("claude-opus-4-8" if backend == "anthropic" else "llama3.1"),
        limit=int(limit) if limit.strip().isdigit() else None,
        detect_conflicts=(detect_conflicts == "on"),
    )

    # Drive the synchronous pipeline in a worker thread and stream its progress
    # messages out through a queue.
    q: "queue.Queue[Optional[str]]" = queue.Queue()

    def worker() -> None:
        try:
            run_pipeline(config, progress=q.put)
            q.put("\n=== Run complete. Open Candidates / Conflicts / Spans. ===")
        except Exception as exc:  # surface failures to the browser
            q.put(f"\nError: {exc}")
        finally:
            q.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        if saved:
            yield f"Saved {saved} uploaded file(s) to {UPLOAD_DIR}\n"
        while True:
            line = q.get()
            if line is None:
                break
            yield line + "\n"

    return StreamingResponse(stream(), media_type="text/plain")


@app.get("/candidates", response_class=HTMLResponse)
def candidates_page(request: Request):
    ctx = _common(request)
    ctx["candidates"] = load_candidates(OUTPUT_DIR)
    return templates.TemplateResponse(request, "candidates.html", ctx)


@app.get("/conflicts", response_class=HTMLResponse)
def conflicts_page(request: Request):
    candidates = {c.rule_id: c for c in load_candidates(OUTPUT_DIR)}
    ctx = _common(request)
    ctx["conflicts"] = load_conflicts(OUTPUT_DIR)
    ctx["candidates"] = candidates
    return templates.TemplateResponse(request, "conflicts.html", ctx)


@app.get("/spans", response_class=HTMLResponse)
def spans_page(request: Request):
    ctx = _common(request)
    ctx["spans"] = load_spans(OUTPUT_DIR)
    return templates.TemplateResponse(request, "spans.html", ctx)


@app.get("/candidate/{rule_id}", response_class=HTMLResponse)
def candidate_detail(request: Request, rule_id: str):
    candidates = load_candidates(OUTPUT_DIR)
    candidate = next((c for c in candidates if c.rule_id == rule_id), None)
    if candidate is None:
        return RedirectResponse("/candidates")

    spans_by_id = {s.span_id: s for s in load_spans(OUTPUT_DIR)}
    source_spans = [
        spans_by_id[sid] for sid in candidate.source_span_ids if sid in spans_by_id
    ]
    # Conflicts that involve this rule, for cross-linking.
    related = [
        c
        for c in load_conflicts(OUTPUT_DIR)
        if rule_id in (c.rule_id_a, c.rule_id_b)
    ]

    ctx = _common(request)
    ctx.update(
        candidate=candidate, source_spans=source_spans, related_conflicts=related
    )
    return templates.TemplateResponse(request, "candidate.html", ctx)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="rule-extractor local web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address.")
    parser.add_argument("--port", type=int, default=8765, help="Port.")
    parser.add_argument(
        "--allow-lan",
        action="store_true",
        help="Permit binding a non-loopback address (NOT recommended).",
    )
    args = parser.parse_args(argv)

    loopback = args.host in {"127.0.0.1", "localhost", "::1"}
    if not loopback and not args.allow_lan:
        parser.error(
            f"Refusing to bind non-loopback address {args.host!r}. "
            "This is a single-user local tool. Pass --allow-lan to override."
        )

    import uvicorn

    print(f"rule-extractor UI on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
