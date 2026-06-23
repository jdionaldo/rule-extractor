"""LLM backend abstraction.

One interface, two implementations:

* ``anthropic`` (default) — Anthropic API. Key from ``ANTHROPIC_API_KEY``.
  The only outbound network call the pipeline makes.
* ``ollama`` — a local Ollama server (``http://localhost:11434``). Selecting
  this makes the pipeline fully offline: nothing leaves the machine.

Both implementations expose a single method, ``generate_json``, which returns a
dict validated against a JSON schema. Callers never branch on the backend.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Protocol

DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_OLLAMA_MODEL = "llama3.1"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class LLMError(RuntimeError):
    """Raised when a backend cannot produce usable JSON output."""


class LLMClient(Protocol):
    """Minimal interface every backend implements."""

    model: str

    def generate_json(
        self, *, system: str, prompt: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return a dict matching ``schema`` (object at the top level)."""
        ...


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Best-effort parse of a JSON object from model text output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tolerate stray prose around the object (common with local models).
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise LLMError(f"Backend did not return JSON. Got:\n{text[:500]}")


class AnthropicClient:
    """Anthropic API backend using structured outputs for guaranteed JSON."""

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise LLMError(
                "The 'anthropic' package is required for the anthropic backend. "
                "Install it with: pip install anthropic"
            ) from exc

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Export it, or use --backend ollama "
                "to run fully offline."
            )
        self.model = model
        self._client = anthropic.Anthropic()

    def generate_json(
        self, *, system: str, prompt: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Adaptive thinking is enabled for higher extraction fidelity: the model
        # reasons about modality, scope, and span attribution before committing
        # to the structured output. `output_config.format` still constrains the
        # response to valid JSON matching the schema (structured outputs work
        # with extended thinking). No assistant prefill (removed on Opus 4.6+).
        #
        # Thinking tokens count toward the output budget, so max_tokens is
        # generous and we stream — the SDK's recommended path for thinking /
        # larger outputs, which also avoids HTTP timeouts on the longer calls.
        with self._client.messages.stream(
            model=self.model,
            max_tokens=32000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            response = stream.get_final_message()
        text = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            "",
        )
        return _extract_json_object(text)


class OllamaClient:
    """Local Ollama backend. Fully offline — no data leaves the machine."""

    def __init__(
        self, model: str = DEFAULT_OLLAMA_MODEL, host: str = OLLAMA_HOST
    ) -> None:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - import guard
            raise LLMError(
                "The 'httpx' package is required for the ollama backend. "
                "Install it with: pip install httpx"
            ) from exc
        self._httpx = httpx
        self.model = model
        self.host = host.rstrip("/")

    def generate_json(
        self, *, system: str, prompt: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Ollama accepts a JSON schema as `format` to constrain output.
        payload = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            resp = self._httpx.post(
                f"{self.host}/api/chat", json=payload, timeout=600.0
            )
            resp.raise_for_status()
        except Exception as exc:  # network / connection errors
            raise LLMError(
                f"Could not reach Ollama at {self.host}. Is it running? "
                f"(start it with `ollama serve`). Underlying error: {exc}"
            ) from exc
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return _extract_json_object(content)


def make_client(backend: str, model: str | None = None) -> LLMClient:
    """Factory: build the requested backend, applying sensible model defaults."""
    if backend == "anthropic":
        return AnthropicClient(model=model or DEFAULT_ANTHROPIC_MODEL)
    if backend == "ollama":
        return OllamaClient(model=model or DEFAULT_OLLAMA_MODEL)
    raise LLMError(f"Unknown backend: {backend!r}. Use 'anthropic' or 'ollama'.")
