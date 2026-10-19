"""Deterministic chunking baseline: no paraphrase, no model.

Splits the original text into sentences (and long sentences at clause
boundaries), puts one per line, and puts the question last. Every word of the
source is kept in its original order, so mathematical fidelity and absence of
leakage hold by construction. The research question is how much presentation
benefit LLM chunking adds over this.

Usage:  python src/baseline.py data/frozen/main.jsonl > data/outputs/baseline_main.jsonl
"""
from __future__ import annotations

import json
import re
import sys

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


def main() -> None:
    for line in open(sys.argv[1], encoding="utf-8"):
        p = json.loads(line)
        if not p.get("text"):
            continue
        out = render(p["text"])
        assert is_lossless(p["text"], out), p["source_id"]
        print(json.dumps({"source_id": p["source_id"], "model": "deterministic", "transformation": "chunked",
                          "adapted_problem": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
