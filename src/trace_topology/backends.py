from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(slots=True)
class BondBackendResult:
    bond_type: str
    confidence: float
    reason: str


class BondBackend:
    name = "none"

    def classify(self, source_text: str, target_text: str) -> BondBackendResult:
        raise NotImplementedError


def _import_requests():
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "Ollama backend requires optional dependency `requests`. "
            "Install it with: pip install trace-topology[ollama]"
        ) from exc
    return requests


def _import_anthropic():
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Anthropic backend requires optional dependency `anthropic`. "
            "Install it with: pip install trace-topology[anthropic]"
        ) from exc
    return Anthropic


class OllamaBackend(BondBackend):
    name = "ollama"

    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def classify(self, source_text: str, target_text: str) -> BondBackendResult:
        requests = _import_requests()
        prompt = (
            "Classify relation between two reasoning steps as one of: "
            "covalent, hydrogen, vanderwaals. Return JSON keys: type, confidence, reason.\n\n"
            f"SOURCE:\n{source_text}\n\nTARGET:\n{target_text}"
        )
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=60,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip().lower()
        except requests.ConnectionError as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. Start it with `ollama serve` "
                "or use `--backend none`."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Ollama backend request failed for model {self.model}: {exc}"
            ) from exc
        for label in ("covalent", "hydrogen", "vanderwaals"):
            if label in text:
                return BondBackendResult(label, 0.6, f"ollama:{self.model}")
        return BondBackendResult("vanderwaals", 0.2, f"ollama:{self.model}:fallback")


class AnthropicBackend(BondBackend):
    name = "anthropic"

    def __init__(self, model: str = "claude-3-5-sonnet-latest", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    def classify(self, source_text: str, target_text: str) -> BondBackendResult:
        if not self.api_key:
            raise RuntimeError(
                "Anthropic backend requires ANTHROPIC_API_KEY. "
                "Set it or use `--backend none`."
            )
        Anthropic = _import_anthropic()
        client = Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Classify relation between reasoning steps as "
                        "covalent/hydrogen/vanderwaals. "
                        "Output a single lowercase label.\n\n"
                        f"SOURCE:\n{source_text}\n\nTARGET:\n{target_text}"
                    ),
                }
            ],
        )
        content = " ".join(block.text for block in msg.content if hasattr(block, "text")).lower()
        for label in ("covalent", "hydrogen", "vanderwaals"):
            if label in content:
                return BondBackendResult(label, 0.7, f"anthropic:{self.model}")
        return BondBackendResult("vanderwaals", 0.2, f"anthropic:{self.model}:fallback")


def prompt_hash(system: str, prompt: str) -> str:
    return hashlib.sha256(f"{system}\n{prompt}".encode("utf-8")).hexdigest()
