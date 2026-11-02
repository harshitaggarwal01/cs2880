"""Failure gallery: verbatim UNSAFE examples from adjudicated labels, with labels and verifier verdicts.

  python src/failure_gallery.py --run data/outputs/<run_id> --labels data/annotations/<run_id>/adjudicated.csv \
      --key data/annotations/<run_id>/KEY_DO_NOT_OPEN.csv --out docs/results/failure_gallery.md [--max-per-code 3]

UNSAFE = not SAFE (evaluate.derive). Examples are grouped by leakage_type and by failure code, up to --max-per-code each
(first output_ids in sorted order, so the gallery is deterministic and not hand-picked). Each example shows the original
(frozen source), the adaptation (run generations or repairs), the human labels and evidence, the verifier decision and
reasons, and a provenance line. GSM1K and GSM-IC items are left out because their text must not be redistributed.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from common import FROZEN, read_jsonl
from evaluate import derive

GEN_FILES = ["generations.jsonl", "ablation_generations.jsonl", "baseline.jsonl", "repairs.jsonl"]
NO_TEXT = {"gsm1k", "gsmic"}                  # datasets whose text we do not redistribute
LABEL_FIELDS = ["math_fidelity", "target_preserved", "solvability_changed", "ambiguity", "leakage_level",
                "leakage_type", "presentation", "failure_codes", "confidence"]


def fence(text: str) -> str:
    """A fenced block whose fence is longer than any backtick run inside the text."""
    longest = max((len(m) for m in re.findall(r"`+", text or "")), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}text\n{(text or '').rstrip()}\n{ticks}"


def split_codes(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [c for c in re.split(r"[;,|\s]+", str(value)) if c and c != "nan"]


def load_sources() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(Path(FROZEN).glob("*.jsonl")):
        for r in read_jsonl(p):
            out.setdefault(r["source_id"], r)
            if r.get("text"):
                out[r["source_id"]] = r
    return out


def load_generations(run_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in GEN_FILES:
        path = run_dir / name
        if path.exists():
            out.update({g["output_id"]: g for g in read_jsonl(path)})
    return out


def load_verdicts(run_dir: Path) -> dict[str, dict]:
    """output_id -> verifier row; the row with the most layers wins (full det+critic+program over derived subsets)."""
    out: dict[str, dict] = {}
    for path in sorted(run_dir.glob("*.verify-*.jsonl")):
        for v in read_jsonl(path):
            old = out.get(v["output_id"])
            if old is None or len(v.get("layers") or ()) > len(old.get("layers") or ()):
                out[v["output_id"]] = v
    return out


def unsafe_items(labels_csv: str | Path, key_csv: str | Path | None) -> pd.DataFrame:
    df = pd.read_csv(labels_csv)
    if "annotator" in df and df["annotator"].eq("ADJ").any():
        df = df[df["annotator"] == "ADJ"]
    if key_csv and "output_id" not in df:
        df = df.merge(pd.read_csv(key_csv), on="annotation_id", suffixes=("", "_key"))
    for col in ("failure_codes", "leakage_type", "abstention_appropriate"):   # derive() needs these; absent -> empty
        if col not in df:
            df[col] = ""
    df = derive(df)
    return df[df["SAFE"] == 0].sort_values("output_id").reset_index(drop=True)


def example_md(row: pd.Series, gens: dict, sources: dict, verdicts: dict) -> str:
    oid = row["output_id"]
    g = gens.get(oid, {})
    src = sources.get(row.get("source_id") or g.get("source_id"), {})
    v = verdicts.get(oid)
    lines = [f"**{oid}**", "",
             f"Provenance: output_id `{oid}` · generator `{g.get('generator', row.get('generator', '?'))}` · "
             f"transformation `{g.get('transformation', row.get('transformation', '?'))}` · "
             f"prompt_version `{g.get('prompt_version', '?')}` · source `{g.get('source_id', row.get('source_id', '?'))}`",
             "", "Original:", "", fence(src.get("text")), "", "Adaptation:", "",
             fence(g.get("adapted_problem") or g.get("raw_output"))]
    labels = ", ".join(f"{f}={row[f]}" for f in LABEL_FIELDS if f in row and not pd.isna(row[f]))
    lines += ["", f"Labels: {labels}"]
    ev = row.get("evidence")
    if isinstance(ev, str) and ev.strip():
        lines += ["", "Evidence:", "", fence(ev)]
    if v:
        reasons = "; ".join(v.get("reasons") or []) or "none"
        lines += ["", f"Verifier: **{v.get('decision')}** (layers: {', '.join(v.get('layers') or [])}); reasons: {reasons}"]
    else:
        lines += ["", "Verifier: no verifier row found for this output"]
    return "\n".join(lines)


def build(run_dir: Path, labels_csv, key_csv, out_md: Path, max_per_code: int = 3) -> None:
    run_dir, out_md = Path(run_dir), Path(out_md)
    unsafe = unsafe_items(labels_csv, key_csv)
    sources, gens, verdicts = load_sources(), load_generations(run_dir), load_verdicts(run_dir)

    def dataset(row) -> str:
        sid = str(row.get("source_id") or gens.get(row["output_id"], {}).get("source_id") or "")
        return (sources.get(sid, {}).get("dataset")) or sid.split("-")[0]

    unsafe["_dataset"] = unsafe.apply(dataset, axis=1)
    skipped = unsafe[unsafe["_dataset"].isin(NO_TEXT)]
    shown = unsafe[~unsafe["_dataset"].isin(NO_TEXT)]
    groups: dict[str, dict[str, list[int]]] = {"leakage_type": {}, "failure_code": {}}
    for i, row in shown.iterrows():
        lt = str(row.get("leakage_type") or "").strip()
        if lt and lt not in ("NONE", "nan"):
            groups["leakage_type"].setdefault(lt, []).append(i)
        for code in split_codes(row.get("failure_codes")):
            groups["failure_code"].setdefault(code, []).append(i)

    out = ["# Failure gallery", "",
           "Verbatim UNSAFE items from the adjudicated labels (UNSAFE = not SAFE, `evaluate.derive`). "
           f"Up to {max_per_code} examples per group, first by output_id (not hand-picked). "
           "A group's size is the number of UNSAFE items carrying that label, not a rate.", "",
           f"Run: `{run_dir.name}` · UNSAFE items: {len(unsafe)} · shown from: {len(shown)}", ""]
    if len(skipped):
        by_ds = skipped["_dataset"].value_counts().to_dict()
        out += [f"> Excluded: {len(skipped)} UNSAFE items from sources whose text may not be redistributed "
                f"({', '.join(f'{k}: {v}' for k, v in sorted(by_ds.items()))}). Their labels are in the release; their text is not.", ""]
    if not len(shown):
        out += ["No UNSAFE items to show.", ""]
    for kind, title in (("leakage_type", "By leakage type"), ("failure_code", "By failure code")):
        if not groups[kind]:
            continue
        out += [f"## {title}", ""]
        for name in sorted(groups[kind]):
            idx = groups[kind][name]
            out += [f"### {name} ({len(idx)} UNSAFE item{'s' if len(idx) != 1 else ''})", ""]
            for i in idx[:max_per_code]:
                out += [example_md(shown.loc[i], gens, sources, verdicts), ""]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"{len(shown)} UNSAFE items in {sum(len(g) for g in groups.values())} groups -> {out_md}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="data/outputs/<run_id>")
    ap.add_argument("--labels", required=True, help="adjudicated.csv")
    ap.add_argument("--key", required=True, help="KEY_DO_NOT_OPEN.csv")
    ap.add_argument("--out", default="docs/results/failure_gallery.md")
    ap.add_argument("--max-per-code", type=int, default=3)
    args = ap.parse_args()
    build(Path(args.run), args.labels, args.key, Path(args.out), args.max_per_code)


if __name__ == "__main__":
    main()
