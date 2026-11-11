"""Package a redistributable release bundle from one run.

  python src/release.py --run data/outputs/<run_id> --out data/release [--annotations data/annotations/<run_id>]

Writes under --out:
  sources.jsonl          frozen sources; GSM1K (and GSM-IC) rows are ids only (text null)
  adaptations.jsonl      generations + ablation + baseline + repairs, minus rows that may not be redistributed
  verifier.jsonl         verifier rows for the kept output_ids (no per-call critic/extractor metadata)
  labels.csv             adjudicated labels joined with the annotation key (needs --annotations)
  ledger_summary.csv     aggregate cost only (if <run>/ledger.csv exists)
  analysis/*.csv, *.json  copied from <run>/analysis if present
  config.frozen.yaml, prompts/, LICENSES.md, CHECKSUMS.sha256, MANIFEST.json

What may leave the repository (docs/plan/PHASE4.md "What may be released"):
  GSM8K-derived  text, adaptations, labels  (MIT)
  ASDiv          text, adaptations, labels  (CC BY-NC 4.0, attribution)
  GSM1K          ids and labels only; adaptations paraphrase the text, so they stay local
  GSM-IC         treated like GSM1K: the repository declares no licence for the added sentences
  red-team and external-tool captures: never released row by row

The bundle is deterministic: the same inputs give byte-identical files (no timestamps of our own),
so `make release` reproduces CHECKSUMS.sha256 until the commit SHA recorded in MANIFEST.json changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from common import FROZEN, PROMPTS, ROOT, primary_verify_files, read_jsonl, write_jsonl

GEN_FILES = ["generations.jsonl", "ablation_generations.jsonl", "baseline.jsonl", "repairs.jsonl"]
ASDIV_ATTRIBUTION = "ASDiv, Miao, Liang & Su (ACL 2020), CC BY-NC 4.0"
GSM1K_NOTE = ("GSM1K (Scale AI) declares no licence on its dataset card: only row ids are released; "
              "fetch the text yourself with src/fetch_data.py --gsm1k")
GSMIC_NOTE = ("GSM-IC (Shi et al., ICML 2023) ships no LICENSE file: only row ids are released; "
              "fetch the text yourself with src/fetch_data.py --gsmic")
RESTRICTED = {"gsm1k": GSM1K_NOTE, "gsmic": GSMIC_NOTE}      # dataset -> licence_note; text and adaptations withheld
RAW_OK = {"gsm8k", "asdiv"}                                   # datasets whose raw_output may be released
SOURCE_ID_KEYS = ["source_id", "dataset", "split", "row", "partition", "text", "source_sha256"]
ADAPT_KEYS = ["output_id", "generator", "transformation", "source_id", "adapted_problem", "status", "prompt_version",
              "prompt_sha256", "returned_model", "timestamp"]
ADAPT_EXTRA = ["run_id", "dataset", "partition", "repair_of", "verifier_decision_before", "changes", "parse_error"]
VERIFY_DROP = ("extract_meta", "raw_output")
LABEL_TEXT_COLUMNS = ["original", "adaptation"]


# ------------------------------------------------------------------ helpers

def dataset_of(row: dict, source_ds: dict[str, str]) -> str:
    """Dataset of a generation row: its own field, else the frozen source, else the source_id prefix."""
    sid = row.get("source_id") or ""
    return row.get("dataset") or source_ds.get(sid) or sid.split("-")[0]


def restricted_dataset(row: dict, source_ds: dict[str, str]) -> str | None:
    """Restricted dataset name if any known label of this row's source says so (conservative)."""
    sid = row.get("source_id") or ""
    for ds in (row.get("dataset"), source_ds.get(sid), sid.split("-")[0]):
        if ds in RESTRICTED:
            return ds
    return None


def is_redteam(row: dict) -> bool:
    return str(row.get("generator") or "").startswith("redteam:")


def is_external(row: dict) -> bool:
    return row.get("transformation") == "external"


def license_fields(dataset: str) -> dict:
    if dataset == "gsm8k":
        return {"license": "MIT"}
    if dataset == "asdiv":
        return {"attribution": ASDIV_ATTRIBUTION}
    return {}


def git_commit() -> tuple[str | None, bool | None]:
    """(HEAD sha, working tree dirty) or (None, None) outside a git checkout."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True,
                                    check=True).stdout.strip())
        return sha, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def count(d: dict, key: str, n: int = 1) -> None:
    d[key] = d.get(key, 0) + n


def read_rows(path: Path) -> list[dict]:
    return read_jsonl(path) if path.exists() else []


# ------------------------------------------------------------------ bundle parts

def build_sources(excluded: dict) -> tuple[list[dict], dict[str, str]]:
    """Frozen sources with licence fields; restricted datasets keep ids only. Returns (rows, source_id -> dataset)."""
    rows: list[dict] = []
    source_ds: dict[str, str] = {}
    seen: set[str] = set()
    for path in sorted(Path(FROZEN).glob("*.jsonl")):
        for r in read_jsonl(path):
            sid = r["source_id"]
            source_ds[sid] = r.get("dataset") or sid.split("-")[0]
            if sid in seen:                      # e.g. ext_gsm1k.jsonl (local text) next to ext_gsm1k_ids.jsonl
                continue
            seen.add(sid)
            ds = source_ds[sid]
            if ds in RESTRICTED:
                out = {k: r[k] for k in SOURCE_ID_KEYS if k in r}
                out["text"] = None
                out["license_note"] = RESTRICTED[ds]
                count(excluded["sources_text_withheld"], ds)
            else:
                out = dict(r)
                out.update(license_fields(ds))
            rows.append(out)
    return rows, source_ds


def adaptation_record(g: dict, ds: str) -> dict:
    rec = {k: g.get(k) for k in ADAPT_KEYS}
    rec.update({k: g[k] for k in ADAPT_EXTRA if k in g})
    rec.update(license_fields(ds))
    if ds in RAW_OK and "raw_output" in g:
        rec["raw_output"] = g["raw_output"]
    return rec


def build_adaptations(run_dir: Path, source_ds: dict[str, str], excluded: dict) -> tuple[list[dict], dict[str, str], dict]:
    """(kept rows, withheld output_id -> reason, kept-row counts per input file).

    Reason priority: red-team generator, external transformation, restricted source dataset."""
    kept: list[dict] = []
    withheld: dict[str, str] = {}
    by_file: dict[str, int] = {}
    for name in GEN_FILES:
        for g in read_rows(run_dir / name):
            oid = g["output_id"]
            if is_redteam(g):
                reason = "redteam_generator"
            elif is_external(g):
                reason = "external_transformation"
            elif (rds := restricted_dataset(g, source_ds)):
                reason = f"{rds}_source"
            else:
                kept.append(adaptation_record(g, dataset_of(g, source_ds)))
                count(by_file, name)
                continue
            withheld[oid] = reason
            count(excluded["adaptations"], reason)
    return kept, withheld, by_file


def build_verifier(run_dir: Path, keep_ids: set[str], excluded: dict) -> list[dict]:
    """Verify rows for kept output_ids; one row per (output_id, layers) so derived subsets are not duplicated."""
    rows, seen = [], set()
    for path in primary_verify_files(run_dir):
        for v in read_jsonl(path):
            if v["output_id"] not in keep_ids:
                count(excluded["verifier"], "output_not_released")
                continue
            key = (v["output_id"], tuple(v.get("layers") or ()))
            if key in seen:
                continue
            seen.add(key)
            row = {k: x for k, x in v.items() if k not in VERIFY_DROP}
            if isinstance(row.get("critic"), dict):
                row["critic"] = {k: x for k, x in row["critic"].items() if k != "_meta"}
            rows.append(row)
    return rows


def build_labels(annotations_dir: Path, source_ds: dict[str, str], excluded: dict) -> pd.DataFrame | None:
    """Adjudicated labels + key. Our labels are released for every source, restricted ones included, but free text that
    may quote the withheld paraphrase (evidence, notes) is blanked for them. Red-team/external rows are dropped."""
    lab_path, key_path = annotations_dir / "adjudicated.csv", annotations_dir / "KEY_DO_NOT_OPEN.csv"
    if not lab_path.exists() or not key_path.exists():
        return None
    labels = pd.read_csv(lab_path)
    if "annotator" in labels and labels["annotator"].eq("ADJ").any():
        labels = labels[labels["annotator"] == "ADJ"]
    df = labels.merge(pd.read_csv(key_path), on="annotation_id", how="inner", suffixes=("", "_key"))
    df = df.drop(columns=[c for c in LABEL_TEXT_COLUMNS if c in df])
    drop = df["generator"].astype(str).str.startswith("redteam:") | df["transformation"].eq("external")
    count(excluded["labels"], "redteam_or_external", int(drop.sum()))
    df = df[~drop].copy()
    restricted = df["source_id"].map(lambda s: source_ds.get(s) or str(s).split("-")[0]).isin(RESTRICTED)
    for col in ("evidence", "notes"):
        if col in df:
            df[col] = df[col].astype(object)
            df.loc[restricted, col] = ""
    count(excluded["labels"], "free_text_blanked_restricted_source", int(restricted.sum()))
    return df.reset_index(drop=True)


def ledger_summary(run_dir: Path) -> pd.DataFrame | None:
    path = run_dir / "ledger.csv"
    if not path.exists():
        return None
    led = pd.read_csv(path)
    for c in ("generator", "transformation"):
        led[c] = led[c].fillna("-")
    g = led.groupby(["stage", "generator", "transformation"]).agg(
        calls=("stage", "size"), input_tokens=("input_tokens", "sum"), output_tokens=("output_tokens", "sum"),
        thinking_tokens=("thinking_tokens", "sum"), usd=("usd", "sum"), mean_latency_s=("latency_s", "mean")).reset_index()
    total = {"stage": "total", "generator": "-", "transformation": "-", "calls": len(led),
             "input_tokens": led["input_tokens"].sum(), "output_tokens": led["output_tokens"].sum(),
             "thinking_tokens": led["thinking_tokens"].sum(), "usd": led["usd"].sum(),
             "mean_latency_s": led["latency_s"].mean()}
    return pd.concat([g, pd.DataFrame([total])], ignore_index=True)


def licenses_md(excluded: dict) -> str:
    return f"""# Licences and attribution

Status: **proposed; confirm with team** (and with course staff for GSM1K / GSM-IC) before publishing.

| Part of this bundle | Terms |
|---|---|
| GSM8K problems and their adaptations (`dataset` = `gsm8k`) | MIT. Source: Cobbe et al. (2021), github.com/openai/grade-school-math. |
| ASDiv problems and their adaptations (`dataset` = `asdiv`) | CC BY-NC 4.0, non-commercial use only. Attribution: {ASDIV_ATTRIBUTION}. Source: github.com/chaochun/nlu-asdiv-dataset. |
| GSM1K (`dataset` = `gsm1k`) | **Row ids only.** The Hugging Face card (ScaleAI/gsm1k) declares no licence, so no problem text and no adaptation of it is included (an adaptation paraphrases the text). Our human labels for these items are included; free-text evidence and notes are blanked. |
| GSM-IC (`dataset` = `gsmic`) | **Row ids only**, treated like GSM1K: the repository ships no LICENSE file. |
| Red-team and external-tool captures | Not included row by row (tool terms of service); aggregate figures appear in `analysis/` only. |
| Our code, prompts, human labels, verifier outputs and analysis tables | CC BY 4.0 (proposed). Code in the repository may carry a separate licence. |

The bundle as a whole inherits the most restrictive included term: **CC BY-NC 4.0 applies to the ASDiv rows, so
treat the release as non-commercial unless you filter `sources.jsonl` and `adaptations.jsonl` to `license: MIT` rows.**

Withheld at packaging time: {json.dumps(excluded["sources_text_withheld"], sort_keys=True)} source texts;
{json.dumps(excluded["adaptations"], sort_keys=True)} adaptation rows.
"""


def sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksums(out_dir: Path) -> int:
    """sha256sum-style lines for every file under out_dir except CHECKSUMS.sha256 itself, sorted by path."""
    self_path = out_dir / "CHECKSUMS.sha256"
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p != self_path)
    lines = [f"{sha256_bytes(p)}  {p.relative_to(out_dir).as_posix()}" for p in files]
    self_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def clean_previous(out_dir: Path) -> None:
    """Remove only what this script writes, so stale files never reach CHECKSUMS.sha256."""
    for name in ("sources.jsonl", "adaptations.jsonl", "verifier.jsonl", "labels.csv", "ledger_summary.csv",
                 "config.frozen.yaml", "LICENSES.md", "CHECKSUMS.sha256", "MANIFEST.json"):
        (out_dir / name).unlink(missing_ok=True)
    for name in ("analysis", "prompts"):
        shutil.rmtree(out_dir / name, ignore_errors=True)


# ------------------------------------------------------------------ main entry

def package(run_dir: Path, out_dir: Path, annotations_dir: Path | None = None) -> dict:
    """Build the release bundle under out_dir and return the manifest dict (also written as MANIFEST.json)."""
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_previous(out_dir)
    excluded: dict = {"sources_text_withheld": {}, "adaptations": {}, "verifier": {}, "labels": {}}
    files: dict[str, dict] = {}

    sources, source_ds = build_sources(excluded)
    write_jsonl(out_dir / "sources.jsonl", sources)
    files["sources.jsonl"] = {"rows": len(sources), "text_null": sum(1 for r in sources if r.get("text") is None)}

    adaptations, withheld, by_file = build_adaptations(run_dir, source_ds, excluded)
    write_jsonl(out_dir / "adaptations.jsonl", adaptations)
    files["adaptations.jsonl"] = {"rows": len(adaptations), "rows_by_input_file": by_file}

    verifier = build_verifier(run_dir, {r["output_id"] for r in adaptations}, excluded)
    write_jsonl(out_dir / "verifier.jsonl", verifier)
    files["verifier.jsonl"] = {"rows": len(verifier)}

    labels = build_labels(Path(annotations_dir), source_ds, excluded) if annotations_dir else None
    if labels is not None:
        labels.to_csv(out_dir / "labels.csv", index=False)
        files["labels.csv"] = {"rows": len(labels)}
    else:
        files["labels.csv"] = {"rows": 0, "note": "not written: no adjudicated.csv + KEY_DO_NOT_OPEN.csv in --annotations"}

    summary = ledger_summary(run_dir)
    if summary is not None:
        summary.to_csv(out_dir / "ledger_summary.csv", index=False)
        files["ledger_summary.csv"] = {"rows": len(summary)}

    analysis = sorted((run_dir / "analysis").glob("*.[cj]s[vo]n")) if (run_dir / "analysis").is_dir() else []
    if analysis:
        (out_dir / "analysis").mkdir()
        for p in analysis:
            shutil.copyfile(p, out_dir / "analysis" / p.name)
        files["analysis/"] = {"files": [p.name for p in analysis]}

    if (run_dir / "config.frozen.yaml").exists():
        shutil.copyfile(run_dir / "config.frozen.yaml", out_dir / "config.frozen.yaml")
        files["config.frozen.yaml"] = {"sha256": sha256_bytes(out_dir / "config.frozen.yaml")}
    prompt_files = sorted(Path(PROMPTS).glob("*.txt"))
    if prompt_files:
        (out_dir / "prompts").mkdir()
        for p in prompt_files:
            shutil.copyfile(p, out_dir / "prompts" / p.name)
        files["prompts/"] = {"files": [p.name for p in prompt_files]}

    (out_dir / "LICENSES.md").write_text(licenses_md(excluded), encoding="utf-8")
    sha, dirty = git_commit()
    manifest = {"run_id": run_dir.name, "commit": sha, "commit_dirty": dirty, "files": files,
                "excluded": {**excluded, "withheld_output_ids": len(withheld)}, "text_redistribution": {
                    "released_datasets": sorted(RAW_OK), "ids_only_datasets": sorted(RESTRICTED)}}
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_checksums(out_dir)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="data/outputs/<run_id>")
    ap.add_argument("--out", default="data/release")
    ap.add_argument("--annotations", default=None, help="data/annotations/<run_id> (adjudicated.csv + KEY_DO_NOT_OPEN.csv)")
    args = ap.parse_args()
    manifest = package(Path(args.run), Path(args.out), Path(args.annotations) if args.annotations else None)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"release written to {args.out}")


if __name__ == "__main__":
    main()
