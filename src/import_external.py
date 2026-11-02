"""Map manually captured external-tool outputs into the generations schema (Phase 3A).

  python src/import_external.py data/external/<file>.csv --run-id external-v1 [--allow-unchecked]

Input: a CSV laid out like data/external/TEMPLATE.csv (one row per tool x frozen source problem).
Output: data/outputs/<run_id>/generations.jsonl + config.frozen.yaml, so verify.py,
make_annotation_sheets.py and ppi.py run on the external tools unchanged.

Rows keep the collect_outputs record keys exactly, plus one extra key, "extra" (captured_by and
other capture metadata). Provider fields are filled as: provider="external", requested_model=<tool>,
returned_model=<tool_version_or_date>, response_id/stop_reason/settings empty, usage zeros,
latency_s None. If `adapted_problem` is blank the whole reply is used (as in the "naive" condition).

Manual capture only. Captured outputs stay local (see docs/external_collection_protocol.md).
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import yaml

from common import FROZEN, OUTPUTS, ROOT, append_jsonl, read_jsonl, sha256_text
from llm import done_ids

REQUIRED = ["external_id", "tool", "tool_version_or_date", "ui_path", "prompt_used", "source_id", "captured_by",
            "captured_at", "raw_response", "adapted_problem", "tos_checked", "tos_notes", "notes"]
NEEDS_VALUE = ["external_id", "tool", "prompt_used", "source_id", "captured_by", "captured_at", "raw_response",
               "tos_checked"]


def tool_slug(tool: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", tool.lower()).strip("_")


def is_example(row: dict) -> bool:
    return row["external_id"].strip().upper().startswith("EXAMPLE")


def load_template(csv_path: Path, allow_unchecked: bool = False) -> list[dict]:
    """Read and validate a capture CSV; EXAMPLE rows are dropped.

    Errors (ValueError) on: missing columns, blank required cells, tos_checked not YES/NO,
    tos_checked != YES (unless allow_unchecked), and two rows for the same tool and source.
    """
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path}: missing columns {missing}")
        rows = [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in reader]
    rows = [r for r in rows if not is_example(r)]
    seen: set[tuple[str, str]] = set()
    for r in rows:
        where = f"{csv_path.name} row {r['external_id'] or '?'}"
        blank = [c for c in NEEDS_VALUE if not r[c]]
        if blank:
            raise ValueError(f"{where}: empty required cells {blank}")
        r["tos_checked"] = r["tos_checked"].upper()
        if r["tos_checked"] not in ("YES", "NO"):
            raise ValueError(f"{where}: tos_checked must be YES or NO, got {r['tos_checked']!r}")
        if r["tos_checked"] != "YES" and not allow_unchecked:
            raise ValueError(f"{where}: tos_checked is {r['tos_checked']} for {r['tool']!r}; read the tool's terms "
                             "first or pass --allow-unchecked (local testing only)")
        key = (tool_slug(r["tool"]), r["source_id"])
        if key in seen:
            raise ValueError(f"{where}: duplicate capture for tool {r['tool']!r} and source {r['source_id']}")
        seen.add(key)
    return rows


def frozen_sources() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(FROZEN.glob("*.jsonl")):
        for r in read_jsonl(p):
            if r.get("text"):
                out.setdefault(r["source_id"], r)
    return out


def to_generations(rows: list[dict], run_id: str = "external-v1") -> list[dict]:
    """Rows from load_template -> generation records (same keys as collect_outputs, plus "extra")."""
    srcs = frozen_sources()
    out = []
    for r in rows:
        s = srcs.get(r["source_id"])
        if s is None:
            raise ValueError(f"{r['external_id']}: source_id {r['source_id']!r} not found in data/frozen/*.jsonl")
        sha = sha256_text(s["text"])
        if s.get("source_sha256") and s["source_sha256"] != sha:
            raise ValueError(f"{r['external_id']}: frozen text for {r['source_id']} does not match its source_sha256")
        slug = tool_slug(r["tool"])
        out.append({
            "output_id": f"{run_id}|{slug}|external|{r['source_id']}", "run_id": run_id, "generator": slug,
            "transformation": "external", "source_id": r["source_id"], "dataset": s["dataset"],
            "partition": s["partition"], "source_sha256": sha, "prompt_version": f"external:{r['prompt_used'][:40]}",
            "prompt_sha256": sha256_text(r["prompt_used"]),
            "raw_output": r["raw_response"], "returned_model": r["tool_version_or_date"], "response_id": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}, "stop_reason": None, "provider": "external",
            "requested_model": r["tool"], "settings": {}, "latency_s": None, "timestamp": r["captured_at"],
            "attempt": 1, "status": "EXTERNAL", "adapted_problem": r["adapted_problem"] or r["raw_response"],
            "parse_error": False,
            "extra": {"captured_by": r["captured_by"], "external_id": r["external_id"], "ui_path": r["ui_path"],
                      "prompt_used": r["prompt_used"], "tos_checked": r["tos_checked"], "tos_notes": r["tos_notes"],
                      "notes": r["notes"], "adapted_problem_blank": not r["adapted_problem"]},
        })
    return out


def write_run(rows: list[dict], run_dir: Path) -> Path:
    """Write <run_dir>/generations.jsonl (run_id = folder name; append-only, existing output_ids are kept)
    and a config.frozen.yaml stub that marks the run as external and is accepted by verify.py --config."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "generations.jsonl"
    seen = done_ids(path)
    for g in to_generations(rows, run_id=run_dir.name):
        if g["output_id"] not in seen:
            append_jsonl(path, g)
    base = yaml.safe_load(next(p for p in (ROOT / "config.yaml", ROOT / "config.example.yaml") if p.exists()).read_text())
    cfg = {"run_id": run_dir.name, "origin": "external",
           "note": "Manually captured outputs from third-party tools (docs/external_collection_protocol.md). "
                   "Nothing here was generated by this pipeline; critic/extractor/prices are copied from the main "
                   "config so verify.py and ledger.py can run on this folder.",
           "tools": sorted({tool_slug(r["tool"]) for r in rows}),
           **{k: base[k] for k in ("critic", "extractor", "prices") if k in base}}
    (run_dir / "config.frozen.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="capture CSV, e.g. data/external/captures.csv")
    ap.add_argument("--run-id", default="external-v1")
    ap.add_argument("--allow-unchecked", action="store_true", help="accept rows whose tos_checked is not YES")
    args = ap.parse_args()
    try:
        rows = load_template(Path(args.csv), allow_unchecked=args.allow_unchecked)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    if not rows:
        raise SystemExit(f"{args.csv}: no non-EXAMPLE rows")
    run_dir = OUTPUTS / args.run_id
    path = write_run(rows, run_dir)
    tools = sorted({tool_slug(r["tool"]) for r in rows})
    print(f"wrote {len(rows)} rows for {len(tools)} tool(s) {tools} -> {path}")
    cfg = run_dir / "config.frozen.yaml"
    print(f"""
Next (captured outputs stay local; do not commit data/outputs/{args.run_id} or the annotation sheets):
  python src/verify.py {path} --config {cfg}
  python src/verify.py {path} --config {cfg} --layers det        # free layer only
  python src/make_annotation_sheets.py {path}
  python src/ppi.py ...    # ~30 human labels per tool, verifier as predictor (see docs/plan/PHASE2.md, 2C)""")


if __name__ == "__main__":
    main()
