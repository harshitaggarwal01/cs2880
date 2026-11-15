"""Stackelberg audit game: where should a limited budget of manual audits go? (POLICY SIMULATION)

  python src/audit_game.py --synthetic [--budget 0.1] [--out audit_game.csv]
  python src/audit_game.py --run data/outputs/main-v1 [--rates <run>/analysis/ppi.csv] [--budget 0.1]
                           [--budget-mode items|targets] [--detect 1.0]

THIS IS A POLICY SIMULATION. Vendors and tools do not currently respond strategically to audits, and the unsafe
rates come from one study; the game shows how an audit budget should be spread if some provider were careless
about where it cuts corners, and how much that is worth compared with simple rules. It is not a prediction.

Model. Targets t = (tool or generator) x condition cells with an estimated unsafe rate p_t (point estimate and CI
[lo_t, hi_t], e.g. from ppi.csv or evaluate output) and a volume v_t (items per period). The defender picks audit
coverage c_t in [0, 1] with sum_t c_t v_t <= B (budget_mode "items") or sum_t c_t <= B ("targets"). An audited
unsafe item is caught with probability `detect` (default 1) and does not reach a student, so the expected number
of unsafe items reaching students at t is  L_t(c) = v_t p_t (1 - detect c_t).  The attacker (a careless or
cost-cutting vendor, or the worst-case target) picks one target; it gains g_t L_t, the defender loses h_t L_t
(harm weights h; with g = h the game is zero-sum). Reported per 1,000 items: 1000 L_t / sum_t v_t.

Solvers.
  solve_sse     Strong Stackelberg Equilibrium by the multiple-LPs method (Conitzer & Sandholm 2006): one LP per
                attacker target t*, maximise the defender's utility subject to t* being a best response (ties
                broken in the defender's favour); keep the best feasible LP. Compact security-game formulation:
                Kiekintveld et al. (2009); overview: Tambe (2011).
  solve_robust  max-min over the box of rates [lo, hi] (Kiekintveld, Islam & Kreinovich 2013, interval
                uncertainty): minimise z such that h_t v_t hi_t (1 - detect c_t) <= z for every target, which is
                the worst case over the attacker's choice and over nature's rate within the box.
Baselines at the same budget: `uniform` (equal coverage) and `proportional` (coverage proportional to the rate,
capped at 1). Audit games in the strict sense, with punishments and a defender who commits to an inspection
policy: Blocki, Christin, Datta, Procaccia & Sinha (2013); here the audit only removes unsafe items.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from evaluate import SEED, md, write_analysis

TOL = 1e-9


@dataclass
class Game:
    names: list[str]
    p: np.ndarray                 # nominal unsafe rate per target
    lo: np.ndarray
    hi: np.ndarray
    volume: np.ndarray            # items per period
    harm: np.ndarray = field(default=None)    # defender's loss weight h_t
    gain: np.ndarray = field(default=None)    # attacker's gain weight g_t
    detect: float = 1.0
    budget_mode: str = "items"    # "items": sum c v <= B ; "targets": sum c <= B

    def __post_init__(self):
        n = len(self.names)
        self.p, self.lo, self.hi, self.volume = (np.asarray(a, float) for a in (self.p, self.lo, self.hi, self.volume))
        self.harm = np.ones(n) if self.harm is None else np.asarray(self.harm, float)
        self.gain = self.harm.copy() if self.gain is None else np.asarray(self.gain, float)
        if self.budget_mode not in ("items", "targets"):
            raise ValueError("budget_mode must be 'items' or 'targets'")
        if not (np.all(self.lo <= self.p + TOL) and np.all(self.p <= self.hi + TOL)):
            raise ValueError("need lo <= p <= hi for every target")

    @property
    def n(self) -> int:
        return len(self.names)

    @property
    def weight(self) -> np.ndarray:
        """Cost of one unit of coverage at each target in the budget constraint."""
        return self.volume if self.budget_mode == "items" else np.ones(self.n)

    @property
    def full_budget(self) -> float:
        return float(self.weight.sum())

    def loss(self, c: np.ndarray, rates: np.ndarray | None = None) -> np.ndarray:
        """Expected unsafe items reaching students per target, L_t(c)."""
        r = self.p if rates is None else rates
        return self.volume * r * (1.0 - self.detect * np.asarray(c, float))


# ------------------------------------------------------------------ input builders

def build_game(rates: pd.DataFrame, group_cols: list[str] | None = None, rate_col: str | None = None,
               lo_col: str | None = None, hi_col: str | None = None, volume_col: str | None = None,
               harm: dict | None = None, detect: float = 1.0, budget_mode: str = "items") -> Game:
    """Game from a rates table with columns group (or `group_cols`), rate, lo, hi, n (volume).

    Column names default to rate/lo/hi, falling back to ppi.csv's `ppipp`/`ppipp_lo`/`ppipp_hi` and then `ppi`.
    Volume defaults to column `volume`, else `n`, else `n_all`, else 1. Rates and CI ends are clipped to [0, 1]
    and ordered so that lo <= rate <= hi. `harm` maps group name -> weight (default 1).
    """
    d = rates.reset_index(drop=True)
    if rate_col is None:
        rate_col = next((c for c in ("rate", "ppipp", "ppi", "classical") if c in d), None)
    if rate_col is None:
        raise ValueError("no rate column found (give rate_col)")
    lo_col = lo_col or (f"{rate_col}_lo" if f"{rate_col}_lo" in d else "lo")
    hi_col = hi_col or (f"{rate_col}_hi" if f"{rate_col}_hi" in d else "hi")
    if "group" in d:
        names = d["group"].astype(str).tolist()
    else:
        gc = group_cols or [c for c in ("transformation", "generator", "model") if c in d]
        names = d[gc].astype(str).agg(" / ".join, axis=1).tolist() if gc else [f"t{i}" for i in range(len(d))]
    vol_col = volume_col or next((c for c in ("volume", "n", "n_all") if c in d), None)
    vol = d[vol_col].to_numpy(float) if vol_col else np.ones(len(d))
    p = d[rate_col].to_numpy(float)
    ok = ~np.isnan(p)
    lo = np.where(np.isnan(d[lo_col].to_numpy(float)), p, d[lo_col].to_numpy(float)) if lo_col in d else p
    hi = np.where(np.isnan(d[hi_col].to_numpy(float)), p, d[hi_col].to_numpy(float)) if hi_col in d else p
    p, lo, hi = (np.clip(a, 0, 1) for a in (p, lo, hi))
    lo, hi = np.minimum(lo, p), np.maximum(hi, p)
    h = np.array([(harm or {}).get(nm, 1.0) for nm in names])
    keep = np.flatnonzero(ok)
    return Game([names[i] for i in keep], p[keep], lo[keep], hi[keep], vol[keep], h[keep], None, detect, budget_mode)


def synthetic_game(n_tools: int = 4, conditions=("plain", "chunked"), seed: int = 0, detect: float = 1.0,
                   budget_mode: str = "items") -> Game:
    """Planted game: tools x conditions with unsafe rates 0.02-0.35, CI half-widths shrinking with volume."""
    rng = np.random.default_rng(seed)
    names, p, lo, hi, vol = [], [], [], [], []
    for i in range(n_tools):
        for cnd in conditions:
            rate = float(rng.uniform(0.02, 0.35))
            v = float(rng.integers(200, 2000))
            half = 1.96 * np.sqrt(rate * (1 - rate) / max(v / 10, 1))      # roughly a 10% labelled subsample
            names.append(f"tool{i}/{cnd}")
            p.append(rate)
            lo.append(max(rate - half, 0.0))
            hi.append(min(rate + half, 1.0))
            vol.append(v)
    return Game(names, np.array(p), np.array(lo), np.array(hi), np.array(vol), detect=detect, budget_mode=budget_mode)


# ------------------------------------------------------------------ solvers

def _budget_row(g: Game, nvar: int) -> np.ndarray:
    row = np.zeros(nvar)
    row[:g.n] = g.weight
    return row


def solve_sse(g: Game, budget: float) -> dict:
    """Strong Stackelberg Equilibrium by multiple LPs (Conitzer & Sandholm 2006).

    For each target k the LP maximises the defender's utility -h_k L_k(c) over coverage c with 0 <= c <= 1,
    budget, and attacker best-response constraints g_k L_k(c) >= g_t L_t(c) for all t. The best feasible LP is the
    SSE; the attacker breaks ties for the defender. Returns dict(c, target, defender_utility, attacker_utility).
    """
    n = g.n
    a = g.gain * g.volume * g.p * g.detect          # attacker utility slope: U_a(t) = g v p - a_t c_t
    base = g.gain * g.volume * g.p
    best = None
    for k in range(n):
        cost = np.zeros(n)
        cost[k] = -g.harm[k] * g.volume[k] * g.p[k] * g.detect      # maximise defender utility = -h L_k
        A, b = [g.weight], [budget]
        for t in range(n):
            if t == k:
                continue
            row = np.zeros(n)
            row[k] += a[k]                                        # base_t - a_t c_t <= base_k - a_k c_k
            row[t] -= a[t]
            A.append(row)
            b.append(base[k] - base[t])
        res = linprog(cost, A_ub=np.array(A), b_ub=np.array(b), bounds=[(0, 1)] * n, method="highs")
        if res.status != 0:
            continue
        c = np.clip(res.x, 0, 1)
        ud = -float(g.harm[k] * g.loss(c)[k])
        if best is None or ud > best["defender_utility"] + 1e-12:
            best = {"c": c, "target": k, "defender_utility": ud,
                    "attacker_utility": float(g.gain[k] * g.loss(c)[k])}
    if best is None:                                            # numerical fallback: no coverage is always feasible
        c = np.zeros(n)
        return _response(g, c)
    return best


def solve_robust(g: Game, budget: float, rates: str = "hi") -> dict:
    """Max-min allocation over the rate box [lo, hi]: minimise z s.t. h_t v_t r_t (1 - detect c_t) <= z for all t.

    With harm weights as the loss, nature's worst case is r = hi (rates="hi"); the objective is therefore the
    worst loss over every target and every rate in the box. Returns dict(c, worst_case_loss).
    """
    r = {"hi": g.hi, "point": g.p, "lo": g.lo}[rates]
    n = g.n
    cost = np.zeros(n + 1)
    cost[n] = 1.0
    A, b = [np.append(g.weight, 0.0)], [budget]
    for t in range(n):
        row = np.zeros(n + 1)
        row[t] = -g.harm[t] * g.volume[t] * r[t] * g.detect
        row[n] = -1.0
        A.append(row)
        b.append(-g.harm[t] * g.volume[t] * r[t])
    res = linprog(cost, A_ub=np.array(A), b_ub=np.array(b), bounds=[(0, 1)] * n + [(0, None)], method="highs")
    if res.status != 0:
        raise RuntimeError(f"robust LP failed: {res.message}")
    c = np.clip(res.x[:n], 0, 1)
    return {"c": c, "worst_case_loss": float(res.x[n])}


def uniform_allocation(g: Game, budget: float) -> np.ndarray:
    return np.full(g.n, min(1.0, budget / g.full_budget))


def proportional_allocation(g: Game, budget: float) -> np.ndarray:
    """Coverage c_t = min(1, s p_t), the scale s found by bisection so the budget is spent (or all is covered)."""
    if budget >= g.full_budget - TOL:
        return np.ones(g.n)
    if g.p.sum() <= 0:
        return uniform_allocation(g, budget)
    lo, hi = 0.0, 1.0 / max(g.p[g.p > 0].min(), 1e-12)
    for _ in range(100):
        s = (lo + hi) / 2
        if (g.weight * np.minimum(1.0, s * g.p)).sum() > budget:
            hi = s
        else:
            lo = s
    return np.minimum(1.0, lo * g.p)


# ------------------------------------------------------------------ evaluation

def _response(g: Game, c: np.ndarray, rates: np.ndarray | None = None) -> dict:
    """Attacker best response to coverage c (ties to the defender), with the resulting utilities."""
    L = g.loss(c, rates)
    ua = g.gain * L
    cand = np.flatnonzero(ua >= ua.max() - TOL * max(1.0, abs(ua.max())))
    k = int(cand[np.argmin(g.harm[cand] * L[cand])])
    return {"c": np.asarray(c, float), "target": k, "defender_utility": -float(g.harm[k] * L[k]),
            "attacker_utility": float(ua[k])}


def evaluate_allocation(g: Game, c: np.ndarray) -> dict:
    """Loss under the attacker's best response (nominal rates), and worst case over any target at the hi rates.

    unsafe_per_1000 = 1000 x (unsafe items reaching students at the attacked target) / (total volume).
    Also checks budget feasibility.
    """
    r = _response(g, c)
    k = r["target"]
    total = float(g.volume.sum())
    worst = float((g.harm * g.loss(c, g.hi)).max())
    return {"attacked": g.names[k], "defender_loss": -r["defender_utility"],
            "unsafe_per_1000": 1000 * float(g.loss(c)[k]) / total,
            "worst_case_loss": worst, "worst_case_per_1000": 1000 * worst / total,
            "budget_used": float((g.weight * c).sum())}


def compare(g: Game, budgets: list[float]) -> pd.DataFrame:
    """Methods x budgets: SSE, robust, uniform, proportional, and no audits (budget 0 reference)."""
    rows = []
    for B in budgets:
        allocs = {"sse": solve_sse(g, B)["c"], "robust": solve_robust(g, B)["c"],
                  "uniform": uniform_allocation(g, B), "proportional": proportional_allocation(g, B)}
        for m, c in allocs.items():
            rows.append({"budget": B, "budget_frac": B / g.full_budget, "method": m, **evaluate_allocation(g, c)})
    return pd.DataFrame(rows)


def coverage_table(g: Game, budget: float) -> pd.DataFrame:
    sse, rob = solve_sse(g, budget)["c"], solve_robust(g, budget)["c"]
    return pd.DataFrame({"target": g.names, "rate": g.p, "lo": g.lo, "hi": g.hi, "volume": g.volume,
                         "c_sse": sse, "c_robust": rob, "c_uniform": uniform_allocation(g, budget),
                         "c_proportional": proportional_allocation(g, budget)})


# ------------------------------------------------------------------ cli

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--rates", help="rates CSV (default <run>/analysis/ppi.csv)")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--budget", type=float, default=0.1, help="fraction of the full audit budget (all items)")
    ap.add_argument("--budget-mode", choices=["items", "targets"], default="items")
    ap.add_argument("--detect", type=float, default=1.0)
    ap.add_argument("--out", help="CSV path when not using --run")
    args = ap.parse_args()
    if not args.synthetic and not args.run:
        ap.error("give --run or --synthetic")
    if args.synthetic:
        g = synthetic_game(detect=args.detect, budget_mode=args.budget_mode)
    else:
        path = Path(args.rates) if args.rates else Path(args.run) / "analysis" / "ppi.csv"
        g = build_game(pd.read_csv(path), detect=args.detect, budget_mode=args.budget_mode)
    B = args.budget * g.full_budget
    fracs = sorted({0.0, 0.05, 0.1, 0.2, 0.4, 1.0, args.budget})
    cmp_ = compare(g, [f * g.full_budget for f in fracs])
    print(f"## Audit game (policy simulation): {g.n} targets, budget {args.budget:.0%} of full ({g.budget_mode})\n")
    print(md(coverage_table(g, B)), "\n")
    print("### Expected unsafe items per 1,000 reaching students (attacker best response), by method and budget\n")
    print(md(cmp_[["budget_frac", "method", "attacked", "unsafe_per_1000", "worst_case_per_1000"]]), "\n")
    if args.run:
        print(f"written: {write_analysis(Path(args.run) / 'analysis', 'audit_game', cmp_)}")
    elif args.out:
        p = Path(args.out)
        print(f"written: {write_analysis(p.parent, p.stem, cmp_)}")


if __name__ == "__main__":
    main()
