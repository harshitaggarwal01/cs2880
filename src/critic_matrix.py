"""Generator x critic matrix: per-critic accuracy, self-preference test, and critic ensembles (Task A2).

  python src/critic_matrix.py --run data/outputs/matrix-v1 --config config.matrix.yaml \
      --labels data/annotations/matrix-v1/adjudicated.csv --key data/annotations/matrix-v1/KEY_DO_NOT_OPEN.csv
  python src/critic_matrix.py --synthetic --out-dir /tmp/cm     # planted self-preference, no files needed

Additional, clearly labelled analysis: it does not change the prespecified Phase-1 analysis, which uses the primary
critic only. Human labels attach to rewrites, so every critic is scored against the same adjudicated SAFE labels.

A critic "says SAFE" when its `overall` is SAFE; UNSURE, UNSAFE, a parse failure or a missing reply count as
"not SAFE" (the item would go to a human or be rejected). Positive class = human UNSAFE throughout.

Outputs (in <run>/analysis/ or --out-dir):
  critic_matrix.csv     per critic: recall / precision / review rate (critic verdict alone, and the full verifier
                        decision with that critic), USD per item, source-clustered bootstrap CIs; plus the
                        generator x critic grid (critic SAFE rate, error rate against humans, false-SAFE rate)
  self_preference.csv   among human-UNSAFE items: logit of "critic says SAFE" on same_family + generator and
                        critic fixed effects, SEs clustered by source (Firth + cluster bootstrap on separation,
                        the same rule as evaluate.logit_unsafe). Panickssery et al. 2024.
  critic_ensembles.csv  majority vote, any-not-SAFE, and a cost-ordered cascade (cheap critic first, the expensive
                        one only when the cheap one is not SAFE), scored like single critics
  critic_pareto.csv     cascade.py policies run once per critic option (single critics and ensembles), with the
                        option's own critic cost, and one global Pareto frontier over (unsafe shipped, USD, minutes)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import cascade
from conformal import risk_score
from evaluate import cluster_boot, fit_logit_clustered, verifier_metrics

DEFAULT_CRITIC_USD = 0.01
B = 500


# ------------------------------------------------------------------ loading

def critic_files(run: Path, cfg: dict) -> dict[str, list[Path]]:
    """critic name -> its verify files (primary: *.verify-critic-det-program.jsonl; others: *critic@NAME*)."""
    from verify import critic_specs
    specs, primary = critic_specs(cfg)
    out = {}
    for name in specs:
        pat = "*.verify-critic-det-program.jsonl" if name == primary else f"*.verify-critic@{name}-det-program.jsonl"
        out[name] = sorted(p for p in run.glob(pat) if not p.name.startswith("repairs."))
    return out


def load_rows(files: dict[str, list[Path]]) -> dict[str, list[dict]]:
    from common import read_jsonl
    return {n: [r for f in fs for r in read_jsonl(f)] for n, fs in files.items()}


def critic_costs(ledger_csv: Path | None) -> dict[tuple[str, str], float]:
    """(output_id, critic_name) -> critic USD, from ledger.csv."""
    if not ledger_csv or not Path(ledger_csv).exists():
        return {}
    led = pd.read_csv(ledger_csv)
    if "critic_name" not in led:
        return {}
    led = led[(led["stage"] == "critic") & led["critic_name"].notna()]
    return {k: float(v) for k, v in led.groupby(["output_id", "critic_name"])["usd"].sum().items()}


# ------------------------------------------------------------------ wide frame

def says_safe(critic: dict | None) -> int:
    return int(bool(critic) and not critic.get("_error") and critic.get("overall") == "SAFE")


def wide(rows: dict[str, list[dict]], labels: pd.DataFrame, gen_family: dict[str, str],
         critic_family: dict[str, str], costs: dict | None = None) -> pd.DataFrame:
    """One row per labelled output; per critic c: safe_<c>, decision_<c> (full verifier), usd_<c>, row_<c>."""
    lab = labels.drop_duplicates("output_id")[["output_id", "source_id", "generator", "SAFE"]].copy()
    lab["gen_family"] = lab["generator"].map(gen_family)
    costs = costs or {}
    for c, rs in rows.items():
        by = {r["output_id"]: r for r in rs}
        lab = lab[lab["output_id"].isin(by)].copy()
        lab[f"row_{c}"] = [by[o] for o in lab["output_id"]]
        lab[f"safe_{c}"] = [says_safe(by[o].get("critic")) for o in lab["output_id"]]
        lab[f"decision_{c}"] = [by[o]["decision"] for o in lab["output_id"]]
        lab[f"usd_{c}"] = [costs.get((o, c), DEFAULT_CRITIC_USD if costs == {} else 0.0) for o in lab["output_id"]]
    lab.attrs["critics"] = list(rows)
    lab.attrs["critic_family"] = critic_family
    return lab.reset_index(drop=True)


# ------------------------------------------------------------------ per-critic metrics

def _rate(d: pd.DataFrame, num, den) -> float:
    n = den(d).sum()
    return float(num(d).sum() / n) if n else float("nan")


def score_option(df: pd.DataFrame, name: str, safe_col: str, usd_col: str, decision_col: str | None,
                 b: int = B, kind: str = "critic") -> list[dict]:
    """Recall / precision / review rate of one critic option, critic verdict alone and (if given) full decision."""
    out = []
    variants = [("critic_verdict", 1 - df[safe_col])]
    if decision_col is not None:
        variants.append(("full_verifier", (df[decision_col] != "PASS").astype(int)))
    for basis, flag in variants:
        d = df.assign(_flag=flag.to_numpy())
        m = verifier_metrics(d, "_flag", b)
        prec = cluster_boot(d, lambda x: _rate(x, lambda y: (y["_flag"] == 1) & (y["SAFE"] == 0),
                                                lambda y: y["_flag"] == 1), b)
        rev = cluster_boot(d, lambda x: float(x["_flag"].mean()), b)
        out.append({"kind": kind, "critic": name, "basis": basis, "n": len(d), "n_unsafe": int((d["SAFE"] == 0).sum()),
                    "recall_unsafe": m["recall_unsafe"], "recall_lo": m["recall_ci"][0], "recall_hi": m["recall_ci"][1],
                    "precision": m["precision"], "precision_lo": prec[1], "precision_hi": prec[2],
                    "review_rate": m["flag_rate"], "review_lo": rev[1], "review_hi": rev[2],
                    "false_safe": m["fn"], "usd_per_item": float(df[usd_col].mean()),
                    "risk_auc": _auc(df, name) if kind == "critic" else float("nan")})
    return out


def _auc(df: pd.DataFrame, c: str) -> float:
    """ROC-AUC of conformal.risk_score (built on this critic's verify rows) for human UNSAFE."""
    if f"row_{c}" not in df:
        return float("nan")
    s = np.array([risk_score(r) for r in df[f"row_{c}"]])
    y = (df["SAFE"].to_numpy() == 0)
    if y.all() or (~y).all():
        return float("nan")
    from scipy.stats import rankdata
    r = rankdata(s)
    return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


def critic_table(df: pd.DataFrame, b: int = B) -> pd.DataFrame:
    rows = []
    for c in df.attrs["critics"]:
        rows += score_option(df, c, f"safe_{c}", f"usd_{c}", f"decision_{c}", b)
    t = pd.DataFrame(rows)
    t.insert(2, "family", t["critic"].map(df.attrs["critic_family"]))
    return t


def grid(df: pd.DataFrame) -> pd.DataFrame:
    """Generator x critic: critic SAFE rate, error rate against humans, false-SAFE rate on human UNSAFE."""
    out = []
    fam = df.attrs["critic_family"]
    for (g, gf), d in df.groupby(["generator", "gen_family"], dropna=False):
        for c in df.attrs["critics"]:
            s = d[f"safe_{c}"]
            uns = d["SAFE"] == 0
            out.append({"kind": "grid", "generator": g, "gen_family": gf, "critic": c, "family": fam.get(c),
                        "same_family": gf == fam.get(c), "n": len(d), "n_unsafe": int(uns.sum()),
                        "critic_safe_rate": float(s.mean()), "error_rate": float((s != d["SAFE"]).mean()),
                        "false_safe_rate": float(s[uns].mean()) if uns.any() else float("nan")})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ self-preference

def long_unsafe(df: pd.DataFrame) -> pd.DataFrame:
    fam = df.attrs["critic_family"]
    rows = []
    for _, r in df[df["SAFE"] == 0].iterrows():
        for c in df.attrs["critics"]:
            rows.append({"output_id": r["output_id"], "source_id": r["source_id"], "generator": r["generator"],
                         "critic": c, "y": int(r[f"safe_{c}"]), "same_family": int(r["gen_family"] == fam.get(c))})
    return pd.DataFrame(rows)


def self_preference(df: pd.DataFrame, n_boot: int = 400, seed: int = 0) -> pd.DataFrame:
    """Logit of critic-says-SAFE among human-UNSAFE items on same_family + generator FE + critic FE.

    A positive same_family coefficient = critics are more lenient on their own family's unsafe rewrites. Identified
    only when the crossing varies (at least two families on both sides); otherwise the row says so.
    """
    L = long_unsafe(df)
    cols = ["term", "coef", "se", "z", "p", "odds_ratio", "or_lo", "or_hi", "n", "n_items", "method", "note"]
    if L.empty or L["same_family"].nunique() < 2 or L["y"].nunique() < 2:
        return pd.DataFrame([{**{k: np.nan for k in cols}, "term": "same_family", "n": len(L), "method": "none",
                              "note": "not identified: need human-UNSAFE items with both same- and cross-family "
                                      "critic verdicts and both verdict values"}])
    X = pd.DataFrame({"same_family": L["same_family"].astype(float)})
    X = X.join(pd.get_dummies(L["generator"], prefix="gen", drop_first=True, dtype=float))
    X = X.join(pd.get_dummies(L["critic"], prefix="critic", drop_first=True, dtype=float))
    X = X.loc[:, X.nunique() > 1]
    # greedily keep fixed-effect dummies that are not collinear with same_family (+ intercept)
    keep = ["same_family"]
    for c in X.columns[1:]:
        M = np.column_stack([np.ones(len(X)), X[keep + [c]].to_numpy()])
        if np.linalg.matrix_rank(M) == M.shape[1]:
            keep.append(c)
    X = X[keep]
    groups = pd.factorize(L["source_id"])[0]
    res = fit_logit_clustered(L["y"], X, groups, n_boot=n_boot, seed=seed)
    t = res["table"].copy()
    t["n"], t["n_items"], t["method"] = res["n"], L["output_id"].nunique(), res["method"]
    t["note"] = ""
    return t[cols]


# ------------------------------------------------------------------ ensembles

def _pick(rows: list[dict], want_safe: bool) -> dict | None:
    for r in rows:
        if says_safe(r.get("critic")) == want_safe:
            return r.get("critic")
    return rows[0].get("critic")


def ensemble_verdicts(df: pd.DataFrame, cheap: str | None = None, expensive: str | None = None) -> pd.DataFrame:
    """Adds safe_/usd_/row_ columns for: majority (ties -> not SAFE), any_unsafe (any not SAFE) and, when cheap and
    expensive are given, cascade:<cheap>><expensive> (expensive critic called only when cheap is not SAFE)."""
    cs = df.attrs["critics"]
    d = df.copy()
    d.attrs = df.attrs
    safe = d[[f"safe_{c}" for c in cs]].to_numpy()
    usd_all = d[[f"usd_{c}" for c in cs]].sum(axis=1).to_numpy()
    opts = {"majority": (safe.sum(axis=1) * 2 > len(cs)).astype(int), "any_unsafe": safe.min(axis=1)}
    usd = {"majority": usd_all, "any_unsafe": usd_all}
    if cheap and expensive:
        name = f"cascade:{cheap}>{expensive}"
        ch = d[f"safe_{cheap}"].to_numpy()
        opts[name] = np.where(ch == 1, 1, d[f"safe_{expensive}"].to_numpy())
        usd[name] = d[f"usd_{cheap}"].to_numpy() + np.where(ch == 1, 0.0, d[f"usd_{expensive}"].to_numpy())
    for name, v in opts.items():
        d[f"safe_{name}"] = v
        d[f"usd_{name}"] = usd[name]
        members = [cheap, expensive] if name.startswith("cascade:") else cs
        new_rows = []
        for i, (_, r) in enumerate(d.iterrows()):
            base = r[f"row_{cs[0]}"]
            if name.startswith("cascade:") and r[f"safe_{cheap}"] == 1:
                crit = r[f"row_{cheap}"].get("critic")
            else:
                crit = _pick([r[f"row_{m}"] for m in (members[1:] if name.startswith("cascade:") else members)],
                             bool(v[i]))
            new_rows.append({**base, "critic": crit, "decision": None})
        d[f"row_{name}"] = new_rows
        d[f"decision_{name}"] = [_decide(r) for r in new_rows]
    d.attrs["ensembles"] = list(opts)
    return d


def _decide(row: dict) -> str:
    from verify import decide
    return decide(row["deterministic"], row.get("critic"), row.get("program"))[0]


def ensemble_table(d: pd.DataFrame, b: int = B) -> pd.DataFrame:
    rows = []
    for e in d.attrs["ensembles"]:
        rows += score_option(d, e, f"safe_{e}", f"usd_{e}", f"decision_{e}", b, kind="ensemble")
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ cascade.py on every critic option

def option_pareto(d: pd.DataFrame, extract_usd: float = cascade.DEFAULT_COSTS["extract_usd"],
                  minutes: float = cascade.DEFAULT_COSTS["minutes_per_review"]) -> pd.DataFrame:
    parts = []
    for opt in d.attrs["critics"] + d.attrs.get("ensembles", []):
        rows = [{**r, "output_id": o} for r, o in zip(d[f"row_{opt}"], d["output_id"])]
        for r in rows:
            r["decision"] = _decide(r)
        costs = {o: {"critic": float(u), "extract": extract_usd} for o, u in zip(d["output_id"], d[f"usd_{opt}"])}
        f = cascade.frame(rows, d[["output_id", "source_id", "generator", "SAFE"]].assign(transformation=""), costs,
                          {"minutes_per_review": minutes})
        p = cascade.pareto(f)
        p.insert(0, "critic_option", opt)
        parts.append(p)
    out = pd.concat(parts, ignore_index=True)
    m = out[["unsafe_shipped_per100", "usd_per100", "minutes_per100"]].to_numpy()
    out["is_pareto_global"] = [not bool(((m <= m[i]).all(axis=1) & (m < m[i]).any(axis=1)).any())
                               for i in range(len(m))]
    return out.sort_values(["is_pareto_global", "unsafe_shipped_per100", "usd_per100"],
                           ascending=[False, True, True], kind="stable").reset_index(drop=True)


# ------------------------------------------------------------------ synthetic data

def synthetic(n_sources: int = 150, seed: int = 0, self_pref: float = 2.0) -> tuple[dict, pd.DataFrame, dict, dict]:
    """Two generators (anthropic, qwen) x three critics (two anthropic, one qwen), with planted self-preference:
    on UNSAFE items, logit P(critic says SAFE) = -1.5 + self_pref * same_family + critic skill offset."""
    rng = np.random.default_rng(seed)
    gens = {"genA": "anthropic", "genQ": "alibaba-qwen"}
    crits = {"critA": "anthropic", "critA2": "anthropic", "critQ": "alibaba-qwen"}
    skill = {"critA": 0.0, "critA2": 0.3, "critQ": 0.5}
    usd = {"critA": 0.02, "critA2": 0.01, "critQ": 0.0005}
    rows = {c: [] for c in crits}
    lab = []
    for s in range(n_sources):
        for g, gf in gens.items():
            for tf in ("plain", "chunked"):
                oid = f"syn|{g}|{tf}|s{s}"
                unsafe = rng.random() < 0.3
                lab.append({"output_id": oid, "source_id": f"s{s}", "generator": g, "SAFE": int(not unsafe)})
                for c, cf in crits.items():
                    if unsafe:
                        p = 1 / (1 + np.exp(-(-1.5 + self_pref * (gf == cf) + skill[c])))
                    else:
                        p = 0.9
                    ok = rng.random() < p
                    critic = {"overall": "SAFE" if ok else "UNSAFE", "failure_codes": [] if ok else ["QTY_CHANGE"],
                              "math_fidelity": "PASS" if ok else "FAIL", "instructional_leakage": "NONE"}
                    rows[c].append({"output_id": oid, "deterministic": {"decision": "PASS", "flags": []},
                                    "critic": critic, "program": {"status": "MATCH", "relation_types_equal": True},
                                    "decision": "PASS" if ok else "REJECT"})
    costs = {(r["output_id"], c): usd[c] for c in crits for r in rows[c]}
    return rows, pd.DataFrame(lab), {"gen_family": gens, "critic_family": crits}, costs


# ------------------------------------------------------------------ cli

def analyse(rows, labels, fams, costs, cheap=None, expensive=None, b=B, n_boot=400):
    df = wide(rows, labels, fams["gen_family"], fams["critic_family"], costs)
    if df.empty:
        raise SystemExit("no verify rows matched the labels on output_id")
    d = ensemble_verdicts(df, cheap, expensive)
    matrix = pd.concat([critic_table(df, b), grid(df)], ignore_index=True)
    return matrix, self_preference(df, n_boot=n_boot), ensemble_table(d, b), option_pareto(d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--config", default="config.matrix.yaml")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--cheap", help="cheap critic for the cost-ordered cascade (default: cheapest by ledger)")
    ap.add_argument("--expensive", help="expensive critic for the cascade (default: primary_critic)")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out-dir")
    ap.add_argument("--boot", type=int, default=B)
    args = ap.parse_args()
    if args.synthetic:
        rows, labels, fams, costs = synthetic()
        cheap, expensive = args.cheap or "critQ", args.expensive or "critA"
        out_dir = Path(args.out_dir or "critic_matrix_synthetic")
    else:
        import yaml
        from evaluate import prepare
        from verify import critic_specs
        if not (args.run and args.labels):
            ap.error("need --run and --labels (or --synthetic)")
        run = Path(args.run)
        cfg = yaml.safe_load(open(args.config))
        specs, primary = critic_specs(cfg)
        labels = prepare(args.labels, args.key)
        if "is_repair" in labels:
            labels = labels[~labels["is_repair"]]
        if "source_id" not in labels and "source_id_x" in labels:
            labels = labels.rename(columns={"source_id_x": "source_id"})
        rows = {n: r for n, r in load_rows(critic_files(run, cfg)).items() if r}
        costs = critic_costs(run / "ledger.csv")
        fams = {"gen_family": {g["name"]: g.get("family") for g in cfg["generators"]},
                "critic_family": {n: s.get("family") for n, s in specs.items()}}
        expensive = args.expensive or primary
        if args.cheap:
            cheap = args.cheap
        else:
            per = {n: np.mean([v for (o, c), v in costs.items() if c == n] or [np.inf]) for n in rows}
            cheap = min(per, key=per.get) if len(rows) > 1 else None
        if cheap == expensive:
            cheap = None
        out_dir = Path(args.out_dir) if args.out_dir else run / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix, sp, ens, par = analyse(rows, labels, fams, costs, cheap, expensive, b=args.boot)
    matrix.to_csv(out_dir / "critic_matrix.csv", index=False)
    sp.to_csv(out_dir / "self_preference.csv", index=False)
    ens.to_csv(out_dir / "critic_ensembles.csv", index=False)
    par.to_csv(out_dir / "critic_pareto.csv", index=False)
    show = ["critic", "basis", "n", "recall_unsafe", "recall_lo", "recall_hi", "precision", "review_rate", "usd_per_item"]
    print("## Critics (additional analysis; primary-critic results stay the prespecified ones)\n")
    print(matrix[matrix["kind"] == "critic"][show].to_markdown(index=False, floatfmt=".3f"), "\n")
    print("## Self-preference (human-UNSAFE items)\n")
    print(sp[sp["term"] == "same_family"].to_markdown(index=False, floatfmt=".3f"), "\n")
    print("## Ensembles\n")
    print(ens[show].to_markdown(index=False, floatfmt=".3f"), "\n")
    print(f"wrote {out_dir}/critic_matrix.csv, self_preference.csv, critic_ensembles.csv, critic_pareto.csv")


if __name__ == "__main__":
    main()
