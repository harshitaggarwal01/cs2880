"""Offline contextual-bandit policy: which adaptation arm should we use for which kind of problem?

  python src/policy.py --run data/outputs/main-v1 [--labels adjudicated.csv --key KEY_DO_NOT_OPEN.csv]
                       [--ledger ledger.csv] [--lam-cost 0.0] [--out <run>/analysis/policy.csv]
  python src/policy.py --synthetic --out policy_synth.csv      # planted structure, no data needed

Arms: the deterministic chunking baseline, `generator:transformation` for each LLM generator x {plain, chunked},
and `generator:transformation+repair` where a repair exists. Reward = SAFE_AND_USEFUL - lam_cost x USD.
Context = the seven surface tags, step bucket, length tercile (words) and number-of-quantities bucket.

Every arm is observed for every source (full-information logs), so the direct method is exact: the value of any
policy is the mean of the reward table at the arms it picks, with no propensity weighting and no model of the
reward (Li et al. 2010; Dudik, Langford & Li 2011). Learned policies are evaluated by K-fold cross-validation
over sources (the source is the exchangeable unit) and compared with always-AI and never-AI baselines, with
source-level bootstrap CIs. A Thompson-sampling replay shows what a live deployment would cost in regret.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from common import ROOT, count_quantities, step_bucket, tags
from evaluate import BASELINE, SEED, load_source_rows, md, prepare

TAG_COLS = ["percent", "fraction", "comparison", "money", "time", "measure", "conditional"]
CAT_COLS = ["step_bucket", "length", "n_quantities"]
LENGTHS = ["len_low", "len_mid", "len_high"]
STEP_LEVELS = ["s<=2", "s=3", "s=4", "s>=5", "unknown"]
QUANT_LEVELS = ["q<=2", "q3-4", "q>=5"]
CHECKPOINTS = (25, 50, 100)


# ------------------------------------------------------------------ context

def _quant_bucket(n: int) -> str:
    return "q<=2" if n <= 2 else ("q>=5" if n >= 5 else "q3-4")


def contexts(sources: list[dict]) -> pd.DataFrame:
    """Context features per source, indexed by source_id.

    Columns: the seven boolean tags from common.tags, `step_bucket` ("unknown" when n_steps is missing),
    `length` (tercile of word count within the given sources: len_low/len_mid/len_high), `n_quantities` bucket.
    """
    rows = []
    for s in sources:
        text = s["text"]
        n = s.get("n_steps")
        known = n is not None and not pd.isna(n)
        rows.append({"source_id": s["source_id"], **tags(text),
                     "step_bucket": step_bucket(int(n)) if known else "unknown",
                     "words": len(text.split()),
                     "n_quantities": _quant_bucket(count_quantities(text))})
    X = pd.DataFrame(rows).set_index("source_id")
    # rank first so ties in word count cannot collapse a tercile
    X["length"] = pd.qcut(X["words"].rank(method="first"), 3, labels=LENGTHS).astype(str)
    return X.drop(columns="words")[TAG_COLS + CAT_COLS]


def encode(X: pd.DataFrame, names: list[str] | None = None) -> pd.DataFrame:
    """0/1 design matrix: tags as-is, categorical features one-hot as `feature=level`."""
    cols = {t: X[t].astype(int) for t in TAG_COLS}
    for c, levels in zip(CAT_COLS, (STEP_LEVELS, LENGTHS, QUANT_LEVELS)):
        for lv in levels:
            cols[f"{c}={lv}"] = (X[c] == lv).astype(int)
    E = pd.DataFrame(cols, index=X.index)
    return E if names is None else E.reindex(columns=names, fill_value=0)


# ------------------------------------------------------------------ reward table

def _norm_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().eq("true")


def reward_table(labels_df: pd.DataFrame, key_df: pd.DataFrame, per_item_cost: dict | None = None,
                 lam_cost: float = 0.0, outcome: str = "SAFE_AND_USEFUL") -> pd.DataFrame:
    """Rows = source_id, columns = arms, values = outcome - lam_cost x USD (NaN if the arm is missing).

    `labels_df` carries output_id and the outcome column; `key_df` maps output_id to source_id, generator,
    transformation, is_repair and repair_of. The deterministic baseline (generator "deterministic") is the arm
    "deterministic"; others are f"{generator}:{transformation}". For every (generator, transformation) with at least
    one repair, an extra arm "<arm>+repair" takes the repaired item's outcome where a repair exists and the
    original's otherwise; its cost is original plus repair cost. Missing cost entries count as 0.
    """
    cost = per_item_cost or {}
    k = key_df.copy()
    k["is_repair"] = _norm_bool(k["is_repair"]) if "is_repair" in k else False
    lab = labels_df[["output_id", outcome]].groupby("output_id", as_index=False)[outcome].mean()
    d = k.merge(lab, on="output_id", how="inner")
    d["arm"] = np.where(d["generator"] == BASELINE, BASELINE, d["generator"] + ":" + d["transformation"].astype(str))
    d["usd"] = d["output_id"].map(lambda o: float(cost.get(o, 0.0)))
    d["reward"] = d[outcome] - lam_cost * d["usd"]

    prim = d[~d["is_repair"]]
    R = prim.pivot_table(index="source_id", columns="arm", values="reward", aggfunc="mean")
    rep = d[d["is_repair"]]
    for arm, g in rep.groupby("arm"):
        g = g.sort_values("output_id").drop_duplicates(["source_id", "repair_of"], keep="last")
        g = g.drop_duplicates("source_id", keep="last").set_index("source_id")
        orig_usd = g["repair_of"].map(lambda o: float(cost.get(o, 0.0)))
        col = R[arm].copy() if arm in R else pd.Series(np.nan, index=R.index)
        col = col.reindex(R.index.union(g.index))
        col.loc[g.index] = g[outcome] - lam_cost * (g["usd"] + orig_usd)
        R = R.reindex(col.index)
        R[f"{arm}+repair"] = col
    arms = sorted(R.columns, key=lambda a: (a != BASELINE, a))
    return R[arms].sort_index()


def _fill(R: pd.DataFrame) -> pd.DataFrame:
    """NaN arm rewards fall back to the deterministic arm (first column when there is none)."""
    base = R[BASELINE] if BASELINE in R else R.iloc[:, 0]
    return R.apply(lambda c: c.fillna(base))


def _arm_order(arms: list[str], arm_cost: dict | None = None) -> list[str]:
    """Tie-break order: deterministic first, then cheaper, then column order."""
    cost = arm_cost or {}
    return sorted(arms, key=lambda a: (a != BASELINE, cost.get(a, 0.0), arms.index(a)))


def _argmax_arm(vals: pd.DataFrame | pd.Series, order: list[str]):
    """First arm in tie-break order attaining the maximum (works for a frame row-wise or a series)."""
    if isinstance(vals, pd.Series):
        v = vals[order]
        return order[int(np.argmax(v.to_numpy()))]
    v = vals[order].to_numpy()
    return pd.Series([order[i] for i in v.argmax(axis=1)], index=vals.index)


# ------------------------------------------------------------------ policy

@dataclass
class Rule:
    conds: tuple          # ((feature, wanted_bool), ...); all must hold
    arm: str
    n: int = 0
    mean_reward: float = float("nan")


@dataclass
class Policy:
    """Context -> arm. `rules` are disjoint leaves of a shallow tree; `default` covers anything unmatched."""
    default: str
    rules: list[Rule] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    name: str = "learned"

    def assign(self, X: pd.DataFrame) -> pd.Series:
        """Arm chosen for each row of X (a `contexts` frame)."""
        out = pd.Series(self.default, index=X.index, dtype=object)
        if not self.rules:
            return out
        E = encode(X, self.features)
        done = pd.Series(False, index=X.index)
        for r in self.rules:
            m = pd.Series(True, index=X.index)
            for f, want in r.conds:
                m &= E[f].astype(bool) == want
            m &= ~done
            out[m] = r.arm
            done |= m
        return out

    def describe(self) -> str:
        if not self.rules:
            return f"ALWAYS use {self.default}"
        lines = []
        for r in self.rules:
            cond = " AND ".join(f if want else f"NOT {f}" for f, want in r.conds) or "(everything)"
            lines.append(f"IF {cond}: use {r.arm}   [n={r.n}, mean reward {r.mean_reward:.3f}]")
        lines.append(f"OTHERWISE: use {self.default}")
        return "\n".join(lines)


def fixed_policy(arm: str) -> Policy:
    return Policy(default=arm, name=f"always {arm}")


def direct_policy(R: pd.DataFrame, X: pd.DataFrame, depth: int = 2, min_leaf: int = 8,
                  arm_cost: dict | None = None) -> Policy:
    """Shallow-tree policy from full-information rewards (direct method).

    A DecisionTreeClassifier(max_depth=depth, min_samples_leaf=min_leaf) is fit on the context to predict each
    source's best arm (ties go to deterministic, then the cheaper arm). Each leaf then plays the arm with the
    highest mean reward over its training sources, which is the exact direct-method value-maximiser for that cell.
    """
    Rf = _fill(R).loc[X.index.intersection(R.index)].dropna(how="all")
    Rf = Rf.dropna(subset=[BASELINE] if BASELINE in Rf else None)
    X = X.loc[Rf.index]
    order = _arm_order(list(R.columns), arm_cost)
    best = _argmax_arm(Rf, order)
    default = _argmax_arm(Rf.mean(), order)
    E = encode(X)
    if best.nunique() < 2 or depth < 1 or len(Rf) < 2 * min_leaf:
        return Policy(default=default, name="learned")
    tree = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=min_leaf, random_state=0).fit(E, best)
    t = tree.tree_
    leaf_of = pd.Series(tree.apply(E), index=E.index)
    rules: list[Rule] = []

    def walk(node: int, conds: tuple) -> None:
        if t.children_left[node] == -1:
            ids = leaf_of.index[leaf_of == node]
            means = Rf.loc[ids].mean()
            arm = _argmax_arm(means, order)
            rules.append(Rule(conds, arm, len(ids), float(means[arm])))
            return
        f = E.columns[t.feature[node]]
        walk(t.children_left[node], conds + ((f, False),))     # feature <= 0.5
        walk(t.children_right[node], conds + ((f, True),))

    walk(0, ())
    return Policy(default=default, rules=rules, features=list(E.columns), name="learned")


def value(policy: Policy, R: pd.DataFrame, X: pd.DataFrame) -> float:
    """Mean reward of the arms `policy` picks (exact in full-information logs). Missing arms use deterministic."""
    Rf = _fill(R)
    ids = X.index.intersection(Rf.index)
    return float(np.nanmean(_chosen(policy, Rf, X.loc[ids])))


def _chosen(policy: Policy, Rf: pd.DataFrame, X: pd.DataFrame) -> np.ndarray:
    arms = policy.assign(X)
    base = Rf[BASELINE] if BASELINE in Rf else Rf.iloc[:, 0]
    arms = arms.where(arms.isin(Rf.columns), base.name)
    idx = Rf.columns.get_indexer(arms)
    return Rf.loc[X.index].to_numpy()[np.arange(len(X)), idx]


# ------------------------------------------------------------------ leave-source-out evaluation

METHODS = ["learned", "best_single", "always_ai", "never_ai"]


def cv_rewards(R: pd.DataFrame, X: pd.DataFrame, depth: int = 2, min_leaf: int = 8, folds: int | None = 10,
               seed: int = SEED) -> pd.DataFrame:
    """Held-out reward per source for the learned policy and the three comparators.

    Sources are split into `folds` groups (None = leave-one-source-out). Everything chosen from data (tree, best
    single arm, best LLM arm) is fit on the training sources only. Columns: learned, best_single, always_ai,
    never_ai.
    """
    Rf = _fill(R)
    Rf = Rf.loc[Rf[BASELINE].notna()] if BASELINE in Rf else Rf
    ids = np.array(Rf.index.intersection(X.index))
    Rf, X = Rf.loc[ids], X.loc[ids]
    n = len(ids)
    k = n if folds is None or folds >= n else folds
    perm = np.random.default_rng(seed).permutation(n)
    llm = [a for a in Rf.columns if a != BASELINE]
    out = pd.DataFrame(index=ids, columns=METHODS, dtype=float)
    for part in np.array_split(perm, k):
        test = ids[part]
        train = ids[np.setdiff1d(np.arange(n), part)]
        means = Rf.loc[train].mean()
        pol = direct_policy(Rf.loc[train], X.loc[train], depth, min_leaf)
        out.loc[test, "learned"] = _chosen(pol, Rf, X.loc[test])
        out.loc[test, "best_single"] = Rf.loc[test, means.idxmax()].to_numpy()
        if llm:
            out.loc[test, "always_ai"] = Rf.loc[test, means[llm].idxmax()].to_numpy()
        out.loc[test, "never_ai"] = Rf.loc[test, BASELINE if BASELINE in Rf else Rf.columns[0]].to_numpy()
    return out


def leave_source_out(R: pd.DataFrame, X: pd.DataFrame, depth: int = 2, n_boot: int = 1000, seed: int = SEED,
                     min_leaf: int = 8, folds: int | None = 10) -> pd.DataFrame:
    """Cross-validated value of the learned policy vs best-single-arm, always-AI and never-AI.

    Because every arm is observed for every source, the direct method is exact: a policy's value on held-out
    sources is just the mean reward of the arms it picks there, so no propensity weighting or reward model is
    involved. Selection (tree, best single arm, best LLM arm) happens on training folds only; the source is the
    resampling unit for the 95% percentile bootstrap CIs, applied to values and to paired differences.
    Reference rows give the in-sample value of the tree fit on all sources (optimistic) and the per-source oracle.
    """
    H = cv_rewards(R, X, depth, min_leaf, folds, seed)
    Rf = _fill(R).loc[H.index]
    full = direct_policy(Rf, X.loc[H.index], depth, min_leaf)
    cols = {f"value: {m}": H[m] for m in METHODS}
    cols["reference: learned in-sample"] = pd.Series(_chosen(full, Rf, X.loc[H.index]), index=H.index)
    cols["reference: oracle per-source max"] = Rf.max(axis=1)
    for a, b in (("learned", "best_single"), ("learned", "always_ai"), ("learned", "never_ai"),
                 ("always_ai", "never_ai"), ("best_single", "never_ai")):
        cols[f"diff: {a} - {b}"] = H[a] - H[b]
    M = pd.DataFrame(cols)
    rng = np.random.default_rng(seed)
    arr = M.to_numpy()
    take = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    boots = np.nanmean(arr[take], axis=1)
    lo, hi = np.nanpercentile(boots, [2.5, 97.5], axis=0)
    res = pd.DataFrame({"kind": [c.split(": ")[0] for c in M], "name": [c.split(": ")[1] for c in M],
                        "estimate": np.nanmean(arr, axis=0), "ci_lo": lo, "ci_hi": hi, "n_sources": len(arr)})
    res.attrs["folds"] = folds
    return res


# ------------------------------------------------------------------ Thompson sampling replay

def thompson_replay(R: pd.DataFrame, X: pd.DataFrame, n_orders: int = 500, seed: int = SEED,
                    context_key: str | None = "step_bucket") -> pd.DataFrame:
    """Beta-Bernoulli Thompson sampling per context bucket, replayed over random source orders.

    Sources arrive one at a time in a random order; for the source's bucket we draw theta_a ~ Beta(alpha, beta)
    for each arm, play the argmax and observe only that arm's reward (bandit feedback, even though our logs
    hold all arms). Use the SAFE_AND_USEFUL table with lam_cost = 0: rewards must lie in [0, 1] (fractional values
    update the Beta as pseudo-counts). Regret is realised regret against the best fixed arm in hindsight (highest
    total reward over all sources). Reports mean and 2.5/97.5 percentiles over orders at t = 25, 50, 100 and all.
    Beta-Bernoulli Thompson sampling: Agrawal & Goyal (2013, AISTATS); empirical behaviour: Chapelle & Li (2011).
    """
    Rf = _fill(R)
    Rf = Rf.loc[Rf.index.intersection(X.index)].dropna()
    if Rf.to_numpy().min() < 0 or Rf.to_numpy().max() > 1:
        raise ValueError("thompson_replay needs rewards in [0, 1]; use SAFE_AND_USEFUL with lam_cost=0")
    n, m = Rf.shape
    bucket = (X.loc[Rf.index, context_key].astype(str) if context_key else pd.Series("all", index=Rf.index))
    codes, _ = pd.factorize(bucket)
    nb = codes.max() + 1
    rew = Rf.to_numpy()
    best_arm = int(np.argmax(rew.sum(axis=0)))
    rng = np.random.default_rng(seed)
    orders = np.argsort(rng.random((n_orders, n)), axis=1)
    alpha = np.ones((n_orders, nb, m))
    beta = np.ones((n_orders, nb, m))
    rows = np.arange(n_orders)
    regret = np.zeros((n_orders, n))
    cum = np.zeros(n_orders)
    for t in range(n):
        src = orders[:, t]
        b = codes[src]
        theta = rng.beta(alpha[rows, b], beta[rows, b])
        arm = theta.argmax(axis=1)
        r = rew[src, arm]
        alpha[rows, b, arm] += r
        beta[rows, b, arm] += 1 - r
        cum += rew[src, best_arm] - r
        regret[:, t] = cum
    ts = sorted({t for t in CHECKPOINTS if t < n} | {n})
    out = []
    for t in ts:
        v = regret[:, t - 1]
        out.append({"t": "all" if t == n else t, "n_sources": t, "regret_mean": v.mean(),
                    "regret_lo": np.percentile(v, 2.5), "regret_hi": np.percentile(v, 97.5),
                    "per_step_mean": v.mean() / t, "best_fixed_arm": Rf.columns[best_arm],
                    "context_key": context_key or "none", "n_orders": n_orders})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ synthetic data

def planted_best_arm(X: pd.DataFrame) -> pd.Series:
    """The arm planted as best in `synthetic`: short -> deterministic; else comparison -> A:chunked, else B:plain."""
    return pd.Series(np.where(X["length"] == "len_low", BASELINE,
                              np.where(X["comparison"], "gen-a:chunked", "gen-b:plain")), index=X.index)


def synthetic(n_sources: int = 200, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Planted structure for tests and demos.

    Short problems: the deterministic arm is best. Longer problems: gen-a:chunked is best when the problem is
    comparison-style ("times as many"), otherwise gen-b:plain. The best arm succeeds with probability 0.95, the others
    with 0.25 to 0.55 (the deterministic arm is weaker on long problems), independently per arm.
    Returns (R, X, sources).
    """
    rng = np.random.default_rng(seed)
    arms = [BASELINE, "gen-a:plain", "gen-a:chunked", "gen-b:plain", "gen-b:chunked", "gen-a:chunked+repair"]
    filler = ("Maria has some apples and buys more each day while her brother counts the boxes "
              "in the garage before dinner and writes the total in a small notebook").split()
    sources = []
    for i in range(n_sources):
        n_words = int(rng.choice([22, 45, 75]) + rng.integers(0, 6))
        comparison = n_words > 30 and rng.random() < 0.5
        words = [filler[j % len(filler)] for j in range(n_words)]
        if comparison:
            words[3:6] = ["has", "3", "times as many"]
        sources.append({"source_id": f"syn-{i:04d}", "text": " ".join(words) + "?",
                        "n_steps": int(np.clip(round(n_words / 20 + rng.normal(0, 0.6)), 1, 8))})
    X = contexts(sources)
    best = planted_best_arm(X)
    P = np.empty((n_sources, len(arms)))
    for j, a in enumerate(arms):
        P[:, j] = rng.uniform(0.25, 0.55, n_sources)
    P[X["length"].to_numpy() != "len_low", 0] -= 0.15     # deterministic is weak on long problems
    P[:, 5] = np.maximum(P[:, 2] - 0.05, 0.1)             # repair never beats the best single arm
    for j, a in enumerate(arms):
        P[(best == a).to_numpy(), j] = 0.95
    R = pd.DataFrame((rng.random(P.shape) < P).astype(float), index=X.index, columns=arms)
    return R, X, sources


# ------------------------------------------------------------------ cli

def _load_costs(path: Path) -> dict:
    if not path.exists():
        return {}
    led = pd.read_csv(path).fillna({"output_id": ""})
    led = led[led["output_id"] != ""]
    return led.groupby("output_id")["usd"].sum().to_dict()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run folder, e.g. data/outputs/main-v1")
    ap.add_argument("--labels", help="default: data/annotations/<run>/adjudicated.csv")
    ap.add_argument("--key", help="default: data/annotations/<run>/KEY_DO_NOT_OPEN.csv")
    ap.add_argument("--ledger", help="default: <run>/ledger.csv if present")
    ap.add_argument("--lam-cost", type=float, default=0.0, help="reward = outcome - lam_cost x USD per source")
    ap.add_argument("--synthetic", action="store_true", help="planted-structure demo instead of a real run")
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--out", help="policy.csv path (default <run>/analysis/policy.csv)")
    args = ap.parse_args()
    if not args.synthetic and not args.run:
        ap.error("give --run or --synthetic")

    if args.synthetic:
        R, X, _ = synthetic()
        R_bin = R
        out = Path(args.out or "policy.csv")
    else:
        run = Path(args.run)
        ann = ROOT / "data" / "annotations" / run.name
        key_path = args.key or ann / "KEY_DO_NOT_OPEN.csv"
        labels = prepare(args.labels or ann / "adjudicated.csv", key_path)   # derived outcomes + key columns
        key = pd.read_csv(key_path)
        cost = _load_costs(Path(args.ledger) if args.ledger else run / "ledger.csv")
        R = reward_table(labels, key, cost, args.lam_cost)
        R_bin = reward_table(labels, key, {}, 0.0)
        src = load_source_rows()
        X = contexts([src[s] for s in R.index if s in src])
        R, R_bin = R.loc[X.index], R_bin.loc[X.index]
        out = Path(args.out) if args.out else run / "analysis" / "policy.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"## Policy analysis: {len(R)} sources, {R.shape[1]} arms, lam_cost={args.lam_cost}\n")
    print(md(R.agg(["mean", "count"]).T.rename_axis("arm").reset_index()), "\n")
    res = leave_source_out(R, X, depth=args.depth, n_boot=args.boot)
    print(f"### Cross-validated value ({res.attrs['folds']}-fold by source; 95% source bootstrap CI)\n")
    print(md(res), "\n")
    pol = direct_policy(R, X, depth=args.depth)
    print("### Policy fit on all sources\n")
    print(pol.describe(), "\n")
    reg = thompson_replay(R_bin.clip(0, 1), X)
    print("### Thompson-sampling replay (SAFE_AND_USEFUL, regret vs best fixed arm)\n")
    print(md(reg))

    res.to_csv(out, index=False)
    (out.with_name(f"{out.stem}_tree.txt")).write_text(pol.describe() + "\n")
    reg.to_csv(out.with_name(f"{out.stem}_regret.csv"), index=False)
    print(f"\nwritten: {out}, {out.stem}_tree.txt, {out.stem}_regret.csv")


if __name__ == "__main__":
    main()
