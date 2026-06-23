# rule-extractor

Extract discrete, **traceable** rule candidates from `.docx` policy and
regulatory documents, flag conflicts between them, and browse everything in a
local web UI — all running on your own machine.

The pipeline turns documents into three plain JSON artifacts:

```
docx files  ->  spans       (verbatim source paragraphs)
            ->  candidates  (one normalized rule each, linked to its spans)
            ->  conflicts   (pairs of candidates that contradict)
```

Every rule points back to the exact source paragraph(s) it came from, so a
reviewer can always verify a rule against the original wording.

## Why "local"

The pipeline runs fully on a local machine. There are two run modes (CLI and a
localhost web UI) and two LLM backends (Anthropic API, or a local Ollama model
for a fully offline run). Nothing is sent anywhere except the LLM call — and
with the Ollama backend, not even that.

---

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` includes `python-docx`, `pydantic`, `fastapi`, `uvicorn`,
`jinja2`, `anthropic`, and `httpx` (for Ollama).

### Make a sample document (optional)

To try the pipeline without supplying your own docs:

```bash
python make_sample.py        # writes ./sample_docs/access_policy.docx
```

---

## Mode 1 — Local CLI (default)

Runs entirely locally. The only outbound network call is to the LLM provider.
No server, no other service required.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python extract.py --input ./sample_docs --out ./output
```

Output JSON lands in `./output/` (`spans.json`, `candidates.json`,
`conflicts.json`, `run.json`).

Flags:

| Flag | Default | Meaning |
|---|---|---|
| `--input` | (required) | A `.docx` file or a directory of `.docx` files. |
| `--out` | (required) | Directory for the JSON artifacts. |
| `--backend` | `anthropic` | `anthropic` or `ollama`. |
| `--model` | per-backend | `claude-opus-4-8` (anthropic) / `llama3.1` (ollama). |
| `--limit` | all | Max number of documents to process. |
| `--no-conflicts` | off | Skip the conflict-detection stage. |

---

## Mode 2 — Local web UI on localhost

A thin presentation layer over the **same** pipeline modules. It reads the JSON
artifacts the CLI writes; no extraction logic lives in the server.

```bash
python server.py
# or:
uvicorn server:app --host 127.0.0.1 --port 8765
```

Open **http://localhost:8765**

Routes:

- `GET /` — upload form (drag-and-drop `.docx`) + run-config fields + **Run
  extraction** button. Progress streams live into the page.
- `POST /run` — runs the pipeline on uploaded/selected docs; streams progress.
- `GET /candidates`, `/conflicts`, `/spans` — browsable tables of the latest run.
- `GET /candidate/<rule_id>` — single candidate shown **side by side** with its
  verbatim source paragraph(s) (the traceability view).

### Security / privacy

- **Loopback only.** Binds `127.0.0.1`. It refuses to bind a non-loopback
  address unless you pass `--allow-lan` explicitly.
- **No auth.** This is fine because it only listens on loopback. It is a
  single-user local tool, **not a deployable service**.
- Uploaded docs stay under `./output/uploads`. Nothing is sent anywhere except
  the LLM call.

---

## LLM backends

The LLM client is abstracted behind one interface (`llm.py`) with two
implementations, selected with `--backend`:

### `anthropic` (default)

Uses the Anthropic API. The key is read from the `ANTHROPIC_API_KEY`
environment variable. Default model `claude-opus-4-8`.

```bash
python extract.py --input ./docs --out ./output --backend anthropic
```

### `ollama` (fully offline)

Uses a local [Ollama](https://ollama.com) server at `http://localhost:11434`.
Selecting this makes the pipeline **fully offline — no data leaves the
machine**.

```bash
# one-time setup
ollama serve            # start the local server (if not already running)
ollama pull llama3.1    # pull a model

python extract.py --input ./docs --out ./output --backend ollama --model llama3.1
```

> **Quality note:** local-model extraction quality is generally lower than the
> Anthropic backend. Validate the yield on the sample documents (and a slice of
> your real docs) before trusting it on a full corpus. Set `OLLAMA_HOST` to
> point at a non-default Ollama address if needed.

**Verifying it's offline:** run the Ollama command with networking disabled
(e.g. in a sandbox with no egress). It should complete end to end with zero
outbound network calls.

---

## How traceability works

1. `docx_reader` reads each paragraph into a **Span** with a stable id like
   `access_policy.docx::p0007` and the verbatim text.
2. `extractor` sends spans to the model and asks for rules that **cite the
   span_id(s)** they came from. References that don't match a real span are
   dropped; if the model cites none, the rule falls back to the chunk's spans so
   it is never left un-sourced.
3. The web UI's `/candidate/<rule_id>` page renders the extracted rule next to
   those exact source paragraphs.

---

## Project layout

```
extract.py            CLI entry point
server.py             FastAPI localhost web UI (thin layer over the pipeline)
llm.py                LLM backend abstraction (anthropic | ollama)
make_sample.py        generate a sample policy .docx
pipeline/
  models.py           pydantic models + artifact (de)serialization
  docx_reader.py      .docx -> Spans
  extractor.py        Spans -> RuleCandidates (LLM)
  conflicts.py        RuleCandidates -> Conflicts (LLM)
  runner.py           orchestration shared by CLI and server
templates/            Jinja2 templates (server-rendered HTML)
static/app.css        vendored stylesheet (no CDN; works air-gapped)
output/               artifacts + uploads (git-ignored)
```

---

## Acceptance checklist

- `python extract.py --input ./docs --out ./output` runs with no server and no
  localhost dependency.
- `python server.py` serves on `127.0.0.1:8765`; the traceability view shows
  each candidate next to its verbatim source paragraph.
- `--backend ollama` runs end to end with zero outbound network calls (verify
  with networking disabled).
