"""Stratum-weighted pooled rate: the valid overall estimate under the lean labelling design.

  python src/ppi_pooled.py --run data/outputs/ollama-v1 [--labels ... --key ...] [--predictor decision|critic]

Why: the lean design labels strata (transformation x generator) at different rates (e.g. realistic 100%,
careful 50%, deterministic 30%). The pooled "all" row of `ppi.py` treats the labelled set as one uniform sample, so
it over-weights the fully labelled strata. This module leaves `ppi.py` and its per-stratum rows untouched and
combines them as  theta = sum_h (N_h / N) * theta_h  (N_h = all first-pass rows of stratum h).

CI: one source-clustered bootstrap shared by every stratum (the same multinomial weight per source across strata,
because a source appears in several strata), each draw re-estimating every stratum with its fixed PPI++ lambda,
then weighting. Strata with fewer than 2 labelled rows are dropped and the weights renormalised (reported).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ppi import B, SEED, load_run, ppi_lambda

GROUPS = ("transformation", "generator")


def pooled_rates(df: pd.DataFrame, mask: np.ndarray, y_col: str = "UNSAFE", f_col: str = "f",
                 group_cols=GROUPS, cluster_col: str = "source_id", alpha: float = 0.05, n_boot: int = B,
                 seed: int = SEED) -> tuple[pd.DataFrame, list[str]]:
    """(one row per estimator: classical, ppi, ppipp with est/lo/hi/width, dropped strata)."""
    df = df.reset_index(drop=True)
    lab = np.asarray(mask, dtype=bool)
    codes, _ = pd.factorize(df[cluster_col])
    k = int(codes.max()) + 1
    rng = np.random.default_rng(seed)
    w = rng.multinomial(k, np.full(k, 1.0 / k), size=n_boot).astype(float)   # (n_boot, k), shared by strata
    strata, dropped = [], []
    for key, idx in df.groupby(list(group_cols), sort=True).indices.items():
        idx = np.asarray(idx)
        m = lab[idx]
        name = "|".join(map(str, key if isinstance(key, tuple) else (key,)))
        if m.sum() < 2:
            dropped.append(f"{name} (n_all {len(idx)}, n_lab {int(m.sum())})")
            continue
        y = df.loc[idx[m], y_col].to_numpy(float)
        fl = df.loc[idx[m], f_col].to_numpy(float)
        fu = df.loc[idx[~m], f_col].to_numpy(float)
        lam_pp = ppi_lambda(y, fl, len(fu))
        cl, cu = codes[idx[m]], codes[idx[~m]]
        cols = [np.bincount(cl, minlength=k), np.bincount(cl, weights=y, minlength=k),
                np.bincount(cl, weights=fl, minlength=k), np.bincount(cu, minlength=k),
                np.bincount(cu, weights=fu, minlength=k)]
        t = w @ np.stack(cols, axis=1)            # (n_boot, 5): n_lab, sum y, sum f_lab, n_unl, sum f_unl
        strata.append({"n": len(idx), "y": y, "fl": fl, "fu": fu, "lam": {"classical": 0.0, "ppi": 1.0, "ppipp": lam_pp},
                       "t": t})
    n_tot = sum(s["n"] for s in strata)
    rows = []
    for est_name in ("classical", "ppi", "ppipp"):
        point, draws = 0.0, np.zeros(n_boot)
        for s in strata:
            lam = s["lam"][est_name] if len(s["fu"]) else 0.0
            wt = s["n"] / n_tot
            point += wt * (s["y"].mean() + (lam * (s["fu"].mean() - s["fl"].mean()) if len(s["fu"]) else 0.0))
            t = s["t"]
            with np.errstate(invalid="ignore", divide="ignore"):
                d = (t[:, 1] - lam * t[:, 2]) / t[:, 0] + (lam * t[:, 4] / t[:, 3] if len(s["fu"]) else 0.0)
            draws += wt * d
        ok = draws[np.isfinite(draws)]
        lo, hi = np.quantile(ok, [alpha / 2, 1 - alpha / 2]) if len(ok) else (np.nan, np.nan)
        rows.append({"estimator": est_name, "weighting": "stratum N_h/N", "estimate": point, "lo": float(lo),
                     "hi": float(hi), "width": float(hi - lo), "n_strata": len(strata), "n_all_used": n_tot,
                     "n_all": len(df), "n_lab": int(lab.sum()), "valid_draws": int(len(ok))})
    return pd.DataFrame(rows), dropped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--predictor", choices=("decision", "critic"), default="decision")
    ap.add_argument("--boot", type=int, default=B)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", help="default <run>/analysis/ppi_pooled.csv")
    a = ap.parse_args()
    df, mask = load_run(a.run, a.labels, a.key, None, a.predictor)
    res, dropped = pooled_rates(df, mask, n_boot=a.boot, seed=a.seed)
    print("## Stratum-weighted pooled UNSAFE rate (replaces the invalid unweighted 'all' row of ppi.csv)\n")
    print(res.to_markdown(index=False, floatfmt=".4f"))
    if dropped:
        print("\nDropped strata (< 2 labelled rows; weights renormalised): " + "; ".join(dropped))
    out = Path(a.out) if a.out else Path(a.run) / "analysis" / "ppi_pooled.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    res.assign(dropped_strata="; ".join(dropped)).to_csv(out, index=False)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
