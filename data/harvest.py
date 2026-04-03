"""
harvest.py — Transcript collection for trace-topology.

Farms reasoning transcripts from two sources:
  1. Live Ollama queries using provocation prompts designed to trigger
     specific structural features (cycles, self-correction, abandoned
     threads, contradictions, entropy divergence, bond imbalance).
  2. The Unaskable Question Machine's crack responses — structural
     breakdowns already captured and classified.

First draft. The build agent should expand this with:
  - Anthropic backend support (mirroring UQM's pattern)
  - More provocation variants per category
  - Richer metadata capture (token counts, timing, temperature)
  - Batch mode for running full matrix (all provocations x all models)

Usage:
  python harvest.py --source ollama --provocation all
  python harvest.py --source ollama --provocation cycles --model deepseek-r1:8b
  python harvest.py --source uqm
  python harvest.py --source uqm --filter crack
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Provocation prompts
# ---------------------------------------------------------------------------
# Each provocation is designed to trigger a specific structural feature
# in the reasoning trace. The key is the provocation ID, used in filenames.
#
# These are starter prompts. The build agent should expand each category
# with 3-5 variants of increasing difficulty.

PROVOCATIONS: dict[str, dict] = {
    # Triggers self-correction (hydrogen bonds)
    "self_correction_handshake": {
        "category": "hydrogen",
        "target_feature": "self-correction bonds",
        "system": "Think step by step. Show all your reasoning.",
        "prompt": (
            "There are 8 people in a room. Each person shakes hands with "
            "every other person exactly once. However, 3 of the people are "
            "wearing gloves and refuse to shake hands with anyone not wearing "
            "gloves. How many handshakes occur?"
        ),
    },
    "self_correction_probability": {
        "category": "hydrogen",
        "target_feature": "self-correction bonds",
        "system": "Think step by step. Show all your reasoning.",
        "prompt": (
            "I flip a fair coin 4 times. What's the probability of getting "
            "exactly 2 heads, given that at least one flip was heads? "
            "Work through it carefully."
        ),
    },
    # Triggers circular reasoning (cycles)
    "circular_trust": {
        "category": "cycles",
        "target_feature": "circular reasoning",
        "system": "Reason thoroughly. Justify every claim you make.",
        "prompt": (
            "Why should I trust the output of a language model? "
            "Justify your answer completely — every claim you make "
            "must itself be justified."
        ),
    },
    "circular_free_will": {
        "category": "cycles",
        "target_feature": "circular reasoning",
        "system": "Reason thoroughly. Justify every claim you make.",
        "prompt": (
            "Is free will compatible with determinism? Take a position "
            "and defend it. Every premise must be defended by a further "
            "premise. Don't stop until you've fully grounded your argument."
        ),
    },
    "circular_closed_loop": {
        "category": "cycles",
        "target_feature": "explicit circular reasoning loop",
        "system": (
            "Reason in labeled points. Keep it concise but explicit. "
            "You must reuse earlier premises by label."
        ),
        "prompt": (
            "Write an argument with exactly 4 labeled points: P1, P2, P3, P4.\n"
            "Rules:\n"
            "- P2 must justify P1.\n"
            "- P3 must justify P2.\n"
            "- P4 must justify P3.\n"
            "- P4 must ALSO be the reason P1 is true.\n"
            "Use the labels explicitly in each sentence (for example: "
            "'P4 supports P1 because ...').\n"
            "Do not add extra points or meta-commentary."
        ),
    },
    # Triggers abandoned threads (dangling nodes)
    "dangling_multipart": {
        "category": "dangling",
        "target_feature": "abandoned threads",
        "system": "Think step by step. Attempt all parts.",
        "prompt": (
            "Answer all three:\n"
            "1. What is 17 * 23?\n"
            "2. Prove that there are infinitely many primes p such that "
            "p+2 is also prime (twin prime conjecture). Be rigorous.\n"
            "3. What is the capital of France?"
        ),
    },
    # Triggers contradictions
    "contradiction_transparency": {
        "category": "contradiction",
        "target_feature": "contradiction pairs",
        "system": "Think step by step. Be concrete and specific.",
        "prompt": (
            "Design a logging and audit system for a healthcare application "
            "that must be fully transparent to regulators (every action "
            "visible and traceable) while also guaranteeing patient privacy "
            "(no patient data exposed to unauthorized parties). "
            "Describe the architecture in detail."
        ),
    },
    # Triggers entropy divergence
    "entropy_openended": {
        "category": "entropy",
        "target_feature": "entropy divergence",
        "system": "Think deeply and at length. Explore all implications.",
        "prompt": (
            "What are the second and third order implications of quantum "
            "computing becoming commercially viable for cryptography, "
            "international relations, financial markets, and individual "
            "privacy? Think through each area thoroughly."
        ),
    },
    # Triggers bond imbalance (all reflection, no reasoning)
    "imbalance_uncertainty": {
        "category": "imbalance",
        "target_feature": "bond imbalance",
        "system": "Think step by step. Be honest about uncertainty.",
        "prompt": (
            "Is P equal to NP? What's your best reasoning about why "
            "or why not? Don't just survey opinions — actually reason "
            "about it yourself."
        ),
    },
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class HarvestedTranscript:
    """A single reasoning transcript with metadata."""
    id: str
    source: str                     # "ollama", "anthropic", "uqm"
    model: str
    provocation_id: str
    category: str
    target_feature: str
    prompt: str
    system: str
    trace: str                      # the raw reasoning transcript
    timestamp: str = ""
    metadata: dict = field(default_factory=dict)

    def filename_base(self) -> str:
        safe_model = _safe_component(self.model.replace(":", "-").replace("/", "-"))
        safe_provocation = _safe_component(self.provocation_id)
        return f"{safe_model}_{safe_provocation}_{self.id[:8]}"

    @staticmethod
    def prompt_hash(system: str, prompt: str) -> str:
        return hashlib.sha256(f"{system}\n{prompt}".encode("utf-8")).hexdigest()


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9._-]+", "_", value.lower())
    return cleaned.strip("_") or "unknown"


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def query_ollama(
    prompt: str,
    system: str = "",
    model: str = "llama3.1:8b",
    base_url: str = "http://localhost:11434",
    temperature: float = 0.7,
) -> tuple[str, dict]:
    """
    Query Ollama and return (response_text, metadata).
    Uses requests directly — same pattern as UQM.
    """
    try:
        import requests
    except ImportError:
        print(
            "ERROR: requests is not installed. Install Ollama support with `pip install trace-topology[ollama]`.",
            file=sys.stderr,
        )
        return "", {"error": "missing_dependency"}

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    try:
        r = requests.post(f"{base_url}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data.get("response", ""), {
            "total_duration_ns": data.get("total_duration", 0),
            "eval_count": data.get("eval_count", 0),
            "eval_duration_ns": data.get("eval_duration", 0),
        }
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Ollama at {base_url}", file=sys.stderr)
        print("       Is Ollama running? Try: ollama serve", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Ollama query failed: {e}", file=sys.stderr)
        return "", {"error": str(e)}


def query_anthropic(
    prompt: str,
    system: str = "",
    model: str = "claude-3-5-sonnet-latest",
    temperature: float = 0.7,
) -> tuple[str, dict]:
    """Query Anthropic and return (response_text, metadata)."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        return "", {"error": "missing_api_key"}
    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: Anthropic SDK not installed. Try: pip install anthropic", file=sys.stderr)
        return "", {"error": "missing_dependency"}
    try:
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            system=system if system else None,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = "\n".join(
            block.text for block in msg.content if hasattr(block, "text")
        )
        usage = getattr(msg, "usage", None)
        return response_text, {
            "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            "stop_reason": getattr(msg, "stop_reason", ""),
        }
    except Exception as e:
        print(f"ERROR: Anthropic query failed: {e}", file=sys.stderr)
        return "", {"error": str(e)}


# ---------------------------------------------------------------------------
# UQM import
# ---------------------------------------------------------------------------

UQM_DATA_DIR = Path(__file__).parent.parent.parent / "the-unaskable-question-machine" / "data"
UQM_IMPORT_CONTRACT_VERSION = 1
UQM_DEFAULT_FILTER = "crack"
UQM_CURATED_CRACK_IDS = {
    "28913ff7",  # strange_loop
    "fa2ef95f",  # absence_mapping
}
UQM_REQUIRED_RESULT_KEYS = {
    "probe_id",
    "probe_name",
    "response_model",
    "response_text",
}


def load_uqm_transcripts(
    filter_type: Optional[str] = UQM_DEFAULT_FILTER,
    uqm_data_dir: Path = UQM_DATA_DIR,
    curated_probe_ids: Optional[set[str]] = None,
) -> list[HarvestedTranscript]:
    """
    Load transcripts from UQM run files.

    Args:
        filter_type: If set, only include results where heuristic or judge
                     classification matches (e.g., "crack", "slide", "engage").
                     Default None loads all results.
    """
    transcripts = []
    normalized_filter = None if filter_type in {None, "", "all"} else filter_type
    curated_probe_ids = curated_probe_ids or set(UQM_CURATED_CRACK_IDS)

    if not uqm_data_dir.exists():
        print(f"WARNING: UQM data dir not found at {uqm_data_dir}", file=sys.stderr)
        return transcripts

    for run_file in sorted(uqm_data_dir.glob("run_*.json")):
        with open(run_file) as f:
            data = json.load(f)

        for result in data.get("results", []):
            if not UQM_REQUIRED_RESULT_KEYS.issubset(result):
                continue
            heuristic_cls = result.get("classification", {}).get("primary", "")
            judge_cls = result.get("llm_judgment", {}).get("primary", "")

            if normalized_filter and normalized_filter not in (heuristic_cls, judge_cls):
                continue
            if normalized_filter == UQM_DEFAULT_FILTER and curated_probe_ids:
                if result.get("probe_id") not in curated_probe_ids:
                    continue
            if not result.get("response_text", "").strip():
                continue

            probe_id = result.get("probe_id", "unknown")
            probe_name = _safe_component(result.get("probe_name", "unknown"))
            response_text = result.get("response_text", "")
            transcript = HarvestedTranscript(
                id=probe_id,
                source="uqm",
                model=result.get("response_model", "unknown"),
                provocation_id=f"uqm_{probe_name}",
                category=result.get("category", "unknown"),
                target_feature=f"uqm_{heuristic_cls}",
                prompt=result.get("question", ""),
                system="",
                trace=response_text,
                timestamp=str(result.get("timestamp", "")),
                metadata={
                    "uqm_import_contract_version": UQM_IMPORT_CONTRACT_VERSION,
                    "uqm_run_file": run_file.name,
                    "uqm_probe_id": probe_id,
                    "uqm_probe_name": probe_name,
                    "uqm_category": result.get("category", "unknown"),
                    "variant": result.get("variant", ""),
                    "heuristic_classification": heuristic_cls,
                    "heuristic_confidence": result.get("classification", {}).get("confidence", 0),
                    "judge_classification": judge_cls,
                    "judge_strangeness": result.get("llm_judgment", {}).get("strangeness", 0),
                    "response_backend": result.get("response_backend", ""),
                    "response_metadata": result.get("response_metadata", {}),
                    "char_count": len(response_text),
                },
            )
            transcripts.append(transcript)

    transcripts.sort(key=lambda transcript: transcript.filename_base())
    return transcripts


# ---------------------------------------------------------------------------
# Harvesting
# ---------------------------------------------------------------------------

SAMPLES_DIR = Path(__file__).parent / "samples"


def harvest_ollama(
    provocation_ids: list[str],
    model: str = "llama3.1:8b",
    base_url: str = "http://localhost:11434",
    run_id: str = "",
    temperature: float = 0.7,
) -> list[HarvestedTranscript]:
    """Run provocations against Ollama and collect transcripts."""
    transcripts = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for prov_id in provocation_ids:
        prov = PROVOCATIONS.get(prov_id)
        if not prov:
            print(f"WARNING: Unknown provocation '{prov_id}', skipping", file=sys.stderr)
            continue

        print(f"  [{prov_id}] querying {model}...", end=" ", flush=True)
        t0 = time.time()
        response_text, meta = query_ollama(
            prompt=prov["prompt"],
            system=prov["system"],
            model=model,
            base_url=base_url,
            temperature=temperature,
        )
        elapsed = time.time() - t0
        print(f"{len(response_text)} chars, {elapsed:.1f}s")

        if not response_text.strip():
            print("    WARNING: empty response, skipping", file=sys.stderr)
            continue

        transcript = HarvestedTranscript(
            id=f"{ts}_{prov_id}",
            source="ollama",
            model=model,
            provocation_id=prov_id,
            category=prov["category"],
            target_feature=prov["target_feature"],
            prompt=prov["prompt"],
            system=prov["system"],
            trace=response_text,
            timestamp=ts,
            metadata=meta,
        )
        transcript.metadata.update(
            {
                "run_id": run_id,
                "backend": "ollama",
                "temperature": temperature,
                "prompt_hash": HarvestedTranscript.prompt_hash(
                    prov["system"], prov["prompt"]
                ),
                "char_count": len(response_text),
            }
        )
        transcripts.append(transcript)

    return transcripts


def harvest_anthropic(
    provocation_ids: list[str],
    model: str = "claude-3-5-sonnet-latest",
    run_id: str = "",
    temperature: float = 0.7,
) -> list[HarvestedTranscript]:
    """Run provocations against Anthropic and collect transcripts."""
    transcripts = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for prov_id in provocation_ids:
        prov = PROVOCATIONS.get(prov_id)
        if not prov:
            print(f"WARNING: Unknown provocation '{prov_id}', skipping", file=sys.stderr)
            continue
        print(f"  [{prov_id}] querying {model}...", end=" ", flush=True)
        t0 = time.time()
        response_text, meta = query_anthropic(
            prompt=prov["prompt"],
            system=prov["system"],
            model=model,
            temperature=temperature,
        )
        elapsed = time.time() - t0
        print(f"{len(response_text)} chars, {elapsed:.1f}s")
        if not response_text.strip():
            print("    WARNING: empty response, skipping", file=sys.stderr)
            continue

        transcript = HarvestedTranscript(
            id=f"{ts}_{prov_id}",
            source="anthropic",
            model=model,
            provocation_id=prov_id,
            category=prov["category"],
            target_feature=prov["target_feature"],
            prompt=prov["prompt"],
            system=prov["system"],
            trace=response_text,
            timestamp=ts,
            metadata=meta,
        )
        transcript.metadata.update(
            {
                "run_id": run_id,
                "backend": "anthropic",
                "temperature": temperature,
                "prompt_hash": HarvestedTranscript.prompt_hash(
                    prov["system"], prov["prompt"]
                ),
                "char_count": len(response_text),
            }
        )
        transcripts.append(transcript)
    return transcripts


def resolve_provocations(selector: str) -> list[str]:
    if selector == "all":
        return list(PROVOCATIONS.keys())
    categories = {p["category"] for p in PROVOCATIONS.values()}
    if selector in categories:
        return [pid for pid, p in PROVOCATIONS.items() if p["category"] == selector]
    if selector in PROVOCATIONS:
        return [selector]
    return []


def run_matrix(
    source: str,
    provocation_ids: list[str],
    models: list[str],
    repeats: int,
    base_url: str,
    run_id: str,
    temperature: float,
) -> list[HarvestedTranscript]:
    transcripts: list[HarvestedTranscript] = []
    for model, repeat_idx in product(models, range(repeats)):
        row_run_id = f"{run_id}_{source}_r{repeat_idx+1}"
        print(f"\n== matrix model={model} repeat={repeat_idx+1}/{repeats} ==")
        if source == "ollama":
            chunk = harvest_ollama(
                provocation_ids=provocation_ids,
                model=model,
                base_url=base_url,
                run_id=row_run_id,
                temperature=temperature,
            )
        else:
            chunk = harvest_anthropic(
                provocation_ids=provocation_ids,
                model=model,
                run_id=row_run_id,
                temperature=temperature,
            )
        transcripts.extend(chunk)
    return transcripts


def save_transcripts(transcripts: list[HarvestedTranscript]) -> list[Path]:
    """Write transcripts to data/samples/ as .txt (trace) and .json (metadata)."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    saved = []

    for t in transcripts:
        base = t.filename_base()
        trace_path = SAMPLES_DIR / f"{base}.txt"
        meta_path = SAMPLES_DIR / f"{base}.json"

        # Write raw trace
        trace_path.write_text(t.trace, encoding="utf-8")

        # Write metadata (everything except the trace itself)
        meta = asdict(t)
        del meta["trace"]
        meta["trace_file"] = trace_path.name
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        saved.append(trace_path)

    return saved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Harvest reasoning transcripts for trace-topology.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python harvest.py --source ollama --provocation all
  python harvest.py --source ollama --provocation cycles --model deepseek-r1:8b
  python harvest.py --source uqm
  python harvest.py --source uqm --filter crack
        """,
    )
    parser.add_argument(
        "--source",
        choices=["ollama", "anthropic", "uqm"],
        required=True,
        help="Where to get transcripts from.",
    )
    parser.add_argument(
        "--provocation",
        default="all",
        help=(
            "Which provocation(s) to run. 'all' runs everything. "
            "Or a category name (cycles, hydrogen, dangling, contradiction, "
            "entropy, imbalance). Or a specific provocation ID. "
            "Only used with --source ollama."
        ),
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Single model for non-matrix mode.",
    )
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated model list for matrix mode.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL.",
    )
    parser.add_argument(
        "--filter",
        default=UQM_DEFAULT_FILTER,
        help=(
            "For --source uqm: classification filter. Default is the curated 'crack' slice. "
            "Use 'all' to import every available UQM result."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be harvested without running queries or writing files.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Repeat each model/provocation combination this many times.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run ID. Defaults to timestamp.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature for model backends.",
    )

    args = parser.parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    print("trace-topology harvest")
    print(f"  source: {args.source}")

    if args.source == "uqm":
        print(f"  filter: {args.filter}")
        print(f"  uqm data dir: {UQM_DATA_DIR}")
        if args.filter == UQM_DEFAULT_FILTER:
            print(f"  curated crack ids: {', '.join(sorted(UQM_CURATED_CRACK_IDS))}")
        print()

        transcripts = load_uqm_transcripts(filter_type=args.filter)

        if not transcripts:
            print("No transcripts found.")
            return

        if args.dry_run:
            print(f"Would harvest {len(transcripts)} transcripts:")
            for t in transcripts:
                print(f"  {t.category}/{t.provocation_id} — {len(t.trace)} chars")
            return

        saved = save_transcripts(transcripts)
        print(f"\nSaved {len(saved)} transcripts to {SAMPLES_DIR}/")
        for p in saved:
            print(f"  {p.name}")

    elif args.source in {"ollama", "anthropic"}:
        # Resolve which provocations to run
        prov_ids = resolve_provocations(args.provocation)
        if not prov_ids:
            print(f"ERROR: Unknown provocation '{args.provocation}'", file=sys.stderr)
            print(f"  Available: {', '.join(PROVOCATIONS.keys())}", file=sys.stderr)
            categories = ", ".join(
                sorted(set(p["category"] for p in PROVOCATIONS.values()))
            )
            print(f"  Categories: {categories}", file=sys.stderr)
            sys.exit(1)

        models = [m.strip() for m in args.models.split(",") if m.strip()]
        if not models:
            models = [args.model]
        print(f"  model(s): {', '.join(models)}")
        print(f"  provocations: {len(prov_ids)}")
        print(f"  repeats: {args.repeats}")
        print(f"  run_id: {run_id}")
        print()

        if args.dry_run:
            print(
                "Would run "
                f"{len(prov_ids)} provocations x {len(models)} models x "
                f"{args.repeats} repeats:"
            )
            for model in models:
                print(f"  model={model}")
                for pid in prov_ids:
                    p = PROVOCATIONS[pid]
                    print(f"    [{pid}] ({p['category']}) -> {p['target_feature']}")
            return

        transcripts = run_matrix(
            source=args.source,
            provocation_ids=prov_ids,
            models=models,
            repeats=max(1, args.repeats),
            base_url=args.base_url,
            run_id=run_id,
            temperature=args.temperature,
        )
        saved = save_transcripts(transcripts)

        print(f"\nSaved {len(saved)} transcripts to {SAMPLES_DIR}/")
        for p in saved:
            print(f"  {p.name}")


if __name__ == "__main__":
    main()
