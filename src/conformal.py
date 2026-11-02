"""Risk-controlled PASS: choose the verifier's PASS threshold with a finite-sample guarantee (Phase 2A).

  python src/conformal.py --run data/outputs/main-v1 [--labels ADJ.csv --key KEY.csv] [--alphas 0.02 0.05 0.1]
  python src/conformal.py --run data/outputs/main-v1 --method ltt --by transformation
  python src/conformal.py --synthetic [--out scratch/conformal_synth.csv]
Reads the full verify files (*.verify-critic-det-program.jsonl) in the run dir, joins the human labels
(default data/annotations/<run_id>/adjudicated.csv + KEY_DO_NOT_OPEN.csv), and writes <run>/analysis/conformal.csv.

Every verify row gets an ordinal risk score (more evidence of harm -> higher). The rule is PASS iff score <= lambda.
  crc  Conformal Risk Control: largest lambda with E[unsafe and passed] <= alpha (marginal, per item).
  ltt  Learn-then-Test fixed-sequence test: largest lambda with P(unsafe | passed) <= alpha, w.p. >= 1 - delta.
Calibration and test halves are split by source_id (the exchangeable unit). See docs/methods/conformal.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom

SEED = 2880
NEG_INF = float("-inf")  # sentinel: no threshold is certified, PASS nothing
ALPHAS = (0.02, 0.05, 0.10, 0.20)
SEV_REJECT = "REJECT"


# ------------------------------------------------------------------ risk score

def risk_score(row: dict) -> float:
    """Ordinal evidence-of-harm score from a verify row; higher = more evidence, never lower when evidence is added.

    base: 5 det REJECT flag > 4 critic UNSAFE > 3 program MISMATCH > 2 critic missing/error/UNSURE or program
    UNCHECKABLE > 1 any det flag > 0 clean; plus 0.1 per det flag (capped at 9, so the bonus stays below 1).
    """
    flags = (row.get("deterministic") or {}).get("flags") or []
    critic, prog = row.get("critic"), row.get("program")
    overall = None if (critic is None or "_error" in critic) else critic.get("overall")
    prog_status = (prog or {}).get("status")
    if any(f.get("severity") == SEV_REJECT for f in flags):
        base = 5
    elif overall == "UNSAFE":
        base = 4
    elif prog_status == "MISMATCH":
        base = 3
    elif overall not in ("SAFE", "UNSAFE") or prog_status == "UNCHECKABLE":
        base = 2  # critic None / _error / UNSURE (or an unrecognised verdict, treated conservatively)
    elif flags:
        base = 1
    else:
        base = 0
    return base + 0.1 * min(len(flags), 9)


# ------------------------------------------------------------------ splitting

def split_by_source(df: pd.DataFrame, frac: float = 0.5, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calibration/test split over unique source_id (a source's items never straddle the split)."""
    ids = np.array(sorted(df["source_id"].unique()))
    perm = np.random.default_rng(seed).permutation(len(ids))
    k = min(max(int(round(frac * len(ids))), 1), max(len(ids) - 1, 1))
    cal_ids = set(ids[perm[:k]])
    mask = df["source_id"].isin(cal_ids)
    return df[mask], df[~mask]


# ------------------------------------------------------------------ calibration

def _grid(scores: np.ndarray) -> np.ndarray:
    return np.unique(np.asarray(scores, dtype=float))


def _unit_losses(scores: np.ndarray, losses: np.ndarray, grid: np.ndarray, groups) -> np.ndarray:
    """Matrix (units x grid): loss of each exchangeable unit (item, or mean over a group's items) at each lambda."""
    li = np.asarray(losses, dtype=float)[:, None] * (np.asarray(scores, dtype=float)[:, None] <= grid[None, :])
    if groups is None:
        return li
    _, codes = np.unique(np.asarray(groups), return_inverse=True)
    sums = np.zeros((codes.max() + 1, len(grid)))
    np.add.at(sums, codes, li)
    return sums / np.bincount(codes)[:, None]


def crc_threshold(scores: np.ndarray, losses: np.ndarray, alpha: float, B: float = 1.0, groups=None) -> float:
    """Conformal Risk Control (Angelopoulos, Bates, Fisch, Lei, Schuster, ICLR 2024).

    Rule: PASS iff score <= lambda. Loss of item i is L_i(lambda) = unsafe_i * 1[score_i <= lambda]: an unsafe item
    that is passed. It is non-decreasing in lambda and bounded by B. Returns the largest lambda on the grid of
    observed scores with  n/(n+1) * mean_i L_i(lambda) + B/(n+1) <= alpha,  which gives E[L_{n+1}(lambda_hat)] <= alpha
    for a new exchangeable unit. With `groups` (source ids) the unit is the group: its loss is the mean over its
    items and n is the number of groups. Returns -inf if no lambda qualifies (pass nothing).
    """
    scores = np.asarray(scores, dtype=float)
    if len(scores) == 0:
        return NEG_INF
    grid = _grid(scores)
    units = _unit_losses(scores, losses, grid, groups)
    n = units.shape[0]
    adj = n / (n + 1) * units.mean(axis=0) + B / (n + 1)
    ok = np.flatnonzero(adj <= alpha)
    return float(grid[ok[-1]]) if len(ok) else NEG_INF


def ltt_threshold(scores: np.ndarray, unsafe: np.ndarray, alpha: float, delta: float = 0.1, groups=None) -> float:
    """Learn-then-Test (Angelopoulos, Bates, Candes, Jordan, Lei 2021), fixed-sequence testing.

    Target: P(unsafe | PASS at lambda) <= alpha. Candidates are the sorted unique scores, strictest first. For each,
    test H_lambda: risk(lambda) > alpha with the exact binomial p-value P(Binom(m, alpha) <= k), where m items have
    score <= lambda and k of them are unsafe. Walk up the sequence while p <= delta; stop at the first lambda with
    p > delta and return the previous lambda (-inf if the first fails). Testing in a fixed order and stopping at the
    first non-rejection controls the family-wise error rate at delta without any multiplicity correction, so with
    probability >= 1 - delta every returned lambda truly has risk <= alpha. (The risk is monotone in lambda, which is
    why the strict-to-lenient order is the natural one; the grid depends on scores only, not on labels.)

    With `groups`, a conservative cluster version: each group's pass-set is one Bernoulli trial of "contains an unsafe
    item" (groups with an empty pass-set are not trials). This controls P(a passed group contains an unsafe item),
    which dominates the within-group unsafe fraction, so it is conservative for the item-level rate unless pass-set
    sizes correlate with unsafe fractions.
    """
    scores = np.asarray(scores, dtype=float)
    unsafe = np.asarray(unsafe, dtype=int)
    if groups is not None:
        codes = np.unique(np.asarray(groups), return_inverse=True)[1]
    best = NEG_INF
    for lam in _grid(scores):
        sel = scores <= lam
        if groups is None:
            m, k = int(sel.sum()), int(unsafe[sel].sum())
        else:
            m = len(np.unique(codes[sel]))
            k = len(np.unique(codes[sel & (unsafe == 1)]))
        if m == 0 or binom.cdf(k, m, alpha) > delta:
            break
        best = float(lam)
    return best


# ------------------------------------------------------------------ guarantee curve

def attach_scores(df: pd.DataFrame, verify_rows: list[dict]) -> pd.DataFrame:
    """Inner-join labels with verify rows on output_id; adds `score` and `unsafe` (= 1 - SAFE)."""
    sc = pd.DataFrame({"output_id": [r["output_id"] for r in verify_rows],
                       "score": [risk_score(r) for r in verify_rows]}).drop_duplicates("output_id")
    out = df.drop_duplicates("output_id").merge(sc, on="output_id")
    out["unsafe"] = 1 - out["SAFE"].astype(int)
    return out.reset_index(drop=True)


def _calibrate(cal: pd.DataFrame, alpha: float, method: str, delta: float, B: float, cluster: bool) -> float:
    groups = cal["source_id"].to_numpy() if cluster else None
    if method == "crc":
        return crc_threshold(cal["score"].to_numpy(), cal["unsafe"].to_numpy(), alpha, B, groups)
    if method == "ltt":
        return ltt_threshold(cal["score"].to_numpy(), cal["unsafe"].to_numpy(), alpha, delta, groups)
    raise ValueError(f"unknown method {method!r}")


def _test_metrics(test: pd.DataFrame, lam: float) -> dict:
    passed = test["score"].to_numpy() <= lam
    unsafe = test["unsafe"].to_numpy().astype(bool)
    n = max(len(test), 1)
    return {"n_test": len(test), "pass_rate": passed.sum() / n, "review_rate": 1 - passed.sum() / n,
            "cond_risk": float((unsafe & passed).sum() / passed.sum()) if passed.any() else 0.0,  # vacuous 0 if no PASS
            "unsafe_pass": float((unsafe & passed).sum() / n)}


def guarantee_curve(df: pd.DataFrame, verify_rows: list[dict], alphas=ALPHAS, n_splits: int = 200,
                    method: str = "crc", seed: int = SEED, by: list[str] | None = None, delta: float = 0.1,
                    B: float = 1.0, cluster: bool = True) -> pd.DataFrame:
    """Repeated source-level splits: calibrate lambda on one half, measure realized risk on the other.

    Per alpha: mean lambda (finite splits only), review rate (score > lambda) with 2.5/97.5 percentiles over splits,
    realized_risk_* = mean(unsafe among PASSed) on test (0 if nothing passed), realized_unsafe_pass_* = share of ALL
    test items that are unsafe and passed (the quantity CRC controls), and the fraction of splits at or below alpha
    for each. `by` adds a per-condition breakdown (thresholds are still calibrated on the pooled half).
    """
    data = attach_scores(df, verify_rows)
    by = list(by or [])
    recs = []
    for s in range(n_splits):
        cal, test = split_by_source(data, 0.5, seed + s)
        for alpha in alphas:
            lam = _calibrate(cal, alpha, method, delta, B, cluster)
            base = {"method": method, "alpha": alpha, "split": s, "lam": lam}
            recs.append({**base, **{c: "ALL" for c in by}, **_test_metrics(test, lam)})
            if by:
                for key, g in test.groupby(by, observed=True):
                    key = key if isinstance(key, tuple) else (key,)
                    recs.append({**base, **dict(zip(by, key)), **_test_metrics(g, lam)})
    r = pd.DataFrame(recs)
    r["finite"] = np.isfinite(r["lam"])
    rows = []
    for keys, g in r.groupby(["method", *by, "alpha"], sort=False):
        a = g["alpha"].iloc[0]
        fin = g.loc[g["finite"], "lam"]
        rows.append({
            **dict(zip(["method", *by, "alpha"], keys)),
            "n_splits": len(g),
            "lambda_mean": float(fin.mean()) if len(fin) else NEG_INF,
            "frac_splits_pass_nothing": float(1 - g["finite"].mean()),
            "review_rate_mean": g["review_rate"].mean(),
            "review_rate_lo": np.percentile(g["review_rate"], 2.5), "review_rate_hi": np.percentile(g["review_rate"], 97.5),
            "pass_rate_mean": g["pass_rate"].mean(),
            "realized_risk_mean": g["cond_risk"].mean(),
            "realized_risk_lo": np.percentile(g["cond_risk"], 2.5), "realized_risk_hi": np.percentile(g["cond_risk"], 97.5),
            "realized_unsafe_pass_mean": g["unsafe_pass"].mean(),
            "realized_unsafe_pass_lo": np.percentile(g["unsafe_pass"], 2.5),
            "realized_unsafe_pass_hi": np.percentile(g["unsafe_pass"], 97.5),
            "frac_splits_risk_below_alpha": float((g["cond_risk"] <= a).mean()),
            "frac_splits_unsafe_pass_below_alpha": float((g["unsafe_pass"] <= a).mean()),
        })
    return pd.DataFrame(rows)  # groupby(sort=False): alphas keep the order given, `by` groups follow ALL


# ------------------------------------------------------------------ synthetic data

def synthetic(n_sources: int = 120, per_source: int = 6, seed: int = 0) -> tuple[pd.DataFrame, list[dict]]:
    """Planted structure: unsafe outputs carry more evidence (flags, critic, program) so risk rises with score.

    Transformation "naive" has a higher unsafe rate; each source also has a latent difficulty shared by its items.
    """
    from verify import decide
    rng = np.random.default_rng(seed)
    trans = ["naive", "chunked", "rename"]
    p_unsafe = {"naive": 0.45, "chunked": 0.18, "rename": 0.10}
    codes_rej, codes_rev = ["QTY_CHANGE", "TARGET_CHANGE", "LEAK_ANSWER"], ["NEW_NUMBER", "LENGTH_RATIO"]
    labels, rows = [], []
    for s in range(n_sources):
        sid = f"syn-{s:04d}"
        shift = rng.normal(0, 0.6)  # source difficulty on the logit scale
        for j in range(per_source):
            t = trans[j % len(trans)]
            p = 1 / (1 + np.exp(-(np.log(p_unsafe[t] / (1 - p_unsafe[t])) + shift)))
            bad = rng.random() < p
            oid = f"{sid}-{j}"
            flags = []
            if rng.random() < (0.35 if bad else 0.03):
                flags.append({"code": str(rng.choice(codes_rej)), "severity": "REJECT", "detail": "synthetic"})
            for _ in range(rng.poisson(0.6 if bad else 0.25)):
                flags.append({"code": str(rng.choice(codes_rev)), "severity": "REVIEW", "detail": "synthetic"})
            overall = rng.choice(["UNSAFE", "UNSURE", "SAFE"], p=[0.5, 0.2, 0.3] if bad else [0.04, 0.10, 0.86])
            critic = None if rng.random() < 0.03 else {"math_fidelity": "FAIL" if overall == "UNSAFE" else "PASS",
                                                      "target_preserved": "PASS", "instructional_leakage": "NONE",
                                                      "ambiguity_introduced": "NO", "failure_codes": [],
                                                      "evidence": [], "overall": str(overall)}
            status = rng.choice(["MISMATCH", "UNCHECKABLE", "MATCH"], p=[0.3, 0.2, 0.5] if bad else [0.03, 0.10, 0.87])
            prog = {"status": str(status)}
            det = {"decision": "REJECT" if any(f["severity"] == "REJECT" for f in flags) else
                   ("REVIEW" if flags else "PASS"), "flags": flags, "readability": {}}
            decision, reasons = decide(det, critic, prog)
            rows.append({"output_id": oid, "decision": decision, "reasons": reasons, "deterministic": det,
                         "critic": critic, "program": prog})
            labels.append({"output_id": oid, "source_id": sid, "generator": "synthetic", "transformation": t,
                           "partition": "main", "SAFE": int(not bad)})
    return pd.DataFrame(labels), rows


# ------------------------------------------------------------------ cli

def _md(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False, floatfmt=".3f")
    except ImportError:
        return df.to_string(index=False)


def _run_methods(args, df: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    methods = ["crc", "ltt"] if args.method == "both" else [args.method]
    return pd.concat([guarantee_curve(df, rows, tuple(args.alphas), args.splits, m, args.seed, args.by, args.delta)
                      for m in methods], ignore_index=True)


def _load_run(run: Path, labels: str | None, key: str | None) -> tuple[pd.DataFrame, list[dict]]:
    from common import ROOT, read_jsonl
    from evaluate import _primary, prepare
    ann = ROOT / "data" / "annotations" / run.name
    df = _primary(prepare(labels or ann / "adjudicated.csv", key or ann / "KEY_DO_NOT_OPEN.csv"))
    files = sorted(run.glob("*.verify-critic-det-program.jsonl"))
    if not files:
        raise SystemExit(f"no *.verify-critic-det-program.jsonl in {run}")
    return df, [r for f in files for r in read_jsonl(f)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run dir, e.g. data/outputs/main-v1")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--alphas", nargs="*", type=float, default=list(ALPHAS))
    ap.add_argument("--method", choices=["crc", "ltt", "both"], default="both")
    ap.add_argument("--by", nargs="*", default=[], help="breakdown columns, e.g. transformation")
    ap.add_argument("--splits", type=int, default=200)
    ap.add_argument("--delta", type=float, default=0.1, help="LTT failure probability")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.synthetic:
        df, rows = synthetic()
        out = Path(args.out) if args.out else None
    elif args.run:
        run = Path(args.run)
        df, rows = _load_run(run, args.labels, args.key)
        out = Path(args.out) if args.out else run / "analysis" / "conformal.csv"
    else:
        ap.error("give --run or --synthetic")
    curve = _run_methods(args, df, rows)
    print(f"## Risk-controlled PASS: {len(df)} labelled items, {df['source_id'].nunique()} sources, "
          f"{args.splits} source-level splits\n")
    print(_md(curve))
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        curve.to_csv(out, index=False)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
