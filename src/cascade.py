"""Cost-aware checking order: which verifier stage may stop an item, and what does it cost?

  python src/cascade.py --run data/outputs/anthropic-v1 --labels data/annotations/adjudicated.csv --key KEY.csv
  python src/cascade.py --run data/outputs/anthropic-v1 --labels ... --ledger data/outputs/anthropic-v1/ledger.csv
  python src/cascade.py --synthetic --out /tmp/cascade.csv      # planted-structure data, no files needed

Stages: S1 deterministic checks (free) -> S2 critic + program check (API cost) -> S3 human review (minutes).
A policy says which S1 / S2 outcomes may stop an item; whatever is not stopped is shipped or sent to a human.
Human review is assumed correct (the human label is the truth), so a human-reviewed item is never an unsafe ship
and never a safe reject. Every policy is evaluated on the same stored verifier fields; no API calls.

Objective (per 100 items): unsafe shipped + lam * USD + mu * human minutes. The Pareto table over
(unsafe shipped, USD, minutes) is the primary output; lam and mu only pick a point on it.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_COSTS = {"critic_usd": 0.01, "extract_usd": 0.008, "minutes_per_review": 1.5}
METRICS = ["unsafe_shipped", "safe_rejected", "human_items", "usd", "minutes", "objective"]
BOOL_KEYS = ["s1_stop_reject", "s1_stop_pass", "s2_stop_unsafe", "s2_stop_safe", "s2_unsure_to_human"]


# ------------------------------------------------------------------ policies

def _policy(name: str | None = None, **kw) -> dict:
    """Full policy dict. s2_enabled=False skips S2 and sends everything S1 did not stop to `rest`."""
    p = {k: False for k in BOOL_KEYS}
    p.update({"s2_enabled": True, "rest": "human", "kind": "staged"})
    p.update(kw)
    if name:
        p["name"] = name
    return p


def policy_name(p: dict) -> str:
    if p.get("name"):
        return p["name"]
    s1 = [n for k, n in (("s1_stop_reject", "rej"), ("s1_stop_pass", "pass")) if p.get(k)]
    s2 = [n for k, n in (("s2_stop_unsafe", "unsafe"), ("s2_stop_safe", "safe")) if p.get(k)]
    return f"s1[{','.join(s1)}]_s2[{','.join(s2)}]_rest[{'human' if p.get('s2_unsure_to_human') else 'ship'}]"


NAMED = [
    _policy("ship_everything", s2_enabled=False, rest="ship"),
    _policy("det_only_ship_rest", s1_stop_reject=True, s2_enabled=False, rest="ship"),
    _policy("det_only_human_rest", s1_stop_reject=True, s2_enabled=False, rest="human"),
    _policy("det_triage_human_rest", s1_stop_reject=True, s1_stop_pass=True, s2_enabled=False, rest="human"),
    _policy("full_verifier_human_review", kind="verifier"),
    _policy("human_everything", s2_enabled=False, rest="human"),
]


def _cat(row: dict) -> tuple[str, bool, str | None, str | None]:
    """(det decision, det clean, critic overall or None, program status or None) of a verify row."""
    det = row.get("deterministic") or {}
    dec = det.get("decision", "REVIEW")
    clean = dec == "PASS" and not det.get("flags")
    critic = row.get("critic")
    overall = None if not critic or critic.get("_error") else critic.get("overall")
    prog = (row.get("program") or {}).get("status")
    return dec, clean, overall, prog


def simulate(row: dict, policy: dict, costs: dict) -> tuple[str, float, float]:
    """(action, usd, human_minutes) for one verify row under one policy.

    action is "ship", "reject" or "human". S1 is free; reaching S2 costs critic_usd + extract_usd; a human review
    costs minutes_per_review. `costs` may carry per-item values; missing keys fall back to DEFAULT_COSTS.
    """
    c = {**DEFAULT_COSTS, **{k: v for k, v in costs.items() if v is not None and v == v}}
    s2_usd, mins = c["critic_usd"] + c["extract_usd"], c["minutes_per_review"]
    if policy.get("kind") == "verifier":  # the stored full-verifier decision: REJECT / REVIEW -> human / PASS
        d = row.get("decision")
        if d is None:
            from verify import decide  # lazy: verify pulls in the LLM client stack
            d = decide(row["deterministic"], row.get("critic"), row.get("program"))[0]
        return {"REJECT": ("reject", s2_usd, 0.0), "PASS": ("ship", s2_usd, 0.0)}.get(d, ("human", s2_usd, mins))
    dec, clean, overall, prog = _cat(row)
    if policy.get("s1_stop_reject") and dec == "REJECT":
        return "reject", 0.0, 0.0
    if policy.get("s1_stop_pass") and clean:
        return "ship", 0.0, 0.0
    if not policy.get("s2_enabled", True):
        return ("ship", 0.0, 0.0) if policy.get("rest") == "ship" else ("human", 0.0, mins)
    if policy.get("s2_stop_unsafe") and (overall == "UNSAFE" or prog == "MISMATCH"):
        return "reject", s2_usd, 0.0
    if policy.get("s2_stop_safe") and overall == "SAFE" and prog != "MISMATCH" and dec != "REJECT":
        return "ship", s2_usd, 0.0
    return ("human", s2_usd, mins) if policy.get("s2_unsure_to_human") else ("ship", s2_usd, 0.0)


def probe_rows() -> list[dict]:
    """One verify row per (det class, critic outcome, program outcome): the behavioural test set for policies."""
    from verify import decide
    det_cls = {"REJECT": {"decision": "REJECT", "flags": [{"code": "QTY_CHANGE", "severity": "REJECT"}]},
               "REVIEW": {"decision": "REVIEW", "flags": [{"code": "NEW_NUMBER", "severity": "REVIEW"}]},
               "PASS": {"decision": "PASS", "flags": []}}
    critics = {"SAFE": {"overall": "SAFE"}, "UNSAFE": {"overall": "UNSAFE", "failure_codes": ["QTY_CHANGE"]},
               "UNSURE": {"overall": "UNSURE"}, "NONE": None}
    progs = {"MATCH": {"status": "MATCH"}, "MISMATCH": {"status": "MISMATCH"},
             "UNCHECKABLE": {"status": "UNCHECKABLE"}, "NONE": None}
    rows = []
    for (dn, d), (cn, c), (pn, p) in itertools.product(det_cls.items(), critics.items(), progs.items()):
        decision, reasons = decide(d, c, p)
        rows.append({"output_id": f"probe|{dn}|{cn}|{pn}", "decision": decision, "reasons": reasons,
                     "deterministic": d, "critic": c, "program": p})
    return rows


def enumerate_policies() -> list[dict]:
    """All 2^5 staged policies plus the named ones, deduplicated by behaviour.

    Two policies are duplicates when they take the same action on every (det, critic, program) outcome; the
    named ones always survive, and among staged duplicates a policy that reaches S2 on a strict superset of
    another's outcomes (hence costs more for the same decisions) is dropped.
    """
    probes = probe_rows()
    zero = {"critic_usd": 1.0, "extract_usd": 0.0, "minutes_per_review": 1.0}

    def sig(p: dict) -> tuple[tuple[str, ...], frozenset[int]]:
        sims = [simulate(r, p, zero) for r in probes]
        return tuple(s[0] for s in sims), frozenset(i for i, s in enumerate(sims) if s[1] > 0)

    kept = []  # (policy, actions, S2-reach set, is_named)
    for p in NAMED:
        kept.append((dict(p), *sig(p), True))
    for bits in itertools.product([False, True], repeat=len(BOOL_KEYS)):
        p = _policy(**dict(zip(BOOL_KEYS, bits)))
        p["name"] = policy_name(p)
        actions, reached = sig(p)
        if any(a == actions and (named or r <= reached) for _, a, r, named in kept):
            continue  # same decisions as a kept policy that is no costlier
        kept = [k for k in kept if not (k[1] == actions and not k[3] and k[2] > reached)]  # drop costlier twins
        kept.append((p, actions, reached, False))
    return [k[0] for k in kept]


# ------------------------------------------------------------------ data

def stage_costs(ledger_csv: str | Path) -> dict[str, dict[str, float]]:
    """output_id -> {stage: usd} from a ledger.csv with columns output_id, stage, usd."""
    led = pd.read_csv(ledger_csv)
    led = led[led["output_id"].notna() & (led["output_id"].astype(str) != "")]
    g = led.groupby(["output_id", "stage"])["usd"].sum()
    out: dict[str, dict[str, float]] = {}
    for (oid, stage), usd in g.items():
        out.setdefault(str(oid), {})[str(stage)] = float(usd)
    return out


def frame(verify_rows: list[dict], labels_df: pd.DataFrame, costs: dict | None = None,
          defaults: dict | None = None) -> pd.DataFrame:
    """Join stored verify rows to labels on output_id; add per-item cost columns and the raw row (`_row`).

    costs: output_id -> {stage: usd} (from stage_costs). An item present in `costs` is charged its recorded
    critic / extract spend (0 if that stage has no ledger row); an item absent from it, or all items when
    costs is None, are charged `defaults` (critic_usd, extract_usd, minutes_per_review).
    """
    d = {**DEFAULT_COSTS, **(defaults or {})}
    lab = labels_df.drop_duplicates("output_id")
    keep = [c for c in ("output_id", "source_id", "generator", "transformation", "SAFE") if c in lab]
    vr = {r["output_id"]: r for r in verify_rows}
    df = lab[keep][lab["output_id"].isin(vr)].reset_index(drop=True)
    df["_row"] = [vr[o] for o in df["output_id"]]
    df["critic_usd"] = d["critic_usd"]
    df["extract_usd"] = d["extract_usd"]
    df["minutes_per_review"] = d["minutes_per_review"]
    if costs:
        for stage, col in (("critic", "critic_usd"), ("extract", "extract_usd")):
            df[col] = [costs[o].get(stage, 0.0) if o in costs else d[col] for o in df["output_id"]]
    return df


def _cost_cols(df: pd.DataFrame) -> list[dict]:
    return df[["critic_usd", "extract_usd", "minutes_per_review"]].to_dict("records")


def _run(df: pd.DataFrame, policy: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sims = [simulate(r, policy, c) for r, c in zip(df["_row"], _cost_cols(df))]
    return (np.array([s[0] for s in sims], dtype=object), np.array([s[1] for s in sims], dtype=float),
            np.array([s[2] for s in sims], dtype=float))


def _stats(unsafe: np.ndarray, act: np.ndarray, usd: np.ndarray, mins: np.ndarray, lam: float, mu: float) -> dict:
    n = max(len(act), 1)
    ship, rej, hum = act == "ship", act == "reject", act == "human"
    k = 100.0 / n
    out = {"unsafe_shipped": k * float((ship & unsafe).sum()), "safe_rejected": k * float((rej & ~unsafe).sum()),
           "human_items": k * float(hum.sum()), "usd": k * float(usd.sum()), "minutes": k * float(mins.sum()),
           "human_rate": float(hum.mean()) if len(act) else float("nan"),
           "reject_rate": float(rej.mean()) if len(act) else float("nan"),
           "ship_rate": float(ship.mean()) if len(act) else float("nan"),
           "recall_unsafe": 1 - float((ship & unsafe).sum()) / unsafe.sum() if unsafe.sum() else float("nan")}
    out["objective"] = out["unsafe_shipped"] + lam * out["usd"] + mu * out["minutes"]
    return out


def _unsafe(df: pd.DataFrame) -> np.ndarray:
    return (df["SAFE"].to_numpy() == 0)


def objective(df_rows: pd.DataFrame, policy: dict, lam: float, mu: float) -> dict:
    """Per-100-item outcome of one policy: unsafe_shipped, safe_rejected, human_items, usd, minutes, objective."""
    act, usd, mins = _run(df_rows, policy)
    s = _stats(_unsafe(df_rows), act, usd, mins, lam, mu)
    return {k: s[k] for k in METRICS}


def pareto(df_rows: pd.DataFrame, policies: list[dict] | None = None) -> pd.DataFrame:
    """Every policy's (unsafe shipped, USD, minutes) per 100 items; is_pareto = not dominated (lower is better)."""
    rows = []
    for p in policies or enumerate_policies():
        s = _stats(_unsafe(df_rows), *_run(df_rows, p), 0.0, 0.0)
        rows.append({"policy_name": policy_name(p), "policy": json.dumps({k: v for k, v in p.items() if k != "name"}),
                     "unsafe_shipped_per100": s["unsafe_shipped"], "safe_rejected_per100": s["safe_rejected"],
                     "usd_per100": s["usd"], "minutes_per100": s["minutes"], "human_rate": s["human_rate"],
                     "reject_rate": s["reject_rate"], "ship_rate": s["ship_rate"],
                     "recall_unsafe": s["recall_unsafe"]})
    out = pd.DataFrame(rows).round(9)
    m = out[["unsafe_shipped_per100", "usd_per100", "minutes_per100"]].to_numpy()
    dominated = [bool(((m <= m[i]).all(axis=1) & (m < m[i]).any(axis=1)).any()) for i in range(len(m))]
    out["is_pareto"] = [not d for d in dominated]
    return out.sort_values(["is_pareto", "unsafe_shipped_per100", "usd_per100", "minutes_per100"],
                           ascending=[False, True, True, True], kind="stable").reset_index(drop=True)


# ------------------------------------------------------------------ calibrate on one half, test on the other

def _split_by_source(sources: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Boolean mask over rows: True = calibration half. Whole sources go to one side."""
    uniq = np.unique(sources)
    cal = set(rng.permutation(uniq)[: len(uniq) // 2])
    return np.array([s in cal for s in sources])


def calibrate_and_test(df_rows: pd.DataFrame, lam: float, mu: float, seed: int, n_splits: int = 100) -> pd.DataFrame:
    """Pick the policy with the lowest objective on a random half of sources, score it on the other half.

    One row for all splits ("(all splits)": out-of-sample performance of the whole select-then-deploy
    procedure) and one per policy ever chosen, with its selection frequency. Test metrics are the mean and
    2.5 / 97.5 percentiles over splits.
    """
    policies = enumerate_policies()
    sims = [_run(df_rows, p) for p in policies]
    unsafe, src = _unsafe(df_rows), df_rows["source_id"].to_numpy()
    rng = np.random.default_rng(seed)
    recs = []
    for _ in range(n_splits):
        cal = _split_by_source(src, rng)
        scores = [_stats(unsafe[cal], a[cal], u[cal], m[cal], lam, mu)["objective"] for a, u, m in sims]
        j = int(np.argmin(scores))
        a, u, m = sims[j]
        recs.append({"policy_name": policy_name(policies[j]),
                     **_stats(unsafe[~cal], a[~cal], u[~cal], m[~cal], lam, mu)})
    res = pd.DataFrame(recs)
    cols = METRICS + ["human_rate", "recall_unsafe"]

    def summarize(name: str, g: pd.DataFrame) -> dict:
        r = {"policy_name": name, "n_selected": len(g), "freq": len(g) / len(res)}
        for c in cols:
            v = g[c].dropna()
            r[c + "_mean"] = v.mean() if len(v) else float("nan")
            r[c + "_lo"], r[c + "_hi"] = (np.percentile(v, [2.5, 97.5]) if len(v) else (float("nan"),) * 2)
        return r

    rows = [summarize("(all splits)", res)]
    for name, g in sorted(res.groupby("policy_name"), key=lambda kv: -len(kv[1])):
        rows.append(summarize(name, g))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ synthetic data

def synthetic(n_sources: int = 120, per_source: int = 6, seed: int = 0) -> tuple[list[dict], pd.DataFrame]:
    """(verify rows, labels df) with planted structure: det REJECT and critic UNSAFE mostly mean unsafe, naive is
    riskier than plain / chunked, and source difficulty is shared across a source's outputs."""
    from verify import decide
    rng = np.random.default_rng(seed)
    combos = [(g, t) for t in ("plain", "chunked", "naive") for g in ("haiku55", "sonnet55")]
    tf_eff = {"plain": 0.0, "chunked": 0.2, "naive": 1.2}
    rows, labs = [], []
    for i in range(n_sources):
        z = rng.normal()
        for k in range(per_source):
            gen, tf = combos[k % len(combos)]
            logit = -1.4 + 0.8 * z + tf_eff[tf] + (0.3 if gen == "haiku55" else 0.0)
            unsafe = bool(rng.random() < 1 / (1 + np.exp(-logit)))
            oid = f"S{i:03d}.{gen}.{tf}" + (f".{k // len(combos)}" if k >= len(combos) else "")
            u = rng.random()
            p_rej, p_rev = (0.40, 0.25) if unsafe else (0.02, 0.15)
            if u < p_rej:
                det = {"decision": "REJECT", "flags": [{"code": "QTY_CHANGE", "severity": "REJECT"}]}
            elif u < p_rej + p_rev:
                det = {"decision": "REVIEW", "flags": [{"code": "NEW_NUMBER", "severity": "REVIEW"}]}
            else:
                det = {"decision": "PASS", "flags": []}
            u = rng.random()
            probs = (0.60, 0.20) if unsafe else (0.07, 0.13)  # P(UNSAFE), P(UNSURE)
            if u < 0.02:
                critic = {"_error": "parse_failure"}
            else:
                overall = "UNSAFE" if u < probs[0] else "UNSURE" if u < sum(probs) else "SAFE"
                critic = {"overall": overall, "failure_codes": [], "math_fidelity": "PASS"}
                if overall == "UNSAFE":
                    critic["failure_codes"] = ["QTY_CHANGE"] if rng.random() < 0.8 else ["STYLE"]
            if "_meta" not in critic:
                critic["_meta"] = {"usage": {"input_tokens": int(rng.integers(700, 1200)),
                                             "output_tokens": int(rng.integers(100, 250))}}
            u = rng.random()
            pm, pu = (0.30, 0.20) if unsafe else (0.02, 0.18)  # P(MISMATCH), P(UNCHECKABLE)
            prog = {"status": "MISMATCH" if u < pm else "UNCHECKABLE" if u < pm + pu else "MATCH",
                    "relation_types_equal": True}
            decision, reasons = decide(det, critic, prog)
            rows.append({"output_id": oid, "decision": decision, "reasons": reasons, "deterministic": det,
                         "critic": critic, "program": prog, "extract_meta": None})
            labs.append({"output_id": oid, "source_id": f"src{i:03d}", "generator": gen, "transformation": tf,
                         "SAFE": 0 if unsafe else 1})
    return rows, pd.DataFrame(labs)


# ------------------------------------------------------------------ cli

def _md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False, floatfmt=".3f") if hasattr(df, "to_markdown") else df.to_string(index=False)


def _load_verify(run: Path) -> list[dict]:
    from common import read_jsonl
    files = sorted(run.glob("*.verify-critic-det-program.jsonl"))
    if not files:
        raise SystemExit(f"no *.verify-critic-det-program.jsonl in {run}; run src/verify.py first")
    return [r for f in files for r in read_jsonl(f)]


def _minutes(config: str) -> float:
    import yaml
    p = Path(config)
    return float(yaml.safe_load(open(p)).get("minutes_per_review", DEFAULT_COSTS["minutes_per_review"])) \
        if p.exists() else DEFAULT_COSTS["minutes_per_review"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run folder, e.g. data/outputs/anthropic-v1")
    ap.add_argument("--labels", help="adjudicated label CSV (with --key to attach output_id / generator)")
    ap.add_argument("--key")
    ap.add_argument("--ledger", help="ledger.csv (default: <run>/ledger.csv if present; else default per-item costs)")
    ap.add_argument("--config", default="config.yaml", help="for minutes_per_review")
    ap.add_argument("--lam", type=float, default=10.0, help="objective weight per USD per 100 items")
    ap.add_argument("--mu", type=float, default=1.0, help="objective weight per human minute per 100 items")
    ap.add_argument("--critic-usd", type=float, default=DEFAULT_COSTS["critic_usd"])
    ap.add_argument("--extract-usd", type=float, default=DEFAULT_COSTS["extract_usd"])
    ap.add_argument("--splits", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", help="pareto CSV path (default <run>/analysis/cascade.csv); "
                                  "the calibrated table goes next to it as <stem>_calibrated.csv")
    args = ap.parse_args()
    defaults = {"critic_usd": args.critic_usd, "extract_usd": args.extract_usd,
                "minutes_per_review": _minutes(args.config)}
    run = Path(args.run) if args.run else None
    costs = None
    if args.synthetic:
        vrows, labels = synthetic(seed=args.seed)
    else:
        if not (run and args.labels):
            ap.error("need --run and --labels (or --synthetic)")
        from evaluate import prepare
        labels = prepare(args.labels, args.key)
        if "is_repair" in labels:
            labels = labels[~labels["is_repair"]]
        if "source_id" not in labels and "source_id_x" in labels:
            labels = labels.rename(columns={"source_id_x": "source_id"})
        vrows = _load_verify(run)
        ledger = Path(args.ledger) if args.ledger else run / "ledger.csv"
        if ledger.exists():
            costs = stage_costs(ledger)
        elif args.ledger:
            ap.error(f"ledger not found: {ledger}")
    df = frame(vrows, labels, costs, defaults)
    if df.empty:
        raise SystemExit("no verify rows matched the labels on output_id")
    out = Path(args.out) if args.out else (run / "analysis" / "cascade.csv" if run else Path("cascade.csv"))
    out.parent.mkdir(parents=True, exist_ok=True)
    cal_out = out.with_name(out.stem + "_calibrated.csv")

    par = pareto(df)
    par.to_csv(out, index=False)
    cal = calibrate_and_test(df, args.lam, args.mu, args.seed, args.splits)
    cal.to_csv(cal_out, index=False)

    print(f"## Cascade policies, per 100 items (n={len(df)}, unsafe={int(_unsafe(df).sum())}; "
          f"costs {'ledger' if costs else 'default'}, {defaults['minutes_per_review']} min/review)\n")
    show = ["policy_name", "unsafe_shipped_per100", "usd_per100", "minutes_per100", "human_rate", "reject_rate",
            "ship_rate", "recall_unsafe", "is_pareto"]
    print("### Pareto frontier (not dominated on unsafe shipped, USD, minutes)\n")
    print(_md(par[par["is_pareto"]][show]), "\n")
    print(f"### Select on a calibration half of sources, test on the rest (lam={args.lam}, mu={args.mu}, "
          f"{args.splits} splits)\n")
    print(_md(cal[["policy_name", "freq", "unsafe_shipped_mean", "unsafe_shipped_lo", "unsafe_shipped_hi", "usd_mean",
                   "minutes_mean", "objective_mean", "objective_lo", "objective_hi"]]), "\n")
    print(f"{len(par)} policies -> {out}\n{len(cal)} rows -> {cal_out}")


if __name__ == "__main__":
    main()
