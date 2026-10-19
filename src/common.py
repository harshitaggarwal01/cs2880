"""Shared helpers: paths, hashing, dataset loading, and source-problem feature tags."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FROZEN = ROOT / "data" / "frozen"
PROMPTS = ROOT / "prompts"
OUTPUTS = ROOT / "data" / "outputs"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- datasets

def gsm8k_answer(solution: str) -> str:
    """Final answer after the '####' marker in a GSM8K solution."""
    return solution.split("####")[-1].strip().replace(",", "")


def load_gsm8k(split: str) -> list[dict]:
    rows = read_jsonl(RAW / f"gsm8k_{split}.jsonl")
    return [
        {
            "source_id": f"gsm8k-{split}-{i:04d}",
            "dataset": "gsm8k",
            "split": split,
            "row": i,
            "text": r["question"],
            "answer": gsm8k_answer(r["answer"]),
            "solution": r["answer"],
            "n_steps": r["answer"].count("<<"),
        }
        for i, r in enumerate(rows)
    ]


def load_asdiv() -> list[dict]:
    root = ET.parse(RAW / "asdiv.xml").getroot()
    out = []
    for p in root.iter("Problem"):
        body = (p.findtext("Body") or "").strip()
        question = (p.findtext("Question") or "").strip()
        out.append(
            {
                "source_id": f"asdiv-{p.get('ID')}",
                "dataset": "asdiv",
                "split": "all",
                "row": p.get("ID"),
                "text": f"{body} {question}".strip(),
                "answer": (p.findtext("Answer") or "").strip(),
                "solution": (p.findtext("Formula") or "").strip(),
                "solution_type": (p.findtext("Solution-Type") or "").strip(),
                "grade": int(p.get("Grade") or 0),
            }
        )
    return out


# ---------------------------------------------------------------- feature tags
# Coarse surface tags used for stratified sampling and exploratory analysis.
# They are heuristics, not ground truth about problem structure.

TAG_PATTERNS = {
    "percent": r"%|\bpercent",
    "fraction": r"\b\d+/\d+\b|\bhalf\b|\bthirds?\b|\bquarters?\b|\bfourths?\b",
    "comparison": r"times as|\btwice\b|\bhalf as\b|\bmore than\b|\bless than\b|\bfewer than\b|as many as|as much as",
    "money": r"\$|\bdollars?\b|\bcents?\b",
    "time": r"\bhours?\b|\bminutes?\b|\bdays?\b|\bweeks?\b|\bmonths?\b|\byears?\b",
    "measure": r"\b(miles?|feet|foot|inch(es)?|yards?|meters?|km|kilometers?|pounds?|ounces?|grams?|kg|liters?|gallons?|cups?)\b",
    "conditional": r"\bif\b|\bunless\b|\bonly\b|\bexcept\b",
}

NUMBER_WORDS = r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|dozen)\b"


def tags(text: str) -> dict[str, bool]:
    return {k: bool(re.search(p, text, re.I)) for k, p in TAG_PATTERNS.items()}


def count_quantities(text: str) -> int:
    digits = re.findall(r"\d+(?:[.,]\d+)?", text)
    words = re.findall(NUMBER_WORDS, text, re.I)
    return len(digits) + len(words)


def step_bucket(n_steps: int) -> str:
    if n_steps <= 2:
        return "s<=2"
    if n_steps >= 5:
        return "s>=5"
    return f"s={n_steps}"


def relational(text: str) -> bool:
    t = tags(text)
    return t["comparison"] or t["fraction"] or t["percent"]
