"""Back up everything that is hard to reproduce to a PRIVATE Hugging Face dataset repo.

  python src/push_hf.py                              # build data/hf_staging/ only (dry run, no network)
  HF_TOKEN=... python src/push_hf.py --push          # build, then upload (creates the repo if needed)
  python src/push_hf.py --push --repo harshitaggarwal/safeadapt-math --runs anthropic-v1 matrix-v1

What goes up (whitelist; everything else stays local):
  frozen/        frozen sample + MANIFEST (dev, main, ext_asdiv, GSM1K ids only; GSM-IC never)
  runs/<run>/    real API outputs, verifier rows, extraction cache, ledger, frozen config, analysis CSVs
  annotations/<run>/  blind sheets, key and adjudicated labels (human labour; cannot be regenerated)
  pilot_oct16/   the first pilot (subagent outputs, preliminary labels, checks)
  calibration/   70-item calibration sheets (+ key, which unblinds them: the repo must stay private)
  prompts/, schemas/, configs/, docs/run_examples.md
  CHECKSUMS.sha256 and a dataset card with the source git commit
Not uploaded: data/raw (re-downloadable with verified checksums), mock runs, any row whose ids mention GSM1K or
GSM-IC with text (no declared licence), and anything that looks like a secret (the build aborts).

API outputs are not reproducible bit-for-bit (sampling, model updates), and labels are hours of human work;
that is why these files are backed up. The code itself lives on GitHub; the card records the commit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "data" / "hf_staging"
DEFAULT_REPO = "harshitaggarwal/safeadapt-math"
NO_LICENCE = re.compile(r"gsm1k|gsmic", re.I)
SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}|sk-[A-Za-z0-9]{32,}|hf_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_\-]{30,}")


def restricted_row(row: dict) -> bool:
    """True if a row is tied to GSM1K / GSM-IC and carries text (ids-only rows are fine)."""
    ids = " ".join(str(row.get(k, "")) for k in ("source_id", "output_id", "partition", "dataset"))
    if not NO_LICENCE.search(ids):
        return False
    return any(row.get(k) for k in ("text", "adapted_problem", "raw_output", "source_text", "candidate_text",
                                     "original", "adaptation", "problem"))


def copy_jsonl(src: Path, dst: Path) -> tuple[int, int]:
    kept = dropped = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src) as fi, open(dst, "w") as fo:
        for line in fi:
            if not line.strip():
                continue
            row = json.loads(line)
            if restricted_row(row):
                dropped += 1
                continue
            fo.write(line if line.endswith("\n") else line + "\n")
            kept += 1
    return kept, dropped


def copy_csv(src: Path, dst: Path) -> tuple[int, int]:
    with open(src, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 0, 0
    keep = [r for r in rows if not restricted_row(r)]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(keep)
    return len(keep), len(rows) - len(keep)


def copy_any(src: Path, dst: Path, log: list) -> None:
    if src.suffix == ".jsonl":
        k, d = copy_jsonl(src, dst)
    elif src.suffix == ".csv":
        k, d = copy_csv(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        k, d = 1, 0
    log.append((str(dst.relative_to(STAGE)), k, d))


def copy_tree(src: Path, dst: Path, log: list, skip=(".done", "__pycache__")) -> None:
    for p in sorted(src.rglob("*")):
        if p.is_file() and not any(s in p.parts for s in skip):
            copy_any(p, dst / p.relative_to(src), log)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def scan_secrets(stage: Path) -> list[str]:
    hits = []
    for p in stage.rglob("*"):
        if p.is_file() and SECRET.search(p.read_text(errors="ignore")):
            hits.append(str(p.relative_to(stage)))
    return hits


CARD = """---
license: other
license_name: mixed-see-card
pretty_name: SafeAdapt-Math run data
tags: [education, accessibility, math-word-problems, llm-evaluation]
---
# SafeAdapt-Math: run data backup (private)

Data behind *SafeAdapt-Math: auditing and verifying LLM accessibility rewrites of math word problems*
(Harvard COMPSCI 2880, Fall 2026). Code: https://github.com/harshitaggarwal01/cs2880 at commit `{commit}`.

**Keep this repo private.** `calibration/` and `annotations/*/` contain `KEY_DO_NOT_OPEN.csv`, which unblinds the
annotation sheets.

| Folder | What | Why it is backed up |
|---|---|---|
| `frozen/` | Frozen sample (seed 2880): 10 dev, 100 main (GSM8K), 12 ASDiv, GSM1K ids only | Defines the study |
| `runs/<run_id>/` | Real API rewrites, verifier rows (rules, critic, program), extraction cache, cost ledger, frozen config, analysis | API outputs cannot be regenerated identically |
| `annotations/<run_id>/` | Blind sheets, key, adjudicated labels | Hours of human labelling |
| `pilot_oct16/` | First pilot (subagent outputs, preliminary AI labels) | Historical record of the earlier finding |
| `calibration/` | 70-item rubric calibration sheets | Human labels in progress |
| `prompts/`, `schemas/`, `configs/` | Exact prompts and configs used | Provenance |

**Licences.** GSM8K-derived text: MIT. ASDiv-derived text: CC BY-NC 4.0 (non-commercial; attribution to Miao et al.
2020). GSM1K and GSM-IC declare no licence, so only their ids are included and every row carrying their text is
removed before upload. Model outputs were produced with Anthropic models under their terms.

**Caveats.** Checker decisions are not human labels. Pilot labels are preliminary. Same-family caveat: the
`anthropic-v1` rewriters and critic are all Claude models.

Files: {n_files} · built from commit `{commit}` · see `CHECKSUMS.sha256`.
"""


def build(runs: list[str]) -> list:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    log: list = []
    for name in ("dev.jsonl", "main.jsonl", "ext_asdiv.jsonl", "ext_gsm1k_ids.jsonl", "MANIFEST.json"):
        if (ROOT / "data/frozen" / name).exists():
            copy_any(ROOT / "data/frozen" / name, STAGE / "frozen" / name, log)
    for run in runs:
        if run.endswith("-mock") or run.startswith("external"):
            continue
        if (ROOT / "data/outputs" / run).exists():
            copy_tree(ROOT / "data/outputs" / run, STAGE / "runs" / run, log)
        if (ROOT / "data/annotations" / run).exists():
            copy_tree(ROOT / "data/annotations" / run, STAGE / "annotations" / run, log)
    copy_tree(ROOT / "pilot", STAGE / "pilot_oct16", log)
    if (ROOT / "data/calibration").exists():
        copy_tree(ROOT / "data/calibration", STAGE / "calibration", log)
    copy_tree(ROOT / "prompts", STAGE / "prompts", log)
    copy_tree(ROOT / "schemas", STAGE / "schemas", log)
    for cfg in sorted(ROOT.glob("config*.yaml")):
        if cfg.name != "config.yaml":
            copy_any(cfg, STAGE / "configs" / cfg.name, log)
    if (ROOT / "docs/run_examples.md").exists():
        copy_any(ROOT / "docs/run_examples.md", STAGE / "docs" / "run_examples.md", log)
    hits = scan_secrets(STAGE)
    if hits:
        shutil.rmtree(STAGE)
        raise SystemExit(f"possible secret found in {hits}; nothing staged or uploaded")
    files = sorted(p for p in STAGE.rglob("*") if p.is_file())
    (STAGE / "CHECKSUMS.sha256").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(STAGE)}\n" for p in files))
    (STAGE / "README.md").write_text(CARD.format(commit=git_commit(), n_files=len(files) + 2))
    return log


def push(repo: str) -> str:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is not set: add a write token to the environment's secrets as HF_TOKEN")
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    info = api.repo_info(repo, repo_type="dataset")
    if not getattr(info, "private", True):
        raise SystemExit(f"{repo} exists and is PUBLIC; refusing to upload keys and labels to a public repo")
    commit = api.upload_folder(folder_path=str(STAGE), repo_id=repo, repo_type="dataset",
                               commit_message=f"Backup from cs2880@{git_commit()[:7]}")
    return str(commit)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--runs", nargs="*", default=None, help="run ids under data/outputs (default: all non-mock)")
    ap.add_argument("--push", action="store_true", help="upload after building (needs HF_TOKEN with write access)")
    args = ap.parse_args()
    runs = args.runs if args.runs is not None else sorted(
        p.name for p in (ROOT / "data/outputs").iterdir() if p.is_dir())
    log = build(runs)
    dropped = sum(d for _, _, d in log)
    print(f"staged {len(log)} files in {STAGE} ({dropped} restricted rows removed)")
    for path, k, d in log:
        print(f"  {path}  rows={k}" + (f"  dropped={d}" if d else ""))
    if args.push:
        print("uploaded:", push(args.repo))


if __name__ == "__main__":
    main()
