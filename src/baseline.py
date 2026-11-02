"""Deterministic chunking baseline: no paraphrase, no model.

Splits the original text into sentences (and long sentences at clause
boundaries), puts one per line, and puts the question last. Every word of the
source is kept in its original order, so mathematical fidelity and absence of
leakage hold by construction. The research question is how much presentation
benefit LLM chunking adds over this.

Usage:  python src/baseline.py data/frozen/main.jsonl data/frozen/ext_asdiv.jsonl \
            --run-id main-v1 --out data/outputs/main-v1/baseline.jsonl
        python src/baseline.py data/frozen/main.jsonl > baseline.jsonl     # JSONL to stdout

Rows use the same schema as collect_outputs generations (generator "deterministic"),
so the verifier, repair and annotation-sheet scripts accept them unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import append_jsonl, read_jsonl, sha256_text
from llm import done_ids

ABBREV = r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bvs)(?<!\be\.g)(?<!\bi\.e)"
SENTENCE_END = re.compile(ABBREV + r"(?<=[.?!])\s+(?=[A-Z$0-9\"'])")
# split long sentences before these clause openers; the words stay in place
CLAUSE_BREAK = re.compile(r",\s+(?=(?:and|but|then|so|while|after|before|if|when)\b)")
MAX_WORDS = 18


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in SENTENCE_END.split(text) if s.strip()]


def chunk(text: str, max_words: int = MAX_WORDS) -> list[str]:
    out: list[str] = []
    for s in sentences(text):
        if len(s.split()) > max_words:
            parts = CLAUSE_BREAK.split(s)
            out += [p if i == len(parts) - 1 else p + "," for i, p in enumerate(parts)]
        else:
            out.append(s)
    return out


def render(text: str) -> str:
    lines = chunk(text)
    questions = [l for l in lines if l.endswith("?")]
    facts = [l for l in lines if not l.endswith("?")]
    # A question in the middle of the text is moved last only if it is the final question;
    # otherwise order is kept so no temporal relation changes.
    if len(questions) == 1 and lines[-1] == questions[0]:
        return "\n".join([f"- {l}" for l in facts] + [f"Question: {questions[0]}"])
    return "\n".join(f"- {l}" for l in lines)


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9$%.']+", text.lower())


def is_lossless(src: str, out: str) -> bool:
    """Same word sequence after removing the layout markers the baseline adds."""
    stripped = re.sub(r"^(- |Question: )", "", out, flags=re.M)
    return tokens(stripped) == tokens(src)


def records(sources: list[dict], run_id: str) -> list[dict]:
    """Baseline rows in the generations schema (one per source with text)."""
    rows = []
    for p in sources:
        if not p.get("text"):
            continue
        out = render(p["text"])
        assert is_lossless(p["text"], out), p["source_id"]
        rows.append({
            "output_id": f"{run_id}|deterministic|chunked|{p['source_id']}", "run_id": run_id,
            "generator": "deterministic", "transformation": "chunked", "source_id": p["source_id"],
            "dataset": p["dataset"], "partition": p["partition"], "source_sha256": sha256_text(p["text"]),
            "prompt_version": "baseline_v1", "prompt_sha256": None, "provider": "deterministic",
            "requested_model": "deterministic", "returned_model": "deterministic", "response_id": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}, "latency_s": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "raw_output": out,
            "status": "DETERMINISTIC", "adapted_problem": out, "parse_error": False,
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="frozen source jsonl files")
    ap.add_argument("--run-id", default="baseline")
    ap.add_argument("--out", default=None, help="append missing rows here; default is stdout")
    args = ap.parse_args()
    srcs = [r for f in args.sources for r in read_jsonl(Path(f))]
    rows = records(srcs, args.run_id)
    if not args.out:
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        return
    out = Path(args.out)
    seen = done_ids(out)
    new = [r for r in rows if r["output_id"] not in seen]
    for r in new:
        append_jsonl(out, r)
    print(f"{len(new)} baseline rows appended ({len(rows) - len(new)} already present) -> {out}")


if __name__ == "__main__":
    main()
