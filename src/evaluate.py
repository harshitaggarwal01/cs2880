"""Analysis: rates with source-clustered bootstrap CIs, paired comparisons, verifier metrics, agreement.

  # main study
  python src/evaluate.py --labels data/annotations/main-v1/adjudicated.csv \
      --key data/annotations/main-v1/KEY_DO_NOT_OPEN.csv --verify <verify.jsonl> [--double A.csv B.csv]
  # same, and write every table as CSV/JSON under one folder (rates, families, presentation_vs_baseline,
  # layer_ablations, repair, logit, agreement)
  python src/evaluate.py --labels ... --key ... --verify ... --analysis-dir data/outputs/main-v1/analysis
  # pilot demo (labels already carry model/transformation columns)
  python src/evaluate.py --labels pilot/pilot_annotations_PRELIMINARY.csv --pilot

The source problem is the resampling unit: all adaptations of one source are
drawn together, so the ~500 outputs are never treated as independent.
"""
from __future__ import annotations

import argparse
import itertools
import json
import warnings
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

from common import FROZEN, TAG_PATTERNS, read_jsonl, step_bucket, tags

B = 10_000
SEED = 2880
BASELINE = "deterministic"      # generator name of the deterministic chunking baseline
LAYER_SETS = {"det": {"det"}, "critic": {"critic"}, "det+critic": {"det", "critic"},
              "det+critic+program": {"det", "critic", "program"}}


# ------------------------------------------------------------------ outcome derivation

def derive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    lvl = pd.to_numeric(df["leakage_level"], errors="coerce").fillna(0)
    pres = pd.to_numeric(df["presentation"], errors="coerce")
    codes = df["failure_codes"].fillna("").astype(str)
    df["SAFE"] = ((df["math_fidelity"] == "PASS") & (df["target_preserved"] == "PASS")
                  & (df["solvability_changed"] == "NO") & (df["ambiguity"] != "NEW") & (lvl == 0)).astype(int)
    if "abstention_appropriate" in df:
        abst_ok = df["abstention_appropriate"].eq("YES")
    else:  # pilot sheet: abstention judged via adaptation_needed
        abst_ok = df.get("status", pd.Series("", index=df.index)).eq("NO_REWRITE_NEEDED") & df["adaptation_needed"].ne("YES")
    useful = ((pres >= 2) & ~codes.str.contains("NO_ADAPT|HARMFUL_FRAGMENT")) | abst_ok
    df["SAFE_AND_USEFUL"] = (df["SAFE"].astype(bool) & useful).astype(int)
    df["MATH_OK"] = ((df["math_fidelity"] == "PASS") & (df["target_preserved"] == "PASS")).astype(int)
    df["NO_LEAK"] = (lvl == 0).astype(int)
    return df


# ------------------------------------------------------------------ bootstrap

def cluster_boot(df: pd.DataFrame, stat, b: int = B, seed: int = SEED) -> tuple[float, float, float]:
    """Point estimate and 95% percentile CI, resampling source problems with replacement."""
    rng = np.random.default_rng(seed)
    df = df.reset_index(drop=True)
    groups = {k: np.asarray(v) for k, v in df.groupby("source_id").indices.items()}
    keys = np.array(list(groups))
    point = stat(df)
    vals = []
    for _ in range(b):
        take = np.concatenate([groups[k] for k in rng.choice(keys, len(keys))])
        v = stat(df.iloc[take].reset_index(drop=True))
        if v is not None and not np.isnan(v):
            vals.append(v)
    lo, hi = np.percentile(vals, [2.5, 97.5]) if vals else (np.nan, np.nan)
    return point, lo, hi


def rate_table(df: pd.DataFrame, outcome: str, by: list[str], b: int) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(by):
        p, lo, hi = cluster_boot(g, lambda d: d[outcome].mean(), b)
        rows.append({**dict(zip(by, key if isinstance(key, tuple) else (key,))), "n": len(g),
                     "k": int(g[outcome].sum()), "rate": p, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ paired tests

def mcnemar_exact(x, y) -> tuple[int, int, float]:
    x, y = np.asarray(x), np.asarray(y)
    b = int(((x == 1) & (y == 0)).sum())
    c = int(((x == 0) & (y == 1)).sum())
    n = b + c
    if n == 0:
        return b, c, 1.0
    p = 2 * sum(comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return b, c, min(1.0, p)


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(pvals) - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def paired_comparisons(df: pd.DataFrame, outcome: str, cond_col: str, b: int) -> pd.DataFrame:
    wide = df.pivot_table(index="source_id", columns=cond_col, values=outcome, aggfunc="first")
    rows = []
    for a, c in itertools.combinations(wide.columns, 2):
        pair = wide[[a, c]].dropna()
        if len(pair) < 2:
            continue
        diff = pair[a] - pair[c]
        long = pd.DataFrame({"source_id": pair.index, "d": diff.values})
        p, lo, hi = cluster_boot(long, lambda d: d["d"].mean(), b)
        bb, cc, pv = mcnemar_exact(pair[a].values, pair[c].values)
        rows.append({"A": a, "B": c, "n_pairs": len(pair), "diff_A_minus_B": p, "ci_lo": lo, "ci_hi": hi,
                     "A_only": bb, "B_only": cc, "mcnemar_p": pv})
    out = pd.DataFrame(rows)
    if len(out):
        out["holm_p"] = holm(out["mcnemar_p"].tolist())
    return out


# ------------------------------------------------------------------ verifier metrics

def verifier_metrics(df: pd.DataFrame, flag_col: str, b: int) -> dict:
    """Positive class = UNSAFE (human label). flag_col = 1 if verifier did not PASS the item."""
    def m(d):
        unsafe, flag = 1 - d["SAFE"], d[flag_col]
        tp = int(((unsafe == 1) & (flag == 1)).sum()); fn = int(((unsafe == 1) & (flag == 0)).sum())
        fp = int(((unsafe == 0) & (flag == 1)).sum()); tn = int(((unsafe == 0) & (flag == 0)).sum())
        return tp, fn, fp, tn
    tp, fn, fp, tn = m(df)
    safe_div = lambda a, c: a / c if c else float("nan")  # noqa: E731
    res = {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
           "recall_unsafe": safe_div(tp, tp + fn), "precision": safe_div(tp, tp + fp),
           "specificity": safe_div(tn, tn + fp), "npv": safe_div(tn, tn + fn),
           "f1": safe_div(2 * tp, 2 * tp + fp + fn), "flag_rate": safe_div(tp + fp, tp + fn + fp + tn)}
    _, lo, hi = cluster_boot(df, lambda d: safe_div(*(lambda t: (t[0], t[0] + t[1]))(m(d))), b)
    res["recall_ci"] = (lo, hi)
    return res


# ------------------------------------------------------------------ agreement

def cohen_kappa(a, b, weights: str | None = None) -> float:
    a, b = pd.Series(a).astype(str).values, pd.Series(b).astype(str).values
    cats = sorted(set(a) | set(b))
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    if k == 1:
        return 1.0
    obs = np.zeros((k, k))
    for x, y in zip(a, b):
        obs[idx[x], idx[y]] += 1
    obs /= obs.sum()
    exp = np.outer(obs.sum(1), obs.sum(0))
    if weights == "quadratic":
        vals = np.array([float(c) for c in cats])
        w = (vals[:, None] - vals[None, :]) ** 2 / (vals.max() - vals.min()) ** 2
    else:
        w = 1 - np.eye(k)
    denom = (w * exp).sum()
    return 1 - (w * obs).sum() / denom if denom else 1.0


def gwet_ac1(a, b) -> float:
    a, b = pd.Series(a).astype(str).values, pd.Series(b).astype(str).values
    cats = sorted(set(a) | set(b))
    q = len(cats)
    if q == 1:
        return 1.0
    pa = np.mean(a == b)
    pi = np.array([(np.mean(a == c) + np.mean(b == c)) / 2 for c in cats])
    pe = (pi * (1 - pi)).sum() / (q - 1)
    return (pa - pe) / (1 - pe)


def agreement(df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:
    m = df_a.merge(df_b, on="annotation_id", suffixes=("_a", "_b"))
    rows = []
    for col, w in [("math_fidelity", None), ("target_preserved", None), ("ambiguity", None),
                   ("leakage_level", "quadratic"), ("presentation", "quadratic"), ("SAFE", None)]:
        x, y = m[f"{col}_a"], m[f"{col}_b"]
        keep = x.notna() & y.notna() & (x.astype(str) != "") & (y.astype(str) != "")
        x, y = x[keep], y[keep]
        rows.append({"label": col, "n": int(keep.sum()), "raw_agreement": float(np.mean(x.astype(str).values == y.astype(str).values)),
                     "kappa": cohen_kappa(x, y, w), "kappa_weighting": w or "none", "gwet_ac1": gwet_ac1(x, y)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ shared helpers for the Phase-1 analyses

def _gen(df: pd.DataFrame) -> pd.Series:
    """Generator name: `generator` (from the annotation key) if present, else `model` (pilot sheet)."""
    return df["generator"] if "generator" in df else df["model"]


def _primary(df: pd.DataFrame) -> pd.DataFrame:
    """First-pass rows only: repairs are analysed separately (see repair_outcomes)."""
    if "is_repair" not in df:
        return df
    return df[~df["is_repair"].astype(str).str.lower().eq("true")]


def load_source_rows(paths: list[str | Path] | None = None) -> dict[str, dict]:
    """source_id -> frozen source row (text, dataset, n_steps if GSM8K). Default: every data/frozen/*.jsonl with text."""
    files = [Path(p) for p in paths] if paths else sorted(FROZEN.glob("*.jsonl"))
    out: dict[str, dict] = {}
    for f in files:
        for r in read_jsonl(f):
            if r.get("text"):
                out[r["source_id"]] = r
    return out


def load_labels(path: str | Path) -> pd.DataFrame:
    """Read a label CSV; if it holds adjudicated (annotator == ADJ) rows, keep only those."""
    df = pd.read_csv(path)
    if "annotator" in df and df["annotator"].eq("ADJ").any():
        df = df[df["annotator"] == "ADJ"]
    return df


def prepare(labels: str | Path, key: str | Path | None = None) -> pd.DataFrame:
    """Labels (+ key) -> derived outcomes with model/condition/is_repair columns."""
    df = load_labels(labels)
    if key:
        df = df.merge(pd.read_csv(key), on="annotation_id")
        df["model"] = df["generator"]
    df = derive(df)
    if "is_repair" in df:
        df["is_repair"] = df["is_repair"].astype(str).str.lower().eq("true")
    df["condition"] = df["model"].astype(str) + "|" + df["transformation"].astype(str)
    return df


def _jsonable(x):
    if isinstance(x, pd.DataFrame):
        return x.to_dict(orient="records")
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer, np.bool_)):
        return x.item()
    if isinstance(x, (float, np.floating)) and np.isnan(x):
        return None
    return x


def write_analysis(dir: Path, name: str, df_or_dict) -> Path:
    """Write a DataFrame as <name>.csv or a dict/list as <name>.json under `dir`; return the path."""
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)
    if isinstance(df_or_dict, pd.DataFrame):
        path = dir / f"{name}.csv"
        df_or_dict.to_csv(path, index=False)
    else:
        path = dir / f"{name}.json"
        path.write_text(json.dumps(_jsonable(df_or_dict), indent=1, default=float))
    return path


# ------------------------------------------------------------------ prespecified families (dossier 14)

def _paired_stats(xa: pd.Series, xb: pd.Series, b: int) -> dict | None:
    """Paired difference A - B on one binary outcome, indexed by source_id; None if < 2 pairs."""
    pair = pd.concat([xa.rename("a"), xb.rename("b")], axis=1).dropna()
    if len(pair) < 2:
        return None
    long = pd.DataFrame({"source_id": pair.index, "d": (pair["a"] - pair["b"]).values})
    diff, lo, hi = cluster_boot(long, lambda d: d["d"].mean(), b)
    n_a, n_b, p = mcnemar_exact(pair["a"].values, pair["b"].values)
    return {"n_pairs": len(pair), "diff": diff, "ci_lo": lo, "ci_hi": hi, "A_only": n_a, "B_only": n_b, "mcnemar_p": p}


def prespecified_families(df: pd.DataFrame, outcome: str = "SAFE", b: int = B) -> pd.DataFrame:
    """The three prespecified paired families on `outcome` (diff = A - B), Holm-adjusted within each family only.

    F1 realistic_vs_constrained_chunked: per generator, naive (A) vs chunked (B)
    F2 generator_A_vs_B: per transformation, generator pair (first name sorted = A)
    F3 plain_vs_chunked: per generator, plain (A) vs chunked (B)
    The deterministic baseline and repair rows are not part of any family.
    """
    d = _primary(df).assign(_g=lambda x: _gen(x))
    d = d[d["_g"] != BASELINE]
    gens = sorted(d["_g"].unique())

    def col(g: str, tf: str) -> pd.Series:
        return d[(d["_g"] == g) & (d["transformation"] == tf)].groupby("source_id")[outcome].first()

    specs: list[tuple[str, str, pd.Series, pd.Series]] = []
    for g in gens:
        specs.append(("realistic_vs_constrained_chunked", f"{g}: naive vs chunked", col(g, "naive"), col(g, "chunked")))
    for tf in ("plain", "chunked", "naive"):
        for g1, g2 in itertools.combinations(gens, 2):
            specs.append(("generator_A_vs_B", f"{tf}: {g1} vs {g2}", col(g1, tf), col(g2, tf)))
    for g in gens:
        specs.append(("plain_vs_chunked", f"{g}: plain vs chunked", col(g, "plain"), col(g, "chunked")))

    rows = []
    for family, comparison, xa, xb in specs:
        st = _paired_stats(xa, xb, b)
        if st:
            rows.append({"family": family, "comparison": comparison, **st})
    cols = ["family", "comparison", "n_pairs", "diff", "ci_lo", "ci_hi", "A_only", "B_only", "mcnemar_p", "holm_p"]
    out = pd.DataFrame(rows, columns=cols[:-1])
    out["holm_p"] = np.nan
    for idx in out.groupby("family").groups.values():
        out.loc[idx, "holm_p"] = holm(out.loc[idx, "mcnemar_p"].tolist())
    return out[cols]


# ------------------------------------------------------------------ presentation vs deterministic baseline (RQ5)

def wilcoxon_p(d) -> float:
    """Two-sided Wilcoxon signed-rank p (zero_method='wilcox'); 1.0 if every difference is zero, NaN if empty."""
    from scipy.stats import wilcoxon
    d = np.asarray(d, dtype=float)
    if len(d) == 0:
        return float("nan")
    if np.all(d == 0):
        return 1.0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return float(wilcoxon(d, zero_method="wilcox").pvalue)
    except ValueError:
        return float("nan")


def _strata(ids: pd.Index, sources: dict | None, cuts: tuple[float, float] | None) -> list[tuple[str, str, list]]:
    """(stratum_type, stratum, source_ids) for overall, step bucket and source-length tercile."""
    out = [("overall", "all", list(ids))]
    if not sources:
        return out
    by_step: dict[str, list] = {}
    for sid in ids:
        n = (sources.get(sid) or {}).get("n_steps")
        if n is not None and not pd.isna(n):
            by_step.setdefault(step_bucket(int(n)), []).append(sid)
    out += [("step_bucket", k, v) for k, v in sorted(by_step.items())]
    if cuts:
        by_len: dict[str, list] = {}
        for sid in ids:
            text = (sources.get(sid) or {}).get("text")
            if text:
                w = len(text.split())
                by_len.setdefault("short" if w <= cuts[0] else "mid" if w <= cuts[1] else "long", []).append(sid)
        out += [("length_tercile", k, by_len[k]) for k in ("short", "mid", "long") if k in by_len]
    return out


def presentation_vs_baseline(df: pd.DataFrame, b: int = B, sources: dict | None = None) -> pd.DataFrame:
    """Per LLM generator, chunked presentation minus the deterministic chunked baseline on the same source.

    Null presentation (abstentions) is ignored. Reports mean paired difference, source-cluster bootstrap CI and a
    Wilcoxon signed-rank p (sensitivity check), overall and by step bucket and source-length tercile when `sources`
    (source_id -> row with text / n_steps) is given.
    """
    d = _primary(df).assign(_g=lambda x: _gen(x), _p=lambda x: pd.to_numeric(x["presentation"], errors="coerce"))
    d = d[(d["transformation"] == "chunked") & d["_p"].notna()]
    base = d[d["_g"] == BASELINE].groupby("source_id")["_p"].mean()
    cols = ["generator", "stratum_type", "stratum", "n_pairs", "mean_llm", "mean_baseline", "diff", "ci_lo", "ci_hi",
            "wilcoxon_p"]
    if base.empty:
        return pd.DataFrame(columns=cols)
    cuts = None
    if sources:
        words = [len(sources[s]["text"].split()) for s in base.index if sources.get(s, {}).get("text")]
        if len(words) >= 3:
            cuts = tuple(np.quantile(words, [1 / 3, 2 / 3]))
    rows = []
    for g in sorted(set(d["_g"]) - {BASELINE}):
        llm = d[d["_g"] == g].groupby("source_id")["_p"].mean()
        pair = pd.concat([llm.rename("llm"), base.rename("base")], axis=1).dropna()
        for stype, stratum, ids in _strata(pair.index, sources, cuts):
            sub = pair.loc[ids]
            if len(sub) < 2:
                continue
            diffs = sub["llm"] - sub["base"]
            long = pd.DataFrame({"source_id": sub.index, "d": diffs.values})
            point, lo, hi = cluster_boot(long, lambda x: x["d"].mean(), b)
            rows.append({"generator": g, "stratum_type": stype, "stratum": stratum, "n_pairs": len(sub),
                         "mean_llm": sub["llm"].mean(), "mean_baseline": sub["base"].mean(), "diff": point,
                         "ci_lo": lo, "ci_hi": hi, "wilcoxon_p": wilcoxon_p(diffs.values)})
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------ exploratory logistic regression (UNSAFE)

def source_features(sources: dict) -> pd.DataFrame:
    """One row per source: n_steps (NaN if not GSM8K), words, dataset, tag_<name> 0/1 columns."""
    rows = []
    for sid, s in sources.items():
        text = s.get("text") or ""
        rows.append({"source_id": sid, "n_steps": s.get("n_steps"), "words": len(text.split()),
                     "dataset": s.get("dataset", "unknown"), **{f"tag_{k}": int(v) for k, v in tags(text).items()}})
    return pd.DataFrame(rows)


def _design(df: pd.DataFrame, sources: dict) -> tuple[pd.Series, pd.DataFrame, np.ndarray]:
    d = _primary(df).assign(_g=lambda x: _gen(x))
    d = d[(d["_g"] != BASELINE) & d["SAFE"].notna()].copy()
    d["UNSAFE"] = 1 - d["SAFE"].astype(int)
    d["_cond"] = d["_g"].astype(str) + "|" + d["transformation"].astype(str)
    d = d.merge(source_features(sources), on="source_id", how="inner")
    X = pd.DataFrame(index=d.index)
    if d["n_steps"].notna().any():
        X["n_steps"] = d["n_steps"].astype(float).fillna(d["n_steps"].median())
    X["words_per10"] = d["words"] / 10.0
    for k in TAG_PATTERNS:
        X[f"tag_{k}"] = d[f"tag_{k}"]
    if d["dataset"].nunique() > 1:
        X = X.join(pd.get_dummies(d["dataset"], prefix="dataset", drop_first=True, dtype=float))
    if d["_cond"].nunique() > 1:
        X = X.join(pd.get_dummies(d["_cond"], prefix="cond", drop_first=True, dtype=float))
    X = X.loc[:, X.nunique() > 1].astype(float)
    return d["UNSAFE"], X, pd.factorize(d["source_id"])[0]


def firth_logit(y: np.ndarray, X: np.ndarray, maxiter: int = 100, tol: float = 1e-8) -> tuple[np.ndarray, bool]:
    """Firth (1993) bias-reduced logistic regression: maximise loglik + 0.5 log|X'WX| (Jeffreys prior).

    Estimates stay finite under complete or quasi-complete separation (Heinze & Schemper 2002). Newton steps on the
    modified score sum_i (y_i - p_i + h_i (1/2 - p_i)) x_i, h = hat-matrix diagonal, with step halving. X must
    include the intercept column. Returns (beta, converged).
    """
    y, X = np.asarray(y, float), np.asarray(X, float)
    beta = np.zeros(X.shape[1])

    def penalised(b):
        eta = X @ b
        p = 1 / (1 + np.exp(-eta))
        info = X.T @ (X * (p * (1 - p))[:, None])
        sign, logdet = np.linalg.slogdet(info)
        ll = float(np.sum(y * eta - np.logaddexp(0, eta)))
        return ll + 0.5 * (logdet if sign > 0 else -np.inf), p, info

    obj, p, info = penalised(beta)
    for _ in range(maxiter):
        w = p * (1 - p)
        inv = np.linalg.pinv(info)
        h = np.einsum("ij,jk,ik->i", X, inv, X) * w
        step = inv @ (X.T @ (y - p + h * (0.5 - p)))
        t = 1.0
        while True:
            new_obj, new_p, new_info = penalised(beta + t * step)
            if new_obj >= obj - 1e-12 or t < 1e-4:
                break
            t /= 2
        beta = beta + t * step
        obj, p, info = new_obj, new_p, new_info
        if np.max(np.abs(t * step)) < tol:
            return beta, True
    return beta, False


def logit_unsafe(df: pd.DataFrame, sources: dict, n_boot: int = 400, seed: int = 0) -> dict:
    """EXPLORATORY logit of UNSAFE on n_steps, length (words/10), tag, dataset and condition dummies.

    Not part of the three prespecified test families. The deterministic baseline (safe by construction) and repair
    rows are excluded. First an ordinary MLE with SEs clustered by source. If that fit shows separation (statsmodels
    raises or warns, does not converge, gives non-finite SEs, max SE >= 10 or |coef| >= 15), the model is refit by
    Firth's bias-reduced logit (`firth_logit`) and inference comes from a source-cluster bootstrap of the Firth fit:
    se = bootstrap SD, CI = percentile interval, p = two-sided bootstrap sign p-value, z = coef / se. Separation is
    likely here (constrained prompts can have no unsafe items at all). Returns {"table", "n", "penalized", "converged",
    "method"}; `penalized` means the Firth fallback was used and `converged` refers to the unpenalised fit.
    """
    import statsmodels.api as sm
    from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationError

    y, X, groups = _design(df, sources)
    cols = ["term", "coef", "se", "z", "p", "odds_ratio", "or_lo", "or_hi"]
    if len(y) < 10 or y.nunique() < 2 or X.shape[1] == 0:
        return {"table": pd.DataFrame(columns=cols), "n": int(len(y)), "penalized": False, "converged": False,
                "method": "none"}
    Xc = sm.add_constant(X, has_constant="add")
    ok = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            res = sm.Logit(y, Xc).fit(disp=0, maxiter=200, cov_type="cluster", cov_kwds={"groups": groups})
            bad_warn = any(issubclass(w.category, ConvergenceWarning) or "separation" in str(w.message).lower()
                           for w in caught)
            ok = (not bad_warn and bool(res.mle_retvals.get("converged", True))
                  and bool(np.all(np.isfinite(res.bse))) and float(np.max(res.bse)) < 10
                  and float(np.abs(res.params).max()) < 15)
        except (PerfectSeparationError, np.linalg.LinAlgError, ValueError):
            ok = False
    if ok:
        ci = res.conf_int()
        table = pd.DataFrame({"term": Xc.columns, "coef": res.params.values, "se": res.bse.values,
                              "z": res.tvalues.values, "p": res.pvalues.values,
                              "odds_ratio": np.exp(res.params.values), "or_lo": np.exp(ci[0].values),
                              "or_hi": np.exp(ci[1].values)})
        return {"table": table, "n": int(len(y)), "penalized": False, "converged": True, "method": "mle-cluster"}

    yv, Xv = y.to_numpy(float), Xc.to_numpy(float)
    coef, _ = firth_logit(yv, Xv)
    rng = np.random.default_rng(seed)
    k = int(groups.max()) + 1
    members = [np.flatnonzero(groups == g) for g in range(k)]
    draws = []
    for _ in range(n_boot):
        idx = np.concatenate([members[g] for g in rng.integers(0, k, k)])
        if np.unique(yv[idx]).size < 2:
            continue
        b, _ = firth_logit(yv[idx], Xv[idx], maxiter=50)
        draws.append(b)
    draws = np.asarray(draws)
    if len(draws) >= 20:
        se = draws.std(axis=0, ddof=1)
        lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
        pval = np.minimum(1.0, 2 * np.minimum((draws <= 0).mean(axis=0), (draws >= 0).mean(axis=0)))
    else:
        se = lo = hi = pval = np.full(len(coef), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = coef / se
    table = pd.DataFrame({"term": Xc.columns, "coef": coef, "se": se, "z": z, "p": pval,
                          "odds_ratio": np.exp(coef), "or_lo": np.exp(lo), "or_hi": np.exp(hi)})
    return {"table": table, "n": int(len(y)), "penalized": True, "converged": False, "method": "firth-bootstrap"}


# ------------------------------------------------------------------ verifier layer ablations (RQ3)

def subset_decision(row: dict, layers: set[str]) -> tuple[str, list[str]]:
    """Decision a verifier restricted to `layers` ({'det','critic','program'}) would have made on a stored row.

    Uses verify.decide_subset when available; otherwise recomputes with verify.decide from the stored fields and
    drops the 'critic missing' REVIEW reason when the critic is not part of the layer set.
    """
    import verify
    if hasattr(verify, "decide_subset"):
        return verify.decide_subset(row, layers)
    det = row["deterministic"] if "det" in layers else {"decision": "PASS", "flags": []}
    critic = row.get("critic") if "critic" in layers else None
    program = row.get("program") if "program" in layers else None
    decision, reasons = verify.decide(det, critic, program)
    if "critic" not in layers:
        reasons = [r for r in reasons if r != "critic:missing"]
        if decision == "REVIEW" and not reasons:
            decision = "PASS"
    return decision, reasons


def _layers_available(row: dict) -> set[str]:
    if row.get("layers"):
        return set(row["layers"])
    return ({"det"} if row.get("deterministic") else set()) | ({"critic"} if row.get("critic") is not None else set()) \
        | ({"program"} if row.get("program") is not None else set())


def layer_ablations(verify_rows: list[dict], labels_df: pd.DataFrame, b: int = B) -> pd.DataFrame:
    """Verifier metrics (positive class = human UNSAFE) per layer set, subset and operating point.

    Subsets: realistic (transformation naive), constrained (all others), overall. Operating points: FLAG_REJECT
    (flag only REJECT) and FLAG_ANY (flag REVIEW or REJECT). Rows whose stored verification lacks a needed layer
    are skipped for that layer set. Labels need output_id, SAFE, transformation, source_id.
    """
    lab = _primary(labels_df)
    cols = ["layers", "subset", "operating_point", "tp", "fn", "fp", "tn", "recall_unsafe", "recall_lo", "recall_hi",
            "precision", "flag_rate"]
    rows = []
    for name, layers in LAYER_SETS.items():
        dec = {r["output_id"]: subset_decision(r, layers)[0] for r in verify_rows if layers <= _layers_available(r)}
        d = lab[lab["output_id"].isin(dec)].copy()
        d["decision"] = d["output_id"].map(dec)
        d["FLAG_ANY"] = (d["decision"] != "PASS").astype(int)
        d["FLAG_REJECT"] = (d["decision"] == "REJECT").astype(int)
        naive = d["transformation"] == "naive"
        for subset, sub in (("realistic", d[naive]), ("constrained", d[~naive]), ("overall", d)):
            if sub.empty:
                continue
            for op in ("FLAG_REJECT", "FLAG_ANY"):
                m = verifier_metrics(sub, op, b)
                rows.append({"layers": name, "subset": subset, "operating_point": op, "tp": m["tp"], "fn": m["fn"],
                             "fp": m["fp"], "tn": m["tn"], "recall_unsafe": m["recall_unsafe"],
                             "recall_lo": m["recall_ci"][0], "recall_hi": m["recall_ci"][1],
                             "precision": m["precision"], "flag_rate": m["flag_rate"]})
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------ constrained repair outcomes

def repair_outcomes(labels_df: pd.DataFrame, key_df: pd.DataFrame | None = None) -> dict:
    """Before/after comparison for repaired items (key columns is_repair, repair_of).

    Counts unsafe->safe, safe->unsafe and unchanged (same SAFE value) over repairs whose original is also labelled;
    mean change in presentation (after - before, where both are scored); SAFE_AND_USEFUL and SAFE yield per 100
    requests before vs after, where a repair replaces its original (deterministic baseline excluded).
    """
    d = labels_df
    if key_df is not None:
        extra = [c for c in ("output_id", "generator", "is_repair", "repair_of") if c in key_df and c not in d]
        d = d.merge(key_df[["annotation_id", *extra]], on="annotation_id", how="left")
    d = d.copy()
    if "is_repair" not in d:
        d["is_repair"] = False
    if "repair_of" not in d:
        d["repair_of"] = np.nan
    d["is_repair"] = d["is_repair"].astype(str).str.lower().eq("true")
    d["_g"] = _gen(d)
    d = d[d["_g"] != BASELINE]
    orig = d[~d["is_repair"]].set_index("output_id")
    rep = d[d["is_repair"]].dropna(subset=["repair_of"])
    rep = rep[rep["repair_of"].isin(orig.index)]
    before = orig.loc[rep["repair_of"]]
    b_safe, a_safe = before["SAFE"].to_numpy(), rep["SAFE"].to_numpy()
    pres_b = pd.to_numeric(before["presentation"], errors="coerce").to_numpy()
    pres_a = pd.to_numeric(rep["presentation"], errors="coerce").to_numpy()
    both = ~np.isnan(pres_b) & ~np.isnan(pres_a)

    def per100(frame: pd.DataFrame, col: str) -> float:
        return 100 * float(frame[col].sum()) / len(frame) if len(frame) else float("nan")

    after = orig.copy()
    swap = rep.set_index("repair_of")
    for col in ("SAFE", "SAFE_AND_USEFUL"):
        after.loc[swap.index, col] = swap[col].to_numpy()
    out = {"n_originals": int(len(orig)), "n_repaired": int(len(rep)),
           "unsafe_to_safe": int(((b_safe == 0) & (a_safe == 1)).sum()),
           "safe_to_unsafe": int(((b_safe == 1) & (a_safe == 0)).sum()),
           "unchanged": int((b_safe == a_safe).sum()),
           "unchanged_safe": int(((b_safe == 1) & (a_safe == 1)).sum()),
           "unchanged_unsafe": int(((b_safe == 0) & (a_safe == 0)).sum()),
           "mean_delta_presentation": float((pres_a[both] - pres_b[both]).mean()) if both.any() else float("nan"),
           "n_delta_presentation": int(both.sum()),
           "safe_per100_before": per100(orig, "SAFE"), "safe_per100_after": per100(after, "SAFE"),
           "safe_useful_per100_before": per100(orig, "SAFE_AND_USEFUL"),
           "safe_useful_per100_after": per100(after, "SAFE_AND_USEFUL")}
    out["by_generator"] = [
        {"generator": g, "n": len(o), "n_repaired": int((rep["_g"] == g).sum()),
         "safe_per100_before": per100(o, "SAFE"), "safe_per100_after": per100(after.loc[o.index], "SAFE"),
         "safe_useful_per100_before": per100(o, "SAFE_AND_USEFUL"),
         "safe_useful_per100_after": per100(after.loc[o.index], "SAFE_AND_USEFUL")}
        for g, o in orig.groupby("_g")]
    return out


# ------------------------------------------------------------------ cli

def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False, floatfmt=".3f") if hasattr(df, "to_markdown") else df.to_string(index=False)


def all_rates(df: pd.DataFrame, b: int) -> pd.DataFrame:
    """Rate tables for the four outcomes, stacked with an `outcome` column."""
    parts = [rate_table(df, o, ["model", "transformation"], b).assign(outcome=o)
             for o in ("SAFE", "SAFE_AND_USEFUL", "MATH_OK", "NO_LEAK")]
    return pd.concat(parts, ignore_index=True)[["outcome", "model", "transformation", "n", "k", "rate", "ci_lo", "ci_hi"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--key")
    ap.add_argument("--verify", nargs="*", default=[])
    ap.add_argument("--double", nargs=2, metavar=("A_CSV", "B_CSV"))
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--boot", type=int, default=B)
    ap.add_argument("--analysis-dir", help="also write rates, families, presentation_vs_baseline, layer_ablations, "
                                           "repair, logit, agreement as CSV/JSON files here")
    ap.add_argument("--sources", nargs="*", default=None,
                    help="frozen jsonl files with source text (default: all data/frozen/*.jsonl)")
    args = ap.parse_args()
    out_dir = Path(args.analysis_dir) if args.analysis_dir else None

    def save(name: str, obj) -> None:
        if out_dir is not None:
            write_analysis(out_dir, name, obj)

    df = prepare(args.labels, args.key)
    first = _primary(df)
    sources = load_source_rows(args.sources)

    print("## Outcome rates (95% CI, source-clustered bootstrap)\n")
    rates = all_rates(first, args.boot)
    for outcome, g in rates.groupby("outcome", sort=False):
        print(f"### {outcome}\n")
        print(md(g.drop(columns="outcome")), "\n")
    save("rates", rates)

    print("## Paired comparisons on SAFE, all condition pairs (exploratory; exact McNemar, Holm over all pairs)\n")
    print(md(paired_comparisons(first, "SAFE", "condition", args.boot)), "\n")

    print("## Prespecified families on SAFE (exact McNemar, Holm within family)\n")
    fam = prespecified_families(first, "SAFE", args.boot)
    print(md(fam), "\n")
    save("families", fam)

    pres = presentation_vs_baseline(first, args.boot, sources)
    if len(pres):
        print("## Presentation: LLM chunked minus deterministic chunked (paired, Wilcoxon sensitivity)\n")
        print(md(pres), "\n")
    save("presentation_vs_baseline", pres)

    if args.pilot:
        df["FLAG_ANY"] = (df["checker_decision"] != "PASS").astype(int)
        df["FLAG_REJECT"] = (df["checker_decision"] == "REJECT").astype(int)
        for col in ("FLAG_ANY", "FLAG_REJECT"):
            print(f"## Deterministic checker vs labels ({col})\n")
            print(json.dumps(verifier_metrics(df, col, args.boot), indent=1, default=float), "\n")
    verify_rows: list[dict] = []
    for path in args.verify:
        v = pd.read_json(path, lines=True)[["output_id", "decision"]]
        d = first.merge(v, on="output_id")
        d["FLAG_ANY"] = (d["decision"] != "PASS").astype(int)
        d["FLAG_REJECT"] = (d["decision"] == "REJECT").astype(int)
        for col in ("FLAG_ANY", "FLAG_REJECT"):
            print(f"## Verifier {path} ({col})\n")
            print(json.dumps(verifier_metrics(d, col, args.boot), indent=1, default=float), "\n")
        verify_rows += read_jsonl(Path(path))
    if verify_rows and "output_id" in first:
        abl = layer_ablations(verify_rows, first, args.boot)
        print("## Verifier layer ablations (positive class = human UNSAFE)\n")
        print(md(abl), "\n")
        save("layer_ablations", abl)

    if args.key:
        rep = repair_outcomes(df, pd.read_csv(args.key))
        print("## Repair outcomes\n")
        print(json.dumps(_jsonable(rep), indent=1), "\n")
        save("repair", rep)

    lg = logit_unsafe(first, sources)
    if len(lg["table"]):
        print(f"## Exploratory logit of UNSAFE (n={lg['n']}, penalized={lg['penalized']}, converged={lg['converged']})\n")
        print(md(lg["table"]), "\n")
    save("logit", {**lg, "table": lg["table"]})

    if args.double:
        a, b = (derive(pd.read_csv(p)) for p in args.double)
        agr = agreement(a, b)
        print("## Inter-annotator agreement (before adjudication)\n")
        print(md(agr))
        save("agreement", agr)


if __name__ == "__main__":
    main()
