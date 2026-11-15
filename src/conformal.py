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
    probability >= 1 - delta every returned lambda truly has risk <= alpha. Validity needs only that the order is fixed
    before the labels are seen (the grid depends on scores only); it does not need the risk to be monotone in lambda,
    and the conditional risk P(unsafe | PASS) need not be. Strict-to-lenient is chosen for power: the strictest
    thresholds are the ones most likely to be rejected, so the walk gets furthest.

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
    for each. `by` adds a per-condition breakdown (thresholds are still calibrated on the pooled half). These rows are
    DESCRIPTIVE: the guarantee holds for the pooled population, not within each condition. For a per-condition
    guarantee, calibrate separately on each condition (fewer sources each, so more conservative).
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


# ------------------------------------------------------------------ weighted conformal under covariate shift (opt-in)

def density_ratio_weights(X_study, X_new, clip: float | None = 20.0, C: float = 1.0) -> np.ndarray:
    """Density ratios w(x) = p_new(x) / p_study(x) at the study rows, from a logistic classifier of new-tool vs study.

    X_study (n, d) and X_new (m, d) are features of outputs (transformation, length, readability, source difficulty:
    anything observable for the NEW tool's outputs without labels). By Bayes, w(x) = P(new|x)/P(study|x) * n/m. Weights
    are clipped at `clip` (None = no clipping; clipping trades a little bias for variance) and returned for the study rows.
    Opt-in; nothing in this module calls it unless you do. Tibshirani, Foygel Barber, Candes & Ramdas (2019).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    Xs, Xn = np.asarray(X_study, dtype=float), np.asarray(X_new, dtype=float)
    Xs, Xn = Xs.reshape(len(Xs), -1), Xn.reshape(len(Xn), -1)
    sc = StandardScaler().fit(np.vstack([Xs, Xn]))
    clf = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(np.vstack([Xs, Xn])),
                                                     np.r_[np.zeros(len(Xs)), np.ones(len(Xn))])
    p = clf.predict_proba(sc.transform(Xs))[:, 1]
    w = p / np.clip(1 - p, 1e-12, None) * len(Xs) / len(Xn)
    return np.minimum(w, clip) if clip is not None else w


def effective_sample_size(w: np.ndarray) -> float:
    """Kish effective sample size (sum w)^2 / sum w^2; equals n when w is constant."""
    w = np.asarray(w, dtype=float)
    return float(w.sum() ** 2 / (w ** 2).sum()) if len(w) else 0.0


def _weighted_unit_losses(scores, losses, weights, grid, groups):
    """(units x grid) weighted loss and (units,) unit weights. Item units: loss_i and w_i. Group units: the
    weight-averaged loss within the group, with the mean weight as the group's weight. With w = 1 this is exactly
    `_unit_losses` and unit weights of 1."""
    w = np.asarray(weights, dtype=float)
    li = np.asarray(losses, dtype=float)[:, None] * (np.asarray(scores, dtype=float)[:, None] <= grid[None, :])
    if groups is None:
        return li, w
    _, codes = np.unique(np.asarray(groups), return_inverse=True)
    k = codes.max() + 1
    sums = np.zeros((k, len(grid)))
    np.add.at(sums, codes, li * w[:, None])
    wsum = np.bincount(codes, weights=w)
    return sums / wsum[:, None], wsum / np.bincount(codes)


def weighted_crc_threshold(scores: np.ndarray, losses: np.ndarray, alpha: float, weights: np.ndarray,
                           B: float = 1.0, groups=None, w_test: float | None = None) -> float:
    """Weighted Conformal Risk Control under covariate shift (Angelopoulos et al. 2024, Sec. on covariate shift, built on
    Tibshirani et al. 2019). Calibration units carry density-ratio weights w_i = p_new(x_i)/p_study(x_i); the test unit's
    weight w_test = w(X_{n+1}) is unknown, so the default is the largest calibration weight (conservative: valid for any
    test point whose ratio is at most that, which is what clipping the weights enforces). Largest lambda on the grid of
    observed scores with

        ( sum_i w_i L_i(lambda) + B * w_test ) / ( sum_i w_i + w_test )  <=  alpha,

    so E_new[L(lambda_hat)] <= alpha when the weights are the true ratios and P(unsafe | x) is shared by study and new tool
    (covariate shift only). With all w_i = 1 and w_test = 1 this is crc_threshold exactly. Estimated weights make it
    approximate: the guarantee is only as good as the density-ratio estimate; check effective_sample_size. Returns -inf if
    no lambda qualifies.
    """
    scores = np.asarray(scores, dtype=float)
    if len(scores) == 0:
        return NEG_INF
    grid = _grid(scores)
    units, uw = _weighted_unit_losses(scores, losses, weights, grid, groups)
    wt = float(np.max(uw)) if w_test is None else float(w_test)
    adj = ((uw[:, None] * units).sum(axis=0) + B * wt) / (uw.sum() + wt)
    ok = np.flatnonzero(adj <= alpha)
    return float(grid[ok[-1]]) if len(ok) else NEG_INF


def _weighted_test_metrics(test: pd.DataFrame, lam: float, w: np.ndarray) -> dict:
    """Importance-weighted test metrics (estimates of the NEW distribution's risk from study test items)."""
    passed = test["score"].to_numpy() <= lam
    unsafe = test["unsafe"].to_numpy().astype(bool)
    W = max(float(w.sum()), 1e-12)
    wp = float(w[passed].sum())
    return {"n_test": len(test), "pass_rate": wp / W, "review_rate": 1 - wp / W,
            "cond_risk": float(w[unsafe & passed].sum() / wp) if wp > 0 else 0.0,
            "unsafe_pass": float(w[unsafe & passed].sum() / W)}


def guarantee_curve_weighted(data: pd.DataFrame, weights, alphas=ALPHAS, n_splits: int = 200, seed: int = SEED,
                             B: float = 1.0, cluster: bool = True, target: pd.DataFrame | None = None,
                             w_test: float | None = None) -> pd.DataFrame:
    """Weighted analogue of guarantee_curve (CRC only): repeated source-level splits, lambda calibrated with
    weighted_crc_threshold on one half, risk measured on the other.

    data: study frame from attach_scores (score, unsafe, source_id, output_id). weights: array aligned to data rows or a
    {output_id: w} mapping (estimated once, held fixed over splits). Evaluation: with `target` (a labelled frame from the
    new tool with score and unsafe) the realized risk is the plain mean on it; without it, study test items are
    importance-weighted by w, which estimates the new-distribution risk. Columns mirror guarantee_curve, plus `unweighted_*`:
    the same split's lambda from plain crc_threshold evaluated the same way, so the two can be compared directly.
    """
    data = data.reset_index(drop=True)
    w_all = (data["output_id"].map(weights).to_numpy(float) if isinstance(weights, dict) else np.asarray(weights, float))
    if len(w_all) != len(data):
        raise ValueError("weights must align with data rows")
    data = data.assign(_w=w_all)
    recs = []
    for s in range(n_splits):
        cal, test = split_by_source(data, 0.5, seed + s)
        groups = cal["source_id"].to_numpy() if cluster else None
        for alpha in alphas:
            lam_w = weighted_crc_threshold(cal["score"].to_numpy(), cal["unsafe"].to_numpy(), alpha,
                                           cal["_w"].to_numpy(), B, groups, w_test)
            lam_u = crc_threshold(cal["score"].to_numpy(), cal["unsafe"].to_numpy(), alpha, B, groups)
            for tag, lam in (("weighted", lam_w), ("unweighted", lam_u)):
                m = (_test_metrics(target, lam) if target is not None
                     else _weighted_test_metrics(test, lam, test["_w"].to_numpy()))
                recs.append({"variant": tag, "alpha": alpha, "split": s, "lam": lam, **m})
    r = pd.DataFrame(recs)
    r["finite"] = np.isfinite(r["lam"])
    rows = []
    for (variant, a), g in r.groupby(["variant", "alpha"], sort=False):
        fin = g.loc[g["finite"], "lam"]
        rows.append({"method": "crc_weighted" if variant == "weighted" else "crc", "variant": variant, "alpha": a,
                     "n_splits": len(g), "lambda_mean": float(fin.mean()) if len(fin) else NEG_INF,
                     "frac_splits_pass_nothing": float(1 - g["finite"].mean()),
                     "review_rate_mean": g["review_rate"].mean(), "pass_rate_mean": g["pass_rate"].mean(),
                     "realized_risk_mean": g["cond_risk"].mean(),
                     "realized_unsafe_pass_mean": g["unsafe_pass"].mean(),
                     "realized_unsafe_pass_hi": np.percentile(g["unsafe_pass"], 97.5),
                     "frac_splits_unsafe_pass_below_alpha": float((g["unsafe_pass"] <= a).mean()),
                     "evaluated_on": "target" if target is not None else "study_test_weighted"})
    return pd.DataFrame(rows)


def synthetic_shift(n_study: int = 3000, n_new: int = 3000, shift: float = 1.0, seed: int = 0):
    """Planted covariate shift. A feature x ~ N(0,1) in the study, N(shift,1) for the new tool; P(unsafe | x) is the same
    in both (logistic in x, so the new tool has more unsafe outputs); the verifier score is 2*unsafe + N(0,1). One source
    per item. Returns (study frame, new frame) with output_id, source_id, x, score, unsafe."""
    rng = np.random.default_rng(seed)

    def draw(n, mu, tag):
        x = rng.normal(mu, 1.0, n)
        unsafe = (rng.random(n) < 1 / (1 + np.exp(-(-1.5 + 1.0 * x)))).astype(int)
        return pd.DataFrame({"output_id": [f"{tag}-{i}" for i in range(n)], "source_id": [f"{tag}-s{i}" for i in range(n)],
                             "x": x, "unsafe": unsafe, "SAFE": 1 - unsafe, "score": 2.0 * unsafe + rng.normal(0, 1, n)})
    return draw(n_study, 0.0, "study"), draw(n_new, shift, "new")


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
    ap.add_argument("--shift-demo", action="store_true",
                    help="opt-in: planted covariate shift, weighted vs unweighted CRC (see docs/methods/conformal_weighted.md)")
    args = ap.parse_args()
    if args.shift_demo:
        study, new = synthetic_shift()
        w = density_ratio_weights(study[["x"]], new[["x"]])
        print(f"## Weighted CRC under planted shift (ESS {effective_sample_size(w):.0f} of {len(w)}; "
              f"risk measured on the new-tool set)\n")
        print(_md(guarantee_curve_weighted(study, w, tuple(args.alphas), min(args.splits, 100), args.seed, target=new)))
        return
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
