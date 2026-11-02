"""Prediction-powered inference (PPI): unbiased failure rates from a few human labels plus a cheap predictor.

  python src/ppi.py --run data/outputs/main-v1                       # labels from data/annotations/main-v1/
  python src/ppi.py --run data/outputs/main-v1 --predictor critic    # predictor = critic overall != SAFE
  python src/ppi.py --run ... --labels adjudicated.csv --key KEY_DO_NOT_OPEN.csv --verify a.jsonl b.jsonl
  python src/ppi.py --synthetic --out /tmp/ppi_synth.csv             # planted data, no run needed

The human label y (UNSAFE = 1 - SAFE from evaluate.derive) exists on a labelled subset; the predictor f
(verifier decision != PASS, or critic overall != SAFE) exists on every item. For a binary outcome:
  classical   mean(y_lab)                                            labelled subset only
  PPI         mean(f_all) + mean(y_lab - f_lab)                      Angelopoulos et al. (2023) Science 382:669
  PPI++       mean(y_lab) + lam * (mean(f_all) - mean(f_lab))        Angelopoulos, Duchi & Zrnic (2023) arXiv:2311.01453
The second term of PPI is the *rectifier*: the predictor's average error where it can be checked. PPI++
tunes lam in [0, 1] so a useless predictor falls back to the classical estimate.

Intervals are percentile bootstraps that resample source problems (clusters), the labelled set and the
full set independently, so the ~5 adaptations of one source are never treated as independent.
Writes <run>/analysis/ppi.csv (per-condition rates, three estimators) and ppi_budget.csv (CI width and
coverage against the labelled fraction).
"""
from __future__ import annotations

import argparse
import itertools
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from common import ROOT, read_jsonl
from evaluate import derive, load_labels, md, write_analysis

B = 2000
SEED = 0
FULL = "verify-critic-det-program"          # suffix of a full-layer verify file (see run_phase1.FULL)
DEFAULT_VERIFY = (f"generations.{FULL}.jsonl", f"ablation_generations.{FULL}.jsonl", "baseline.verify-det.jsonl")
FRACS = (0.2, 0.3, 0.5, 0.75, 1.0)
SYN_TRANSFORMATIONS = ("plain", "chunked", "naive")      # synthetic data only
SYN_GENERATORS = ("gen_a", "gen_b")
SYN_RATES = (0.15, 0.2, 0.25, 0.3, 0.35, 0.4)            # per-condition UNSAFE rates, cycled over conditions


# ------------------------------------------------------------------ cluster bootstrap

def _codes(cluster, n: int) -> np.ndarray:
    """Cluster codes 0..k-1; without clusters every item is its own cluster (plain i.i.d. bootstrap)."""
    if cluster is None:
        return np.arange(n)
    cluster = np.asarray(cluster)
    if len(cluster) != n:
        raise ValueError(f"cluster has {len(cluster)} entries for {n} items")
    return pd.factorize(cluster)[0]


def boot_means(rng: np.random.Generator, cols, cluster=None, n_boot: int = B) -> np.ndarray:
    """(n_boot, len(cols)) bootstrap means of the columns, resampling clusters with replacement, all columns together.

    Vectorised: per-cluster sums plus multinomial cluster weights, so each draw is one matrix product.
    """
    cols = [np.asarray(c, dtype=float) for c in cols]
    codes = _codes(cluster, len(cols[0]))
    k = int(codes.max()) + 1
    counts = np.bincount(codes, minlength=k).astype(float)
    sums = np.stack([np.bincount(codes, weights=c, minlength=k) for c in cols], axis=1)
    w = rng.multinomial(k, np.full(k, 1.0 / k), size=n_boot).astype(float)
    return (w @ sums) / (w @ counts)[:, None]


def _ci(vals: np.ndarray, alpha: float) -> tuple[float, float]:
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def _arr(*xs) -> list[np.ndarray]:
    return [np.asarray(x, dtype=float).ravel() for x in xs]


# ------------------------------------------------------------------ estimators

def classical_mean(y: np.ndarray, cluster: np.ndarray | None = None, alpha: float = 0.05, n_boot: int = B,
                   seed: int = SEED) -> tuple[float, float, float]:
    """Labelled-only mean; CI by cluster bootstrap when `cluster` is given, else normal approximation."""
    (y,) = _arr(y)
    est = float(y.mean()) if len(y) else np.nan
    if len(y) < 2:
        return est, np.nan, np.nan
    if cluster is None:
        se = y.std(ddof=1) / np.sqrt(len(y))
        z = norm.ppf(1 - alpha / 2)
        return est, est - z * se, est + z * se
    rng = np.random.default_rng(seed)
    lo, hi = _ci(boot_means(rng, [y], cluster, n_boot)[:, 0], alpha)
    return est, lo, hi


def ppi_mean(y_lab, f_lab, f_all, alpha: float = 0.05, cluster_lab=None, cluster_all=None, n_boot: int = B,
             seed: int = SEED) -> tuple[float, float, float]:
    """PPI mean: mean(f_all) + rectifier, rectifier = mean(y_lab - f_lab). Unbiased for any predictor.

    CI: bootstrap the labelled set (rectifier) and the full set (mean of f) independently, at cluster level
    when clusters are given, and take percentiles of their sum.
    """
    y_lab, f_lab, f_all = _arr(y_lab, f_lab, f_all)
    rect = y_lab - f_lab
    if len(y_lab) < 2 or len(f_all) < 2:
        return (float(f_all.mean() + rect.mean()) if len(y_lab) and len(f_all) else np.nan), np.nan, np.nan
    est = float(f_all.mean() + rect.mean())
    rng = np.random.default_rng(seed)
    draws = boot_means(rng, [f_all], cluster_all, n_boot)[:, 0] + boot_means(rng, [rect], cluster_lab, n_boot)[:, 0]
    lo, hi = _ci(draws, alpha)
    return est, lo, hi


def ppi_lambda(y_lab, f_lab, n_all: int) -> float:
    """Variance-minimising PPI++ weight cov(y, f) / (var(f) (1 + n_lab / n_all)), clipped to [0, 1]."""
    y_lab, f_lab = _arr(y_lab, f_lab)
    n = len(y_lab)
    if n < 2 or f_lab.var(ddof=1) == 0:
        return 0.0
    cov = np.cov(y_lab, f_lab, ddof=1)[0, 1]
    return float(np.clip(cov / (f_lab.var(ddof=1) * (1 + n / n_all)), 0.0, 1.0))


def ppi_pp_mean(y_lab, f_lab, f_all, alpha: float = 0.05, lam: float | None = None, cluster_lab=None,
                cluster_all=None, n_boot: int = B, seed: int = SEED) -> tuple[float, float, float, float]:
    """PPI++ mean: mean(y_lab) + lam * (mean(f_all) - mean(f_lab)); lam tuned unless given. Returns (est, lo, hi, lam).

    lam = 0 is the classical estimate, lam = 1 is PPI; lam is fixed at its point value inside the bootstrap.
    """
    y_lab, f_lab, f_all = _arr(y_lab, f_lab, f_all)
    lam = ppi_lambda(y_lab, f_lab, len(f_all)) if lam is None else float(lam)
    if len(y_lab) < 2 or len(f_all) < 2:
        est = float(y_lab.mean() + lam * (f_all.mean() - f_lab.mean())) if len(y_lab) and len(f_all) else np.nan
        return est, np.nan, np.nan, lam
    est = float(y_lab.mean() + lam * (f_all.mean() - f_lab.mean()))
    rng = np.random.default_rng(seed)
    lab = boot_means(rng, [y_lab, f_lab], cluster_lab, n_boot)
    whole = boot_means(rng, [f_all], cluster_all, n_boot)[:, 0]
    lo, hi = _ci(lab[:, 0] + lam * (whole - lab[:, 1]), alpha)
    return est, lo, hi, lam


# ------------------------------------------------------------------ tables

def _groups(df: pd.DataFrame, group_cols: list[str]) -> list[tuple[dict, np.ndarray]]:
    """[(group labels, row positions)]: an 'all' row first, then one per group."""
    out = [({c: "all" for c in group_cols}, np.arange(len(df)))]
    if group_cols:
        for key, idx in df.groupby(group_cols, sort=True).indices.items():
            key = key if isinstance(key, tuple) else (key,)
            out.append((dict(zip(group_cols, key)), np.asarray(idx)))
    return out


def _three(y, f_lab, f_all, cl, ca, alpha, n_boot, seed) -> dict:
    """Classical, PPI and PPI++ estimates with CI and width for one group."""
    nan3 = (np.nan, np.nan, np.nan)
    c = classical_mean(y, cl, alpha, n_boot, seed) if len(y) else nan3
    p = ppi_mean(y, f_lab, f_all, alpha, cl, ca, n_boot, seed) if len(y) else nan3
    q = ppi_pp_mean(y, f_lab, f_all, alpha, None, cl, ca, n_boot, seed) if len(y) else (*nan3, np.nan)
    row = {}
    for name, (est, lo, hi) in (("classical", c), ("ppi", p), ("ppipp", q[:3])):
        row.update({name: est, f"{name}_lo": lo, f"{name}_hi": hi, f"{name}_width": hi - lo})
    row["lam"] = q[3]
    return row


def estimate_rates(df_all: pd.DataFrame, labeled_mask: np.ndarray, y_col: str = "UNSAFE", f_col: str = "f",
                   group_cols=("transformation", "generator"), cluster_col: str = "source_id", alpha: float = 0.05,
                   n_boot: int = B, seed: int = SEED) -> pd.DataFrame:
    """Per group (and overall): classical (labelled only), PPI and PPI++ rates with CIs, widths, n_lab, n_all."""
    df = df_all.reset_index(drop=True)
    lab = np.asarray(labeled_mask, dtype=bool)
    if len(lab) != len(df):
        raise ValueError("labeled_mask must have one entry per row of df_all")
    rows = []
    for key, idx in _groups(df, list(group_cols)):
        d, m = df.iloc[idx], lab[idx]
        y, fl, fa = d.loc[m, y_col].to_numpy(float), d.loc[m, f_col].to_numpy(float), d[f_col].to_numpy(float)
        cl = d.loc[m, cluster_col].to_numpy() if cluster_col and cluster_col in d else None
        ca = d[cluster_col].to_numpy() if cluster_col and cluster_col in d else None
        rows.append({**key, "n_lab": int(m.sum()), "n_all": len(d), "f_rate_all": float(fa.mean()),
                     **_three(y, fl, fa, cl, ca, alpha, n_boot, seed)})
    return pd.DataFrame(rows)


def label_budget_curve(df_all: pd.DataFrame, y_col: str = "UNSAFE", f_col: str = "f", fracs=FRACS, n_rep: int = 200,
                       seed: int = SEED, cluster_col: str = "source_id", alpha: float = 0.05, n_boot: int = 1000,
                       group_cols=()) -> pd.DataFrame:
    """Mean CI width and coverage of the full-data mean(y) when only a fraction of sources is labelled.

    Every row of df_all needs y (it is the population whose mean the intervals must cover). For each fraction
    and repetition a random subset of sources is 'labelled'; f is used on all rows. With `group_cols` the
    curve is also computed within each group.
    """
    df = df_all.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    rows = []
    for key, idx in _groups(df, list(group_cols)):
        d = df.iloc[idx].reset_index(drop=True)
        y, f, cl = d[y_col].to_numpy(float), d[f_col].to_numpy(float), d[cluster_col].to_numpy()
        target = float(y.mean())
        units, by = np.unique(cl), d.groupby(cluster_col).indices
        for frac in fracs:
            k = min(len(units), max(2, int(round(frac * len(units)))))
            stats = {name: [] for name in ("classical", "ppi", "ppipp")}
            lams, n_labs = [], []
            for _ in range(n_rep):
                take = np.concatenate([by[u] for u in rng.choice(units, k, replace=False)])
                yl, fl, cll = y[take], f[take], cl[take]
                s = int(rng.integers(2**31 - 1))
                ests = {"classical": classical_mean(yl, cll, alpha, n_boot, s),
                        "ppi": ppi_mean(yl, fl, f, alpha, cll, cl, n_boot, s)}
                q = ppi_pp_mean(yl, fl, f, alpha, None, cll, cl, n_boot, s)
                ests["ppipp"], lams = q[:3], lams + [q[3]]
                n_labs.append(len(take))
                for name, (est, lo, hi) in ests.items():
                    stats[name].append((hi - lo, lo <= target <= hi, (est - target) ** 2))
            row = {**key, "frac": frac, "n_sources_lab": k, "n_lab": float(np.mean(n_labs)), "n_all": len(d),
                   "n_rep": n_rep, "target": target}
            for name, vals in stats.items():
                a = np.asarray(vals, dtype=float)
                row[f"width_{name}"], row[f"cov_{name}"], row[f"rmse_{name}"] = a[:, 0].mean(), a[:, 1].mean(), np.sqrt(a[:, 2].mean())
            row["lam_mean"] = float(np.mean(lams))
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ predictors and data

def predictor_from_verify(verify_rows: list[dict], kind: str = "decision") -> dict[str, int]:
    """output_id -> 1 if the verifier predicts UNSAFE: decision != PASS, or critic overall != SAFE (missing/_error -> 1)."""
    if kind == "decision":
        return {r["output_id"]: int(r.get("decision") != "PASS") for r in verify_rows}
    if kind == "critic":
        out = {}
        for r in verify_rows:
            c = r.get("critic")
            out[r["output_id"]] = int(not isinstance(c, dict) or bool(c.get("_error")) or c.get("overall") != "SAFE")
        return out
    raise ValueError(f"unknown predictor kind {kind!r} (decision|critic)")


def synthetic(n_sources: int = 150, per_source: int = 5, predictor_acc: float = 0.85, predictor_bias: float = 0.1,
              seed: int = SEED) -> pd.DataFrame:
    """Planted data: UNSAFE with a source random effect; f = UNSAFE flipped with asymmetric error rates.

    predictor_acc = P(f == y); predictor_bias = E[f] - E[y] (positive: the predictor over-flags), achieved by
    false-positive rate fp = (e + bias) / (2 (1 - p)) and miss rate fn = (e - bias) / (2 p), e = 1 - acc,
    each clipped to [0, 1] (so |bias| <= 1 - acc is exact). Columns: output_id, source_id, transformation,
    generator, UNSAFE, f. df.attrs records the realised fp, fn, accuracy and bias.
    """
    rng = np.random.default_rng(seed)
    conds = list(itertools.product(SYN_TRANSFORMATIONS, SYN_GENERATORS))
    logit = {c: np.log(r / (1 - r)) for c, r in zip(conds, itertools.cycle(SYN_RATES))}
    u = rng.normal(0.0, 0.9, n_sources)         # some problems are hard for every condition
    src = np.repeat(np.arange(n_sources), per_source)
    j = np.tile(np.arange(per_source), n_sources)
    cond = [conds[i % len(conds)] for i in j]
    p = 1 / (1 + np.exp(-(np.array([logit[c] for c in cond]) + u[src])))
    y = (rng.random(len(p)) < p).astype(int)
    pbar, e = y.mean(), 1 - predictor_acc
    fp = float(np.clip((e + predictor_bias) / (2 * (1 - pbar)), 0, 1))
    fn = float(np.clip((e - predictor_bias) / (2 * pbar), 0, 1))
    flip = np.where(y == 1, rng.random(len(y)) < fn, rng.random(len(y)) < fp)
    f = (y ^ flip.astype(int)).astype(int)
    df = pd.DataFrame({"output_id": [f"syn|{c[1]}|{c[0]}|s{s:04d}" for c, s in zip(cond, src)],
                       "source_id": [f"s{s:04d}" for s in src], "transformation": [c[0] for c in cond],
                       "generator": [c[1] for c in cond], "UNSAFE": y, "f": f})
    df.attrs.update({"fp": fp, "fn": fn, "accuracy": float((f == y).mean()), "bias": float(f.mean() - y.mean())})
    return df


def load_run(run: str | Path, labels: str | Path | None = None, key: str | Path | None = None,
             verify: list[str | Path] | None = None, predictor: str = "decision") -> tuple[pd.DataFrame, np.ndarray]:
    """All first-pass verify rows of a run with f, source_id/transformation/generator (from the generations file)
    and UNSAFE where adjudicated labels exist. Returns (df_all, labeled_mask)."""
    run = Path(run)
    ann = ROOT / "data" / "annotations" / run.name
    labels = Path(labels) if labels else ann / "adjudicated.csv"
    key = Path(key) if key else ann / "KEY_DO_NOT_OPEN.csv"
    paths = [Path(p) for p in verify] if verify else [run / n for n in DEFAULT_VERIFY if (run / n).exists()]
    if not paths:
        raise FileNotFoundError(f"no verify files under {run} (expected one of {DEFAULT_VERIFY})")
    frames = []
    for vp in paths:
        gens = vp.with_name(vp.name.split(".verify-")[0] + ".jsonl")
        meta = {g["output_id"]: g for g in read_jsonl(gens)} if gens.exists() else {}
        rows = read_jsonl(vp)
        f = predictor_from_verify(rows, predictor)
        frames.append(pd.DataFrame([{"output_id": r["output_id"], "verify_file": vp.name,
                                     **{k: meta.get(r["output_id"], {}).get(k) for k in ("source_id", "transformation", "generator")},
                                     "f": f[r["output_id"]]} for r in rows]))
    df = pd.concat(frames, ignore_index=True).drop_duplicates("output_id").reset_index(drop=True)
    if df["source_id"].isna().any():
        warnings.warn(f"{int(df['source_id'].isna().sum())} verify rows have no generations row; dropped")
        df = df.dropna(subset=["source_id"]).reset_index(drop=True)
    lab = load_labels(labels).merge(pd.read_csv(key), on="annotation_id")
    lab = derive(lab)
    unsafe = dict(zip(lab["output_id"], 1 - lab["SAFE"].astype(int)))
    missing = set(unsafe) - set(df["output_id"])
    if missing:
        warnings.warn(f"{len(missing)} labelled output_ids are not in the verify rows (repairs?) and are ignored")
    df["UNSAFE"] = df["output_id"].map(unsafe)
    mask = df["UNSAFE"].notna().to_numpy()
    return df, mask


# ------------------------------------------------------------------ CLI

def report(df: pd.DataFrame, mask: np.ndarray, n_boot: int, n_rep: int, fracs, seed: int,
           group_cols=("transformation", "generator"), budget_df: pd.DataFrame | None = None
           ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rates table on (df, mask) and the budget curve on `budget_df` (default: the labelled rows, which have y)."""
    rates = estimate_rates(df, mask, group_cols=group_cols, n_boot=n_boot, seed=seed)
    pop = df[mask] if budget_df is None else budget_df
    budget = label_budget_curve(pop.reset_index(drop=True), fracs=fracs, n_rep=n_rep, seed=seed,
                                n_boot=min(n_boot, 1000))
    return rates, budget


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", help="data/outputs/<run_id>; labels default to data/annotations/<run_id>/")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--verify", nargs="*", help=f"verify jsonl files (default: {', '.join(DEFAULT_VERIFY)})")
    ap.add_argument("--predictor", choices=("decision", "critic"), default="decision")
    ap.add_argument("--synthetic", action="store_true", help="planted data instead of a run")
    ap.add_argument("--frac", type=float, default=0.3, help="labelled fraction of sources for --synthetic")
    ap.add_argument("--boot", type=int, default=B)
    ap.add_argument("--n-rep", type=int, default=200)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", help="write the rates CSV here (budget curve next to it as <stem>_budget.csv); "
                                  "default <run>/analysis/ppi.csv and ppi_budget.csv")
    args = ap.parse_args()
    if not args.synthetic and not args.run:
        ap.error("--run or --synthetic is required")

    if args.synthetic:
        df = synthetic(seed=args.seed)
        rng = np.random.default_rng(args.seed)
        units = df["source_id"].unique()
        take = set(rng.choice(units, max(2, int(round(args.frac * len(units)))), replace=False))
        mask = df["source_id"].isin(take).to_numpy()
        print(f"synthetic: n={len(df)}, labelled {int(mask.sum())} ({args.frac:.0%} of sources); "
              f"predictor accuracy {df.attrs['accuracy']:.3f}, bias {df.attrs['bias']:+.3f}\n")
    else:
        df, mask = load_run(args.run, args.labels, args.key, args.verify, args.predictor)
        print(f"run {args.run}: n={len(df)} verify rows, labelled {int(mask.sum())}; predictor = {args.predictor}\n")
    if mask.sum() < 2:
        raise SystemExit("fewer than 2 labelled items; nothing to estimate")

    rates, budget = report(df, mask, args.boot, args.n_rep, FRACS, args.seed,
                           budget_df=df if args.synthetic else None)   # synthetic: y is known on every row
    print("## Rates: classical (labelled only) vs PPI vs PPI++ (95% CI, source-clustered bootstrap)\n")
    print(md(rates), "\n")
    print("## Label budget: mean CI width and coverage of the full-data mean vs labelled fraction of sources\n")
    print(md(budget), "\n")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        rates.to_csv(out, index=False)
        budget.to_csv(out.with_name(out.stem + "_budget.csv"), index=False)
        print(f"wrote {out} and {out.with_name(out.stem + '_budget.csv')}")
    elif args.run:
        p1 = write_analysis(Path(args.run) / "analysis", "ppi", rates)
        p2 = write_analysis(Path(args.run) / "analysis", "ppi_budget", budget)
        print(f"wrote {p1} and {p2}")


if __name__ == "__main__":
    main()
