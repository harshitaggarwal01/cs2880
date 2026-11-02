"""Markdown report with figures for one run.

  # pipeline report (no human labels yet): counts, verifier decisions, flag codes, cost, readability
  python src/report.py --run data/outputs/main-v1
  # full report once labels exist (labels/key are auto-detected at data/annotations/<run_id>/ when present)
  python src/report.py --run data/outputs/main-v1 --labels data/annotations/main-v1/adjudicated.csv \
      --key data/annotations/main-v1/KEY_DO_NOT_OPEN.csv [--out docs/results/main-v1_report.md] \
      [--fig-dir docs/results/figures/main-v1]

Reads from the run folder: generations.jsonl, ablation_generations.jsonl, pilot_generations.jsonl, baseline*.jsonl,
repairs.jsonl, *.verify-*.jsonl and ledger.csv (each optional). Figures are PNG (150 dpi) and are linked relatively
from the Markdown file.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import evaluate as ev  # noqa: E402
from common import ROOT, read_jsonl  # noqa: E402

# Okabe-Ito colour-blind-safe palette
PAL = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442", "#000000"]
DECISION_COLORS = {"PASS": "#009E73", "REVIEW": "#E69F00", "REJECT": "#D55E00"}
GEN_FILES = [("generations.jsonl", "main"), ("ablation_generations.jsonl", "ablation"),
             ("pilot_generations.jsonl", "pilot"), ("repairs.jsonl", "repair")]


# ------------------------------------------------------------------ loading

def load_generations(run_dir: Path) -> pd.DataFrame:
    """All generation-like rows in the run folder with columns kind, output_id, generator, transformation, ..."""
    paths = [(run_dir / f, kind) for f, kind in GEN_FILES] + [(p, "baseline") for p in sorted(run_dir.glob("baseline*.jsonl")) if ".verify-" not in p.name]
    rows = []
    for path, kind in paths:
        if path.exists():
            for i, r in enumerate(read_jsonl(path)):
                gen = r.get("generator") or r.get("model") or "?"
                rows.append({"kind": kind, "output_id": r.get("output_id") or f"{kind}|{gen}|{r.get('source_id')}|{i}",
                             "generator": gen, "transformation": r.get("transformation", "?"),
                             "source_id": r.get("source_id"), "status": r.get("status"),
                             "parse_error": bool(r.get("parse_error")), "api_error": bool(r.get("error")),
                             "has_text": bool(r.get("adapted_problem"))})
    cols = ["kind", "output_id", "generator", "transformation", "source_id", "status", "parse_error", "api_error",
            "has_text"]
    return pd.DataFrame(rows, columns=cols)


def load_verify(run_dir: Path) -> dict[str, list[dict]]:
    """Verification files keyed by layer set (e.g. 'critic+det+program'); the file with the most layers sorts first."""
    out: dict[str, list[dict]] = {}
    for path in sorted(run_dir.glob("*.verify-*.jsonl")):
        rows = read_jsonl(path)
        if rows:
            label = "+".join(rows[0].get("layers") or [path.stem.split(".verify-")[-1]])
            out.setdefault(label, []).extend(rows)
    return dict(sorted(out.items(), key=lambda kv: -len(kv[0].split("+"))))


def load_ledger(run_dir: Path) -> pd.DataFrame | None:
    path = run_dir / "ledger.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return df if len(df) else None


# ------------------------------------------------------------------ pipeline tables

def counts_table(gens: pd.DataFrame) -> pd.DataFrame:
    g = gens.assign(rewritten=gens["status"].eq("REWRITTEN"), no_rewrite=gens["status"].eq("NO_REWRITE_NEEDED"),
                    free_text=gens["status"].eq("FREE_TEXT"))
    return (g.groupby(["kind", "generator", "transformation"])
            .agg(n=("output_id", "size"), rewritten=("rewritten", "sum"), no_rewrite=("no_rewrite", "sum"),
                 free_text=("free_text", "sum"), parse_error=("parse_error", "sum"), api_error=("api_error", "sum"))
            .reset_index())


def decision_table(rows: list[dict], gens: pd.DataFrame) -> pd.DataFrame:
    cond = gens.set_index("output_id")[["generator", "transformation"]]
    v = pd.DataFrame({"output_id": [r["output_id"] for r in rows], "decision": [r["decision"] for r in rows]})
    v = v.join(cond, on="output_id").fillna({"generator": "?", "transformation": "?"})
    t = pd.crosstab([v["generator"], v["transformation"]], v["decision"])
    for d in ("PASS", "REVIEW", "REJECT"):
        if d not in t:
            t[d] = 0
    t = t[["PASS", "REVIEW", "REJECT"]]
    t["n"] = t.sum(axis=1)
    for d in ("PASS", "REVIEW", "REJECT"):
        t[f"{d}_share"] = t[d] / t["n"]
    return t.reset_index()


def flag_table(rows: list[dict]) -> pd.DataFrame:
    """Deterministic flag codes: number and share of items carrying each code."""
    recs = [{"code": f["code"], "severity": f["severity"], "output_id": r["output_id"]}
            for r in rows for f in (r.get("deterministic") or {}).get("flags", [])]
    cols = ["code", "severity", "n_items", "share"]
    if not recs:
        return pd.DataFrame(columns=cols)
    t = pd.DataFrame(recs).groupby(["code", "severity"])["output_id"].nunique().rename("n_items").reset_index()
    t["share"] = t["n_items"] / max(1, len(rows))
    return t.sort_values("n_items", ascending=False)[cols].reset_index(drop=True)


def readability_table(rows: list[dict], gens: pd.DataFrame) -> pd.DataFrame:
    recs = [{"output_id": r["output_id"], "source_fkgl": rd.get("source_fkgl"), "candidate_fkgl": rd.get("candidate_fkgl")}
            for r in rows if (rd := (r.get("deterministic") or {}).get("readability"))]
    cols = ["generator", "transformation", "n", "source_fkgl", "candidate_fkgl", "delta_fkgl"]
    if not recs:
        return pd.DataFrame(columns=cols)
    v = pd.DataFrame(recs).join(gens.set_index("output_id")[["generator", "transformation"]], on="output_id")
    v = v.fillna({"generator": "?", "transformation": "?"})
    v["delta_fkgl"] = v["candidate_fkgl"] - v["source_fkgl"]
    return (v.groupby(["generator", "transformation"])
            .agg(n=("output_id", "size"), source_fkgl=("source_fkgl", "mean"), candidate_fkgl=("candidate_fkgl", "mean"),
                 delta_fkgl=("delta_fkgl", "mean")).reset_index())[cols]


def ledger_tables(led: pd.DataFrame, gens: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(summary per stage, USD per 100 items by condition and stage)."""
    for c in ("input_tokens", "output_tokens", "thinking_tokens", "usd", "latency_s"):
        if c not in led:
            led[c] = 0.0
    summary = (led.groupby("stage")
               .agg(calls=("stage", "size"), input_tokens=("input_tokens", "sum"), output_tokens=("output_tokens", "sum"),
                    thinking_tokens=("thinking_tokens", "sum"), usd=("usd", "sum"), mean_latency_s=("latency_s", "mean"))
               .reset_index())
    led = led.assign(condition=led.get("generator", pd.Series("?", index=led.index)).fillna("(none)").astype(str)
                     + "|" + led.get("transformation", pd.Series("?", index=led.index)).fillna("-").astype(str))
    n_items = led[led["stage"] == "gen"].groupby("condition")["output_id"].nunique()
    if n_items.empty:
        g = gens[gens["kind"] != "repair"]
        n_items = (g["generator"] + "|" + g["transformation"]).value_counts()
    per = led.groupby(["condition", "stage"])["usd"].sum().reset_index()
    per["items"] = per["condition"].map(n_items)
    per["usd_per_100"] = 100 * per["usd"] / per["items"].where(per["items"] > 0)
    return summary, per


# ------------------------------------------------------------------ figures

def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)


def fig_rates(rates: pd.DataFrame, path: Path) -> Path | None:
    sub = rates[rates["outcome"].isin(["SAFE", "SAFE_AND_USEFUL"])]
    if sub.empty:
        return None
    sub = sub.assign(cond=sub["model"] + "\n" + sub["transformation"])
    conds = list(dict.fromkeys(sub["cond"]))
    fig, ax = plt.subplots(figsize=(max(5, 1.0 * len(conds) + 2), 4))
    for j, (outcome, color) in enumerate((("SAFE", PAL[0]), ("SAFE_AND_USEFUL", PAL[1]))):
        s = sub[sub["outcome"] == outcome].set_index("cond").reindex(conds)
        x = np.arange(len(conds)) + (j - 0.5) * 0.38
        err = np.vstack([s["rate"] - s["ci_lo"], s["ci_hi"] - s["rate"]]).clip(min=0)
        ax.bar(x, s["rate"], 0.38, yerr=err, capsize=3, color=color, label=outcome)
    ax.set_xticks(range(len(conds)), conds, fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("rate (95% source-cluster bootstrap CI)")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    return _save(fig, path)


def fig_verifier(abl: pd.DataFrame, path: Path) -> Path | None:
    if abl.empty:
        return None
    subsets = [s for s in ("overall", "realistic", "constrained") if s in set(abl["subset"])]
    fig, axes = plt.subplots(1, len(subsets), figsize=(4.2 * len(subsets), 4), sharey=True, squeeze=False)
    sets = list(dict.fromkeys(abl["layers"]))
    for ax, subset in zip(axes[0], subsets):
        for k, ls in enumerate(sets):
            s = abl[(abl["subset"] == subset) & (abl["layers"] == ls)].set_index("operating_point")
            if not {"FLAG_REJECT", "FLAG_ANY"} <= set(s.index):
                continue
            xs, ys = s.loc[["FLAG_REJECT", "FLAG_ANY"], "flag_rate"], s.loc[["FLAG_REJECT", "FLAG_ANY"], "recall_unsafe"]
            ax.plot(xs, ys, "-", color=PAL[k], alpha=0.5)
            for op, marker in (("FLAG_REJECT", "o"), ("FLAG_ANY", "s")):
                r = s.loc[op]
                ax.errorbar(r["flag_rate"], r["recall_unsafe"], yerr=[[max(0, r["recall_unsafe"] - r["recall_lo"])],
                            [max(0, r["recall_hi"] - r["recall_unsafe"])]], fmt=marker, color=PAL[k], capsize=2,
                            label=ls if op == "FLAG_REJECT" else None)
        ax.axhline(0.9, color="grey", ls=":", lw=1)
        ax.set_title(subset, fontsize=10)
        ax.set_xlabel("flag rate (review burden)")
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.05)
        _style(ax)
    axes[0][0].set_ylabel("recall on human-UNSAFE")
    fig.suptitle("circle: flag REJECT only; square: flag REVIEW or REJECT; bars: 95% CI; dotted: 0.90 target", fontsize=8, y=1.0)
    axes[0][-1].legend(frameon=False, fontsize=8, loc="lower right")
    return _save(fig, path)


def fig_repair(rep: dict, path: Path) -> Path | None:
    if not rep or not rep.get("n_originals"):
        return None
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9, 3.8), gridspec_kw={"width_ratios": [2, 1]})
    rows = [{"generator": "all", **{k: rep[k] for k in rep if k.endswith(("before", "after"))}}] + rep.get("by_generator", [])
    labels = [r["generator"] for r in rows]
    x = np.arange(len(rows))
    for j, (col, color, name) in enumerate((("safe_useful_per100", PAL[1], "SAFE_AND_USEFUL"), ("safe_per100", PAL[0], "SAFE"))):
        for k, when in enumerate(("before", "after")):
            ax.bar(x + (j * 2 + k - 1.5) * 0.2, [r[f"{col}_{when}"] for r in rows], 0.2, color=color,
                   alpha=1.0 if when == "after" else 0.45, label=f"{name} {when}")
    ax.set_xticks(x, labels, fontsize=8)
    ax.set_ylabel("per 100 requests")
    ax.legend(frameon=False, fontsize=7)
    _style(ax)
    vals = [rep["unsafe_to_safe"], rep["safe_to_unsafe"], rep["unchanged"]]
    ax2.bar(["unsafe to safe", "safe to unsafe", "unchanged"], vals, color=[PAL[2], PAL[4], "#999999"])
    ax2.set_ylabel(f"repaired items (n={rep['n_repaired']})")
    ax2.tick_params(axis="x", labelrotation=20, labelsize=8)
    _style(ax2)
    return _save(fig, path)


def fig_cost(per: pd.DataFrame, path: Path) -> Path | None:
    p = per.dropna(subset=["usd_per_100"])
    if p.empty:
        return None
    t = p.pivot_table(index="condition", columns="stage", values="usd_per_100", aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(max(5, 0.9 * len(t) + 2), 4))
    bottom = np.zeros(len(t))
    for k, stage in enumerate(t.columns):
        ax.bar(range(len(t)), t[stage], bottom=bottom, color=PAL[k % len(PAL)], label=stage)
        bottom += t[stage].to_numpy()
    ax.set_xticks(range(len(t)), [c.replace("|", "\n") for c in t.index], fontsize=8)
    ax.set_ylabel("USD per 100 items")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    return _save(fig, path)


def fig_presentation(pres: pd.DataFrame, path: Path) -> Path | None:
    if pres.empty:
        return None
    p = pres.assign(label=pres["generator"] + " | " + pres["stratum_type"].replace("overall", "") + " " + pres["stratum"].replace("all", "overall"))
    gens = list(dict.fromkeys(p["generator"]))
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(p) + 1.5))
    y = np.arange(len(p))[::-1]
    colors = [PAL[gens.index(g) % len(PAL)] for g in p["generator"]]
    ax.errorbar(p["diff"], y, xerr=[(p["diff"] - p["ci_lo"]).clip(lower=0), (p["ci_hi"] - p["diff"]).clip(lower=0)],
                fmt="none", ecolor="#555555", capsize=2)
    ax.scatter(p["diff"], y, c=colors, zorder=3)
    ax.axvline(0, color="grey", lw=1)
    ax.set_yticks(y, p["label"], fontsize=8)
    ax.set_xlabel("presentation: LLM chunked minus deterministic chunked (paired, 95% CI)")
    ax.grid(axis="x", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, path)


def fig_flags(flags: pd.DataFrame, path: Path) -> Path | None:
    if flags.empty:
        return None
    f = flags.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 0.3 * len(f) + 1.5))
    ax.barh(f["code"], f["n_items"], color=[DECISION_COLORS.get(s, "#999999") for s in f["severity"]])
    ax.set_xlabel("items carrying the flag (deterministic layer; red: REJECT, orange: REVIEW)")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="x", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, path)


def fig_decisions(dec: pd.DataFrame, title: str, path: Path) -> Path | None:
    if dec.empty:
        return None
    labels = (dec["generator"] + "\n" + dec["transformation"]).tolist()
    fig, ax = plt.subplots(figsize=(max(5, 0.9 * len(dec) + 2), 4))
    bottom = np.zeros(len(dec))
    for d in ("PASS", "REVIEW", "REJECT"):
        ax.bar(range(len(dec)), dec[f"{d}_share"], bottom=bottom, color=DECISION_COLORS[d], label=d)
        bottom += dec[f"{d}_share"].to_numpy()
    ax.set_xticks(range(len(dec)), labels, fontsize=8)
    ax.set_ylabel("share of items")
    ax.set_title(f"Verifier decisions ({title})", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    return _save(fig, path)


# ------------------------------------------------------------------ markdown assembly

class Doc:
    """Tiny Markdown builder; image links are relative to the report file."""

    def __init__(self, out_md: Path):
        self.out_md, self.parts = out_md, []

    def h(self, title: str, level: int = 2) -> None:
        self.parts.append(f"{'#' * level} {title}\n")

    def p(self, text: str) -> None:
        self.parts.append(text + "\n")

    def table(self, df: pd.DataFrame, empty: str = "_No data._") -> None:
        self.parts.append((ev.md(df) if len(df) else empty) + "\n")

    def image(self, path: Path | None, caption: str) -> None:
        if path is not None:
            self.parts.append(f"![{caption}]({os.path.relpath(path, self.out_md.parent)})\n")

    def write(self) -> None:
        self.out_md.parent.mkdir(parents=True, exist_ok=True)
        self.out_md.write_text("\n".join(self.parts), encoding="utf-8")


def pipeline_sections(doc: Doc, run_dir: Path, fig_dir: Path) -> pd.DataFrame:
    gens = load_generations(run_dir)
    verify = load_verify(run_dir)
    ledger = load_ledger(run_dir)

    doc.h("Outputs per condition")
    doc.p("Rows by source file (`main`, `ablation`, `pilot`, `repair`, `baseline`). `rewritten` and `no_rewrite` come from the "
          "model's own status field; `parse_error` means the reply was not valid JSON; `api_error` means the call failed.")
    doc.table(counts_table(gens), "_No generation files found in the run folder._")

    if verify:
        best_label, best_rows = next(iter(verify.items()))
        doc.h("Verifier decisions")
        for label, rows in verify.items():
            doc.h(f"Layers: {label}", 3)
            dec = decision_table(rows, gens)
            doc.table(dec.drop(columns=[c for c in dec if c.endswith("_share")]))
            if label == best_label:
                doc.image(fig_decisions(dec, label, fig_dir / "fig_decisions.png"), f"Verifier decisions, {label}")
        flags = flag_table(best_rows)
        doc.h("Deterministic flag codes")
        doc.p(f"From the `{best_label}` verification ({len(best_rows)} items); an item counts once per code.")
        doc.table(flags, "_No deterministic flags raised._")
        doc.image(fig_flags(flags, fig_dir / "fig_flags.png"), "Deterministic flag frequencies")
        doc.h("Readability (diagnostic only)")
        doc.p("Flesch-Kincaid grade of the adaptation minus that of the source. These numbers are never part of the safety decision.")
        doc.table(readability_table(best_rows, gens), "_No readability fields in the verification files._")
    else:
        doc.h("Verifier decisions")
        doc.p("_No `*.verify-*.jsonl` files in the run folder yet._")

    doc.h("Cost and latency")
    if ledger is not None:
        summary, per = ledger_tables(ledger, gens)
        doc.table(summary)
        doc.image(fig_cost(per, fig_dir / "fig_cost.png"), "USD per 100 items by condition and stage")
    else:
        doc.p("_No `ledger.csv` in the run folder._")
    return gens


def labelled_sections(doc: Doc, run_dir: Path, labels: Path, key: Path | None, fig_dir: Path, sources: dict, b: int) -> None:
    df = ev.prepare(labels, key)
    first = ev._primary(df)
    rates = ev.all_rates(first, b)

    doc.h("Outcome rates")
    doc.p("Human (adjudicated) labels, first-pass outputs only. 95% percentile CIs from a source-clustered bootstrap "
          f"({b} replicates): all adaptations of one source are resampled together.")
    for outcome, g in rates.groupby("outcome", sort=False):
        doc.h(outcome, 3)
        doc.table(g.drop(columns="outcome"))
    doc.image(fig_rates(rates, fig_dir / "fig_rates.png"), "SAFE and SAFE_AND_USEFUL per condition")

    doc.h("Prespecified paired comparisons on SAFE")
    doc.p("Three families (diff = A minus B): realistic vs constrained-chunked per generator, generator A vs B per "
          "transformation, plain vs chunked per generator. Exact McNemar on discordant pairs; Holm adjustment within each "
          "family only. Everything else is exploratory.")
    doc.table(ev.prespecified_families(first, "SAFE", b))

    doc.h("Presentation versus the deterministic chunking baseline")
    pres = ev.presentation_vs_baseline(first, b, sources)
    doc.p("Paired by source; abstentions (null presentation) are ignored. Wilcoxon signed-rank is a sensitivity check. "
          "Strata are exploratory.")
    doc.table(pres, "_No deterministic baseline rows among the labels._")
    doc.image(fig_presentation(pres, fig_dir / "fig_presentation.png"), "Paired presentation differences versus baseline")

    verify = load_verify(run_dir)
    verify_rows = [r for rows in verify.values() for r in rows] if verify else []
    if verify_rows and "output_id" in first:
        abl = ev.layer_ablations(verify_rows, first, b)
        doc.h("Verifier layer ablations")
        doc.p("Positive class = human UNSAFE. `FLAG_REJECT` flags only REJECT decisions; `FLAG_ANY` flags REVIEW or REJECT "
              "(its flag rate is the human-review burden). Layer sets are recomputed from the stored layer outputs.")
        doc.table(abl)
        doc.image(fig_verifier(abl, fig_dir / "fig_verifier.png"), "Recall versus flag rate per layer set")

    if key is not None:
        rep = ev.repair_outcomes(df, pd.read_csv(key))
        doc.h("Constrained repair")
        if rep["n_repaired"]:
            doc.table(pd.DataFrame([{k: v for k, v in rep.items() if k != "by_generator"}]).T.reset_index()
                      .rename(columns={"index": "metric", 0: "value"}))
            doc.table(pd.DataFrame(rep["by_generator"]))
            doc.image(fig_repair(rep, fig_dir / "fig_repair.png"), "Before and after repair")
        else:
            doc.p("_No labelled repairs._")

    lg = ev.logit_unsafe(first, sources)
    doc.h("Exploratory logistic regression of UNSAFE")
    doc.p(f"n = {lg['n']}; standard errors clustered by source; penalized fallback used: {lg['penalized']}; unpenalized fit "
          f"converged: {lg['converged']}. Exploratory only.")
    doc.table(lg["table"], "_Model not estimable (too few rows or only one outcome class)._")

    sheet_a, sheet_b = labels.parent / "sheet_A.csv", labels.parent / "sheet_B.csv"
    if sheet_a.exists() and sheet_b.exists():
        agr = ev.agreement(ev.derive(pd.read_csv(sheet_a)), ev.derive(pd.read_csv(sheet_b)))
        agr = agr[agr["n"] > 0]
        doc.h("Inter-annotator agreement (before adjudication)")
        doc.table(agr, "_Double-annotated labels not filled in yet._")


def build(run_dir: Path, labels: Path | None, key: Path | None, out_md: Path, fig_dir: Path,
          sources: dict | None = None, b: int = ev.B) -> None:
    """Write the report for `run_dir` to `out_md` and figures to `fig_dir` (see module docstring)."""
    run_dir, out_md, fig_dir = Path(run_dir), Path(out_md), Path(fig_dir)
    with_labels = labels is not None and Path(labels).exists()
    doc = Doc(out_md)
    doc.h(f"Report: {run_dir.name}" + ("" if with_labels else " (pipeline report, no human labels)"), 1)
    if not with_labels:
        doc.p("No adjudicated labels were supplied, so this report covers pipeline outputs only. It makes no claim about "
              "safety rates; those need human labels.")
    pipeline_sections(doc, run_dir, fig_dir)
    if with_labels:
        labelled_sections(doc, run_dir, Path(labels), Path(key) if key else None, fig_dir,
                          sources if sources is not None else ev.load_source_rows(), b)
    doc.write()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run folder, e.g. data/outputs/main-v1")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--out")
    ap.add_argument("--fig-dir")
    ap.add_argument("--boot", type=int, default=ev.B)
    args = ap.parse_args()
    run_dir = Path(args.run)
    run_id = run_dir.resolve().name
    ann = ROOT / "data" / "annotations" / run_id
    labels = Path(args.labels) if args.labels else (ann / "adjudicated.csv" if (ann / "adjudicated.csv").exists() else None)
    key = Path(args.key) if args.key else (ann / "KEY_DO_NOT_OPEN.csv" if (ann / "KEY_DO_NOT_OPEN.csv").exists() else None)
    out_md = Path(args.out) if args.out else ROOT / "docs" / "results" / f"{run_id}_report.md"
    fig_dir = Path(args.fig_dir) if args.fig_dir else ROOT / "docs" / "results" / "figures" / run_id
    build(run_dir, labels, key, out_md, fig_dir, b=args.boot)
    print(f"wrote {out_md} ({'with' if labels else 'without'} labels); figures in {fig_dir}")


if __name__ == "__main__":
    main()
