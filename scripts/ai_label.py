"""AI STAND-IN labels: a local model fills the frozen rubric (v1.1) for every item in a labelling folder.

NOT GROUND TRUTH. Owner decision 2026-11-19: Cathy is busy, so every label-dependent method runs on stand-in labels
first, marked as such, and is rerun on human labels when they exist. The labeller is a model family that is
neither a rewriter nor a judge in this study (Mistral), it reads only what an annotator sees (the sheets: no
model names, no key), and it is scored against the adjudicated human calibration labels before its labels are used.

  python scripts/ai_label.py --sheets data/annotations/ollama-v1 --out data/annotations/ollama-v1-standin \
      --shard 0 --nshards 4                 # inside a GPU job with Ollama running
  python scripts/ai_label.py --sheets data/annotations/ollama-v1 --out data/annotations/ollama-v1-standin --merge
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm import call_with_one_retry, make_provider, parse_json_block  # noqa: E402
from make_annotation_sheets import LABEL_COLUMNS  # noqa: E402
from sheets_xlsx import ENUMS, FAILURE_CODES, SHOWN, validate  # noqa: E402

MODEL = "mistral-small3.2:24b"
SPEC = {"provider": "openai_compat", "base_url": f"http://localhost:{os.environ.get('OLLAMA_PORT', '11434')}/v1", "model": MODEL,
        "settings": {"max_tokens": 1500, "temperature": 0, "seed": 2880}}
FIELDS = [c for c in LABEL_COLUMNS if c != "notes"] + ["notes"]


def system_prompt() -> str:
    guide = (ROOT / "docs" / "annotation_guide.md").read_text(encoding="utf-8")
    codes = "\n".join(f"- {k}: {v}" for k, v in FAILURE_CODES.items())
    enums = "\n".join(f"- {k}: one of {v}" for k, v in ENUMS.items())
    return (f"You are a careful annotator applying this rubric exactly.\n\n{guide}\n\n"
            f"Allowed values:\n{enums}\n- failure_codes: comma-separated, from:\n{codes}\n\n"
            "Rules: judge the ADAPTATION against the ORIGINAL. adaptation_needed is judged on the ORIGINAL only. "
            "If model_status is NO_REWRITE_NEEDED, leave presentation empty and set abstention_appropriate YES or NO; "
            "otherwise abstention_appropriate is NA. Any FAIL, solvability YES, ambiguity NEW or leakage_level > 0 "
            "needs the exact offending words in evidence. Label everything in the adaptation, including preambles "
            "and tips (code EXTRA_TEXT for teacher-only text).\n"
            f"Reply with one JSON object with exactly these keys: {FIELDS}. Values are strings.")


def items(sheets: Path) -> pd.DataFrame:
    frames = [pd.read_csv(sheets / f"sheet_{s}.csv", dtype=str, keep_default_na=False)[SHOWN] for s in "AB"]
    return pd.concat(frames).drop_duplicates("annotation_id").sort_values("annotation_id").reset_index(drop=True)


def user_prompt(r: pd.Series) -> str:
    return (f"transformation_requested: {r.transformation_requested}\nmodel_status: {r.model_status or '(none)'}\n\n"
            f"ORIGINAL:\n{r.original}\n\nADAPTATION:\n{r.adaptation}")


def label(sheets: Path, out: Path, shard: int, nshards: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"raw_shard{shard}.jsonl"
    done = {json.loads(l)["annotation_id"] for l in path.open()} if path.exists() else set()
    todo = [r for i, r in items(sheets).iterrows() if i % nshards == shard and r.annotation_id not in done]
    prov, system = make_provider(SPEC), system_prompt()
    print(f"shard {shard}/{nshards}: {len(todo)} items to label ({len(done)} done)", flush=True)
    for n, r in enumerate(todo, 1):
        res = call_with_one_retry(prov, system, user_prompt(r))
        parsed = parse_json_block(res.get("raw_output") or "") or {}
        row, probs, complete = validate({**{c: r[c] for c in SHOWN}, **{k: parsed.get(k, "") for k in FIELDS}})
        if probs:   # one content retry with the validator's message (stand-in labels only; never for humans)
            res2 = call_with_one_retry(prov, system, user_prompt(r) + "\n\nYour previous reply had these problems: "
                                       + "; ".join(probs) + ". Reply again with a corrected JSON object.")
            p2 = parse_json_block(res2.get("raw_output") or "") or {}
            row2, probs2, complete2 = validate({**{c: r[c] for c in SHOWN}, **{k: p2.get(k, "") for k in FIELDS}})
            if len(probs2) <= len(probs):
                row, probs, complete, res = row2, probs2, complete2, res2
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"annotation_id": r.annotation_id, "labels": {k: row.get(k, "") for k in LABEL_COLUMNS},
                                "problems": probs, "complete": complete, "model": MODEL,
                                "usage": res.get("usage"), "latency_s": res.get("latency_s")}) + "\n")
        if n % 25 == 0:
            print(f"  {n}/{len(todo)}", flush=True)


def merge(sheets: Path, out: Path) -> None:
    rows = [json.loads(l) for p in sorted(out.glob("raw_shard*.jsonl")) for l in p.open()]
    by_id = {r["annotation_id"]: r for r in rows}
    its = items(sheets)
    recs = []
    for _, r in its.iterrows():
        x = by_id.get(r.annotation_id)
        if not x:
            continue
        recs.append({**{c: r[c] for c in SHOWN}, **x["labels"], "annotator": "ADJ",
                     "source": f"ai_standin:{MODEL}", "complete": x["complete"]})
    df = pd.DataFrame(recs)
    df.to_csv(out / "adjudicated.csv", index=False)
    (out / "README.md").write_text(
        "# AI STAND-IN LABELS: NOT GROUND TRUTH\n\n"
        f"Labeller: {MODEL} (Mistral family: neither a rewriter nor a judge in this study), rubric v1.1, "
        "temperature 0, reading only the annotator sheets (no model names, no key).\n"
        "Every result computed from these labels is a dry run of the methods, to be rerun on human labels.\n"
        f"Items labelled: {len(df)} of {len(its)}; complete: {int(df['complete'].sum()) if len(df) else 0}.\n")
    print(f"wrote {out / 'adjudicated.csv'}: {len(df)} of {len(its)} items, complete {int(df['complete'].sum())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    (merge if a.merge else lambda s, o: label(s, o, a.shard, a.nshards))(Path(a.sheets), Path(a.out))
