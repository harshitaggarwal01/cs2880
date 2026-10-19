"""Analysis: rates with source-clustered bootstrap CIs, paired comparisons, verifier metrics, agreement.

  # main study
  python src/evaluate.py --labels data/annotations/main-v1/adjudicated.csv \
      --key data/annotations/main-v1/KEY_DO_NOT_OPEN.csv --verify <verify.jsonl> [--double A.csv B.csv]
  # pilot demo (labels already carry model/transformation columns)
  python src/evaluate.py --labels pilot/pilot_annotations_PRELIMINARY.csv --pilot

The source problem is the resampling unit: all adaptations of one source are
drawn together, so the ~500 outputs are never treated as independent.
"""
from __future__ import annotations

import argparse
import itertools
import json
from math import comb

import numpy as np
import pandas as pd

B = 10_000
SEED = 2880


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
    groups = {k: g for k, g in df.groupby("source_id")}
    keys = np.array(list(groups))
    point = stat(df)
    vals = []
    for _ in range(b):
        sample = pd.concat([groups[k] for k in rng.choice(keys, len(keys))], ignore_index=True)
        v = stat(sample)
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


# ------------------------------------------------------------------ cli

def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False, floatfmt=".3f") if hasattr(df, "to_markdown") else df.to_string(index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--key")
    ap.add_argument("--verify", nargs="*", default=[])
    ap.add_argument("--double", nargs=2, metavar=("A_CSV", "B_CSV"))
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--boot", type=int, default=B)
    args = ap.parse_args()

    df = pd.read_csv(args.labels)
    if args.key:
        df = df.merge(pd.read_csv(args.key), on="annotation_id")
        df["model"] = df["generator"]
    df = derive(df)
    df["condition"] = df["model"].astype(str) + "|" + df["transformation"].astype(str)

    print("## Outcome rates (95% CI, source-clustered bootstrap)\n")
    for outcome in ("SAFE", "SAFE_AND_USEFUL", "MATH_OK", "NO_LEAK"):
        print(f"### {outcome}\n")
        print(md(rate_table(df, outcome, ["model", "transformation"], args.boot)), "\n")

    print("## Paired comparisons on SAFE (exact McNemar, Holm-adjusted)\n")
    print(md(paired_comparisons(df, "SAFE", "condition", args.boot)), "\n")

    flag_col = "checker_decision" if args.pilot else None
    if args.pilot:
        df["FLAG_ANY"] = (df["checker_decision"] != "PASS").astype(int)
        df["FLAG_REJECT"] = (df["checker_decision"] == "REJECT").astype(int)
        for col in ("FLAG_ANY", "FLAG_REJECT"):
            print(f"## Deterministic checker vs labels ({col})\n")
            print(json.dumps(verifier_metrics(df, col, args.boot), indent=1, default=float), "\n")
    for path in args.verify:
        v = pd.read_json(path, lines=True)[["output_id", "decision"]]
        d = df.merge(v, on="output_id")
        d["FLAG_ANY"] = (d["decision"] != "PASS").astype(int)
        d["FLAG_REJECT"] = (d["decision"] == "REJECT").astype(int)
        for col in ("FLAG_ANY", "FLAG_REJECT"):
            print(f"## Verifier {path} ({col})\n")
            print(json.dumps(verifier_metrics(d, col, args.boot), indent=1, default=float), "\n")
    if args.double:
        a, b = (derive(pd.read_csv(p)) for p in args.double)
        print("## Inter-annotator agreement (before adjudication)\n")
        print(md(agreement(a, b)))
    del flag_col


if __name__ == "__main__":
    main()
