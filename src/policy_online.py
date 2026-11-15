"""Online contextual bandit for choosing the rewrite arm, plus off-policy evaluation and a feedback logger.

  python src/policy_online.py --run data/outputs/main-v1 [--lam-cost 0.0] [--orders 200] [--cells step_bucket]
  python src/policy_online.py --synthetic [--out policy_online.csv]   # planted structure, markdown tables, no data needed

Method note (policy simulation, not a deployment): the arms, context features and reward table come from
`policy.py` (imported, not copied). Reward = SAFE_AND_USEFUL - lambda x USD, as in `policy.reward_table`.

Algorithms (all see only the chosen arm's reward, i.e. bandit feedback):
  thompson   Beta-Bernoulli Thompson sampling per discrete context cell (or per leaf of a depth<=2 tree).
             Agrawal & Goyal (2013); Chapelle & Li (2011); tutorial: Russo et al. (2018).
  linucb     disjoint LinUCB, one ridge regression per arm on the one-hot context. Li et al. (2010).
  eps_greedy per-cell epsilon-greedy baseline.   uniform: random arm.
Rewards are affinely rescaled to [0, 1] for the Beta updates (needed when lambda > 0 makes rewards negative);
regret is always reported on the original reward scale.

Replay simulator: the label table is full-information (every source has an outcome for every arm), so sources are
replayed in random arrival orders and the learner is shown only its chosen arm. Cumulative regret is reported
against the best fixed arm in hindsight and against the per-source oracle: mean and 2.5/97.5 percentiles over
orders. Regret against the best fixed arm can be negative: a contextual learner may beat every fixed arm.

Off-policy evaluation (OPE) for future logged deployments where only the chosen arm is observed, with the
logging propensity stored for each row: IPS, self-normalised IPS (Swaminathan & Joachims 2015) and doubly robust
(Dudik, Langford & Li 2011) with a per-cell, per-arm mean as the direct-method model. `check_ope` simulates a
logging policy on the full table, hides the other arms and compares each estimator with the exact value.

Feedback logger: `log_feedback(path, record)` appends one JSON line (timestamp, source_id, arm, propensity,
reward / thumbs); `load_feedback(path)` reads them back as a DataFrame. The demo writes to data/feedback/.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate import SEED, cluster_boot, md, write_analysis
from policy import BASELINE, _fill, contexts, direct_policy, encode, reward_table, synthetic

CHECKPOINTS = (25, 50, 100, 200)
ALGOS = ("thompson", "linucb", "eps_greedy", "uniform")
FEEDBACK_FIELDS = ["timestamp", "source_id", "arm", "propensity", "reward", "thumbs"]


# ------------------------------------------------------------------ contexts -> cells

def cell_codes(X: pd.DataFrame, cols: list[str] | str = "step_bucket") -> np.ndarray:
    """Integer cell id per row of X: one cell per distinct combination of the given context columns."""
    cols = [cols] if isinstance(cols, str) else list(cols)
    key = X[cols].astype(str).agg("|".join, axis=1) if cols else pd.Series("all", index=X.index)
    return pd.factorize(key)[0]


def tree_cells(policy, X: pd.DataFrame) -> np.ndarray:
    """Cell id = index of the first rule (leaf) of a `policy.Policy` that matches a row; unmatched rows get the last id.

    Fit the policy (policy.direct_policy, depth <= 2) on earlier data, not on the stream being replayed.
    """
    if not policy.rules:
        return np.zeros(len(X), dtype=int)
    E = encode(X, policy.features)
    out = np.full(len(X), len(policy.rules), dtype=int)
    done = np.zeros(len(X), dtype=bool)
    for k, r in enumerate(policy.rules):
        m = np.ones(len(X), dtype=bool)
        for f, want in r.conds:
            m &= E[f].to_numpy().astype(bool) == want
        m &= ~done
        out[m] = k
        done |= m
    return out


def to_unit(R: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Affine map of rewards to [0, 1] (a constant table maps to 0.5)."""
    lo, hi = float(np.min(R)), float(np.max(R))
    if hi - lo < 1e-12:
        return np.full_like(R, 0.5, dtype=float), lo, hi
    return (R - lo) / (hi - lo), lo, hi


# ------------------------------------------------------------------ learners

class _Base:
    """select(i) -> arm index for table row i; update(i, arm, unit_reward) with the reward rescaled to [0, 1]."""

    def __init__(self, rng: np.random.Generator, cells: np.ndarray, Z: np.ndarray, K: int):
        self.rng, self.cells, self.Z, self.K = rng, cells, Z, K
        self.nc = int(cells.max()) + 1 if len(cells) else 1

    def _argmax(self, v: np.ndarray) -> int:
        return int(np.argmax(v + 1e-12 * self.rng.random(self.K)))


class Thompson(_Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.alpha = np.ones((self.nc, self.K))
        self.beta = np.ones((self.nc, self.K))

    def select(self, i):
        c = self.cells[i]
        return self._argmax(self.rng.beta(self.alpha[c], self.beta[c]))

    def update(self, i, a, r):
        c = self.cells[i]
        self.alpha[c, a] += r
        self.beta[c, a] += 1 - r


class LinUCB(_Base):
    def __init__(self, *a, alpha: float = 0.5, ridge: float = 1.0, **k):
        super().__init__(*a, **k)
        d = self.Z.shape[1]
        self.a = alpha
        self.Ainv = np.tile(np.eye(d) / ridge, (self.K, 1, 1))
        self.b = np.zeros((self.K, d))

    def select(self, i):
        x = self.Z[i]
        theta = np.einsum("kij,kj->ki", self.Ainv, self.b)
        mean = theta @ x
        width = np.sqrt(np.maximum(np.einsum("i,kij,j->k", x, self.Ainv, x), 0.0))
        return self._argmax(mean + self.a * width)

    def update(self, i, a, r):
        x = self.Z[i]
        Ax = self.Ainv[a] @ x
        self.Ainv[a] -= np.outer(Ax, Ax) / (1.0 + x @ Ax)       # Sherman-Morrison
        self.b[a] += r * x


class EpsGreedy(_Base):
    def __init__(self, *a, eps: float = 0.1, **k):
        super().__init__(*a, **k)
        self.eps = eps
        self.n = np.zeros((self.nc, self.K))
        self.s = np.zeros((self.nc, self.K))

    def select(self, i):
        c = self.cells[i]
        untried = np.flatnonzero(self.n[c] == 0)
        if len(untried):
            return int(self.rng.choice(untried))
        if self.rng.random() < self.eps:
            return int(self.rng.integers(self.K))
        return self._argmax(self.s[c] / self.n[c])

    def update(self, i, a, r):
        c = self.cells[i]
        self.n[c, a] += 1
        self.s[c, a] += r


class Uniform(_Base):
    def select(self, i):
        return int(self.rng.integers(self.K))

    def update(self, i, a, r):
        pass


FACTORIES = {"thompson": Thompson, "linucb": LinUCB, "eps_greedy": EpsGreedy, "uniform": Uniform}


# ------------------------------------------------------------------ replay simulator

def replay(R: pd.DataFrame, X: pd.DataFrame, cells: np.ndarray | None = None, algos=ALGOS, n_orders: int = 100,
           seed: int = SEED, cell_cols: list[str] | str = "step_bucket", horizon: int | None = None,
           **params) -> dict[str, dict[str, np.ndarray]]:
    """Replay random arrival orders; return per algorithm the cumulative regret paths (n_orders x T).

    Result[algo] = {"vs_best_fixed": ..., "vs_oracle": ...}. `cells` (one id per source in R's row order after
    aligning to X) overrides `cell_cols`. Extra `params` go to the learners, e.g. eps=0.2 or alpha=1.0 (LinUCB).
    """
    Rf = _fill(R)
    Rf = Rf.loc[Rf.index.intersection(X.index)].dropna()
    Xa = X.loc[Rf.index]
    rew = Rf.to_numpy(float)
    n, K = rew.shape
    T = min(horizon or n, n)
    cells = cell_codes(Xa, cell_cols) if cells is None else np.asarray(cells)
    Z = np.column_stack([encode(Xa).to_numpy(float), np.ones(n)])
    unit, _, _ = to_unit(rew)
    best_fixed = int(np.argmax(rew.sum(axis=0)))
    oracle = rew.max(axis=1)
    orders = np.argsort(np.random.default_rng(seed).random((n_orders, n)), axis=1)[:, :T]
    out = {}
    for name in algos:
        vb = np.zeros((n_orders, T))
        vo = np.zeros((n_orders, T))
        for o in range(n_orders):
            # same stream for every algorithm; learner randomness is seeded per (algorithm, order)
            rng = np.random.default_rng([seed, o, sorted(FACTORIES).index(name)])
            kw = {k: v for k, v in params.items() if (name == "linucb" and k in ("alpha", "ridge"))
                  or (name == "eps_greedy" and k == "eps")}
            L = FACTORIES[name](rng, cells, Z, K, **kw)
            cb = co = 0.0
            for t, i in enumerate(orders[o]):
                a = L.select(i)
                L.update(i, a, unit[i, a])
                cb += rew[i, best_fixed] - rew[i, a]
                co += oracle[i] - rew[i, a]
                vb[o, t], vo[o, t] = cb, co
        out[name] = {"vs_best_fixed": vb, "vs_oracle": vo}
    out["_meta"] = {"best_fixed_arm": Rf.columns[best_fixed], "n_sources": n, "n_arms": K, "n_orders": n_orders}
    return out


def regret_table(res: dict, checkpoints=CHECKPOINTS) -> pd.DataFrame:
    """Mean and 2.5/97.5 percentile regret over orders at the checkpoints and at the horizon."""
    meta = res["_meta"]
    rows = []
    for name, d in res.items():
        if name == "_meta":
            continue
        T = d["vs_oracle"].shape[1]
        for t in sorted({c for c in checkpoints if c < T} | {T}):
            row = {"algorithm": name, "t": t}
            for key in ("vs_best_fixed", "vs_oracle"):
                v = d[key][:, t - 1]
                row.update({f"regret_{key}": v.mean(), f"{key}_lo": np.percentile(v, 2.5),
                            f"{key}_hi": np.percentile(v, 97.5)})
            rows.append({**row, "per_step_oracle": row["regret_vs_oracle"] / t,
                         "best_fixed_arm": meta["best_fixed_arm"], "n_orders": meta["n_orders"]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ off-policy evaluation

def propensities_epsilon(greedy: np.ndarray, K: int, eps: float) -> np.ndarray:
    """Matrix (n x K) of epsilon-greedy action probabilities: eps/K everywhere plus 1-eps on the greedy arm."""
    P = np.full((len(greedy), K), eps / K)
    P[np.arange(len(greedy)), greedy] += 1 - eps
    return P


def simulate_log(R: pd.DataFrame, X: pd.DataFrame, cells: np.ndarray, logging_probs: np.ndarray, n_log: int,
                 seed: int = SEED) -> pd.DataFrame:
    """Bandit log from the full table: draw sources with replacement, sample an arm from `logging_probs` (n x K,
    rows aligned to R after `_fill`/alignment with X), observe only its reward and store the propensity.

    Columns: source_id, cell, arm (name), arm_idx, propensity, reward.
    """
    Rf = _fill(R).loc[R.index.intersection(X.index)].dropna()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(Rf), n_log)
    P = logging_probs[idx]
    a = (P.cumsum(axis=1) > rng.random((n_log, 1))).argmax(axis=1)
    return pd.DataFrame({"source_id": Rf.index.to_numpy()[idx], "cell": np.asarray(cells)[idx],
                         "arm": Rf.columns.to_numpy()[a], "arm_idx": a, "propensity": P[np.arange(n_log), a],
                         "reward": Rf.to_numpy(float)[idx, a]})


def _dm_model(log: pd.DataFrame, n_cells: int, K: int) -> np.ndarray:
    """q_hat[cell, arm] = mean logged reward in the cell, falling back to the arm mean, then the global mean."""
    s = np.zeros((n_cells, K))
    c = np.zeros((n_cells, K))
    np.add.at(s, (log["cell"].to_numpy(), log["arm_idx"].to_numpy()), log["reward"].to_numpy())
    np.add.at(c, (log["cell"].to_numpy(), log["arm_idx"].to_numpy()), 1)
    arm_mean = np.where(c.sum(0) > 0, s.sum(0) / np.maximum(c.sum(0), 1), log["reward"].mean())
    return np.where(c > 0, s / np.maximum(c, 1), arm_mean[None, :])


def ope_estimates(log: pd.DataFrame, target_probs: np.ndarray, n_cells: int | None = None,
                  clip: float | None = None) -> dict[str, float]:
    """IPS, SNIPS and DR value of a target policy from a bandit log with stored propensities.

    `target_probs` is (n_cells x K): the target policy's action distribution per cell (one-hot rows for a
    deterministic policy). With w = pi(a|cell) / propensity:
      IPS   = mean(w r)                SNIPS = sum(w r) / sum(w)
      DR    = mean( sum_a pi(a) q_hat(cell, a) + w (r - q_hat(cell, arm)) )   q_hat = per-cell per-arm mean
    `clip` caps the weights (biased, lower variance; off by default).
    """
    if (log["propensity"] <= 0).any():
        raise ValueError("every logged propensity must be > 0")
    K = target_probs.shape[1]
    nc = n_cells or target_probs.shape[0]
    c, a, r, p = (log[k].to_numpy() for k in ("cell", "arm_idx", "reward", "propensity"))
    w = target_probs[c, a] / p
    if clip is not None:
        w = np.minimum(w, clip)
    q = _dm_model(log, nc, K)
    dm = (target_probs[c] * q[c]).sum(axis=1)
    return {"ips": float(np.mean(w * r)), "snips": float(np.sum(w * r) / max(np.sum(w), 1e-12)),
            "dr": float(np.mean(dm + w * (r - q[c, a]))), "dm": float(np.mean(dm)),
            "ess": float(np.sum(w) ** 2 / max(np.sum(w ** 2), 1e-12)), "n_log": len(log)}


def ope_with_ci(log: pd.DataFrame, target_probs: np.ndarray, n_boot: int = 300, seed: int = SEED,
                **kw) -> pd.DataFrame:
    """OPE estimates with 95% source-clustered bootstrap CIs (evaluate.cluster_boot), one row per estimator."""
    rows = []
    for est in ("ips", "snips", "dr"):
        pt, lo, hi = cluster_boot(log, lambda d, e=est: ope_estimates(d, target_probs, **kw)[e], b=n_boot, seed=seed)
        rows.append({"estimator": est, "estimate": pt, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def true_value(R: pd.DataFrame, X: pd.DataFrame, cells: np.ndarray, target_probs: np.ndarray) -> float:
    """Exact value of a cell-level target policy on the full table (the quantity OPE tries to recover)."""
    Rf = _fill(R).loc[R.index.intersection(X.index)].dropna()
    return float(np.mean((target_probs[np.asarray(cells)] * Rf.to_numpy(float)).sum(axis=1)))


def best_arm_per_cell(R: pd.DataFrame, X: pd.DataFrame, cells: np.ndarray) -> np.ndarray:
    """Greedy cell policy (one-hot matrix, n_cells x K): the arm with the highest mean reward in each cell."""
    Rf = _fill(R).loc[R.index.intersection(X.index)].dropna()
    M = Rf.groupby(np.asarray(cells)).mean().to_numpy()
    P = np.zeros_like(M)
    P[np.arange(len(M)), M.argmax(axis=1)] = 1.0
    return P


def check_ope(R: pd.DataFrame, X: pd.DataFrame, cells: np.ndarray | None = None, cell_cols="step_bucket",
              eps: float = 0.3, n_log: int = 5000, seed: int = SEED, logging_arm: str | None = None) -> pd.DataFrame:
    """Simulate a logging policy on the full table, hide non-chosen arms, compare each estimator with the truth.

    Logging policy: epsilon-greedy around `logging_arm` (default: the best fixed arm; propensities eps/K plus
    1-eps), every probability > 0 so the target is supported. Targets: the per-cell greedy policy and a uniform
    policy. Returns rows (target, estimator, estimate, truth, error).
    """
    Rf = _fill(R).loc[R.index.intersection(X.index)].dropna()
    Xa = X.loc[Rf.index]
    cells = cell_codes(Xa, cell_cols) if cells is None else np.asarray(cells)
    K = Rf.shape[1]
    base = list(Rf.columns).index(logging_arm) if logging_arm else int(Rf.mean().to_numpy().argmax())
    log = simulate_log(Rf, Xa, cells, propensities_epsilon(np.full(len(Rf), base), K, eps), n_log, seed)
    nc = int(cells.max()) + 1
    targets = {"greedy_per_cell": best_arm_per_cell(Rf, Xa, cells), "uniform": np.full((nc, K), 1.0 / K)}
    rows = []
    for tname, tp in targets.items():
        truth = true_value(Rf, Xa, cells, tp)
        for est, v in ope_estimates(log, tp, nc).items():
            if est in ("ips", "snips", "dr", "dm"):
                rows.append({"target": tname, "estimator": est, "estimate": v, "truth": truth, "error": v - truth})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ feedback logger

def log_feedback(path: str | Path, record: dict) -> dict:
    """Append one feedback record as a JSON line and return it (with a timestamp filled in if missing).

    Fields: timestamp, source_id, arm, propensity (probability with which the arm was shown; None when a person
    chose it, so such rows cannot be used for IPS), reward (0/1 or float) and/or thumbs ("up"/"down"/+1/-1).
    """
    rec = {k: record.get(k) for k in FEEDBACK_FIELDS}
    rec.update({k: v for k, v in record.items() if k not in FEEDBACK_FIELDS})
    rec["timestamp"] = rec["timestamp"] or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if rec["propensity"] is not None and not rec["propensity"] > 0:
        raise ValueError("propensity must be > 0 when given")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")
    return rec


def load_feedback(path: str | Path) -> pd.DataFrame:
    """Read a feedback JSONL into a DataFrame (empty frame with the standard columns if the file is missing).
    A `reward` column is derived from thumbs where reward is missing (up -> 1, down -> 0)."""
    p = Path(path)
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()] if p.exists() else []
    df = pd.DataFrame(rows, columns=None if rows else FEEDBACK_FIELDS)
    for c in FEEDBACK_FIELDS:
        if c not in df:
            df[c] = None
    thumbs = df["thumbs"].map({"up": 1.0, "down": 0.0, 1: 1.0, -1: 0.0, "1": 1.0, "-1": 0.0})
    df["reward"] = pd.to_numeric(df["reward"], errors="coerce").fillna(thumbs)
    return df


# ------------------------------------------------------------------ cli

def _report(R: pd.DataFrame, X: pd.DataFrame, cell_cols, n_orders: int, lam: float) -> dict[str, pd.DataFrame]:
    print(f"## Online policy simulation: {len(R)} sources, {R.shape[1]} arms, lambda={lam}, cells={cell_cols}\n")
    print("Policy simulation on a full-information table; not evidence about a live deployment.\n")
    res = replay(R, X, n_orders=n_orders, cell_cols=cell_cols)
    reg = regret_table(res)
    print("### Cumulative regret (mean and 2.5/97.5 percentile over random arrival orders)\n")
    print(md(reg[["algorithm", "t", "regret_vs_best_fixed", "vs_best_fixed_lo", "vs_best_fixed_hi",
                  "regret_vs_oracle", "vs_oracle_lo", "vs_oracle_hi"]]), "\n")
    ope = check_ope(R, X, cell_cols=cell_cols)
    print("### OPE check (hidden non-chosen arms; epsilon-greedy logging policy)\n")
    print(md(ope), "\n")
    return {"policy_online": reg, "policy_online_ope": ope}


def main() -> None:
    from common import ROOT
    from evaluate import load_source_rows, prepare
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--lam-cost", type=float, default=0.0, help="reward = outcome - lam_cost x USD")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--orders", type=int, default=100)
    ap.add_argument("--cells", nargs="+", default=None, help="context columns that define a cell")
    ap.add_argument("--out", help="regret CSV path when not using --run")
    args = ap.parse_args()
    if not args.synthetic and not args.run:
        ap.error("give --run or --synthetic")
    if args.synthetic:
        R, X, _ = synthetic(400)
        tables = _report(R, X, args.cells or ["length", "comparison"], args.orders, args.lam_cost)
        if args.out:
            p = Path(args.out)
            write_analysis(p.parent, p.stem, tables["policy_online"])
            write_analysis(p.parent, p.stem + "_ope", tables["policy_online_ope"])
        return
    run = Path(args.run)
    ann = ROOT / "data" / "annotations" / run.name
    key_path = args.key or ann / "KEY_DO_NOT_OPEN.csv"
    labels = prepare(args.labels or ann / "adjudicated.csv", key_path)
    key = pd.read_csv(key_path)
    R = reward_table(labels, key, {}, args.lam_cost)
    src = load_source_rows()
    X = contexts([src[s] for s in R.index if s in src])
    tables = _report(R.loc[X.index], X, args.cells or ["step_bucket"], args.orders, args.lam_cost)
    for name, df in tables.items():
        print(f"written: {write_analysis(run / 'analysis', name, df)}")


if __name__ == "__main__":
    main()
