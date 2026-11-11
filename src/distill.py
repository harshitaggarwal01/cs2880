"""Distilled free layer (Phase 3D): how much of the critic's recall can the deterministic layer's own evidence recover?

  python src/distill.py --run data/outputs/main-v1 [--labels ADJ.csv --key KEY.csv] [--use-critic]
  python src/distill.py --synthetic [--out analysis/distill.csv]

A small scikit-learn classifier is trained on features of the deterministic layer only (flag one-hots, flag counts,
readability deltas) to predict the human UNSAFE label. Evaluation is leave-source-out (GroupKFold on source_id, 5 folds)
and compares recall of UNSAFE at the SAME review rate as the det-only REJECT and det-only ANY operating points, so
the classifier cannot win by flagging more items. See docs/methods/distill.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2880
FOLDS = 5
FLAG_CODES = ["QTY_OMIT_OR_CHANGE", "LEAK_DERIVED_VALUE", "QTY_ADD", "LEAK_OPERATION", "LEAK_STEPS", "LEAK_SYMBOLS",
              "STRUCTURE_OR_RELEVANCE_CUE", "RELATION_OR_QUANTIFIER_LOST", "RELATION_OR_QUANTIFIER_ADDED",
              "UNIT_SET_CHANGED", "QUESTION_MISSING", "TARGET_WORDING_CHANGED", "LENGTH_EXPANDED", "LENGTH_SHRUNK"]
CRITIC_OVERALL = ["SAFE", "UNSAFE", "UNSURE", "MISSING"]
CRITIC_CODES = ["QTY_CHANGE", "QTY_OMIT", "QTY_ADD", "UNIT_CHANGE", "ENTITY_CHANGE", "REL_CHANGE", "COND_OMIT",
                "COND_ADD", "QUANTIFIER_CHANGE", "ORDER_CHANGE", "TARGET_CHANGE", "SOLVABILITY_CHANGE",
                "CONTRADICTION", "LEAK_ANSWER", "LEAK_INTERMEDIATE", "LEAK_OPERATION", "LEAK_STEPS", "LEAK_RELEVANCE"]


# ------------------------------------------------------------------ features

def features(verify_row: dict, source_text: str | None = None, use_critic: bool = False) -> dict:
    """Fixed-key feature dict for one verify row. Deterministic evidence only unless use_critic=True."""
    det = verify_row.get("deterministic") or {}
    flags = det.get("flags") or []
    codes = {f.get("code") for f in flags}
    rd = det.get("readability") or {}
    src_w, cand_w = rd.get("source_words") or 0, rd.get("candidate_words") or 0
    f: dict = {f"flag_{c}": int(c in codes) for c in FLAG_CODES}
    f["n_flags"] = len(flags)
    f["n_reject_flags"] = sum(1 for x in flags if x.get("severity") == "REJECT")
    f["fkgl_delta"] = float((rd.get("candidate_fkgl") or 0.0) - (rd.get("source_fkgl") or 0.0))
    f["word_ratio"] = cand_w / src_w if src_w else 1.0
    f["max_sentence_words"] = float(rd.get("candidate_max_sentence_words") or 0)
    f["src_words"] = float(len(source_text.split())) if source_text else float(src_w)
    if use_critic:
        critic = verify_row.get("critic")
        overall = "MISSING" if critic is None or "_error" in critic else str(critic.get("overall"))
        got = set((critic or {}).get("failure_codes") or [])
        f.update({f"critic_{o}": int(overall == o) for o in CRITIC_OVERALL})
        f.update({f"critic_code_{c}": int(c in got) for c in CRITIC_CODES})
        f["critic_math_fail"] = int((critic or {}).get("math_fidelity") == "FAIL")
        f["critic_leak"] = int((critic or {}).get("instructional_leakage") not in (None, "NONE", "UNSURE"))
    return f


def det_flags(verify_row: dict) -> tuple[int, int]:
    """(det-only REJECT, det-only ANY) indicators for a verify row."""
    flags = (verify_row.get("deterministic") or {}).get("flags") or []
    return int(any(x.get("severity") == "REJECT" for x in flags)), int(bool(flags))


# ------------------------------------------------------------------ evaluation

def _model(name: str, seed: int):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if name == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    if name == "gbt":
        return GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=0.1, subsample=0.8,
                                          random_state=seed)
    raise ValueError(f"unknown model {name!r}")


def _folds(groups: np.ndarray, seed: int):
    from sklearn.model_selection import GroupKFold
    k = min(FOLDS, len(set(groups)))
    try:
        return GroupKFold(n_splits=k, shuffle=True, random_state=seed)
    except TypeError:  # scikit-learn < 1.6 has no shuffle
        return GroupKFold(n_splits=k)


def leave_source_out_proba(X: np.ndarray, y: np.ndarray, groups: np.ndarray, model: str = "logreg",
                           seed: int = SEED) -> np.ndarray:
    """Out-of-fold P(unsafe): every item is scored by a model that never saw any item of its source."""
    p = np.zeros(len(y))
    for tr, te in _folds(groups, seed).split(X, y, groups):
        if len(set(y[tr])) < 2:
            p[te] = y[tr].mean()
            continue
        p[te] = _model(model, seed).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return p


def top_k_flags(p: np.ndarray, rate: float, seed: int = SEED) -> tuple[np.ndarray, float]:
    """Flag the round(rate * n) highest-scoring items (random tie-break); return flags and the cut-off score."""
    k = int(round(rate * len(p)))
    order = np.lexsort((np.random.default_rng(seed).random(len(p)), -p))
    flag = np.zeros(len(p), dtype=int)
    flag[order[:k]] = 1
    return flag, float(p[order[k - 1]]) if k else float("inf")


def _row(method: str, model: str, flag: np.ndarray, unsafe: np.ndarray, score: np.ndarray, thr=np.nan) -> dict:
    from sklearn.metrics import average_precision_score
    tp = int(((flag == 1) & (unsafe == 1)).sum())
    return {"method": method, "model": model, "n": len(unsafe), "n_unsafe": int(unsafe.sum()),
            "flag_rate": flag.mean(), "recall_unsafe": tp / unsafe.sum() if unsafe.sum() else np.nan,
            "precision": tp / flag.sum() if flag.sum() else np.nan,
            "auprc": average_precision_score(unsafe, score) if unsafe.sum() else np.nan, "threshold": thr}


def fit_eval(verify_rows: list[dict], labels_df: pd.DataFrame, groups=None, model: str = "logreg",
             review_rate_match: float | None = None, seed: int = SEED, sources: dict | None = None,
             use_critic: bool = False) -> pd.DataFrame:
    """Leave-source-out recall of UNSAFE for det-only flags vs the distilled score at the same flag rate.

    labels_df needs output_id, SAFE (1 = safe) and source_id (or pass `groups`, aligned to labels_df rows).
    `sources` is an optional {source_id: row or text} map used for the source-length feature.
    """
    lab = labels_df.copy()
    if groups is not None:
        lab["_group"] = list(groups)
    else:
        lab["_group"] = lab["source_id"]
    lab = lab.drop_duplicates("output_id")
    by_id = {r["output_id"]: r for r in verify_rows}
    lab = lab[lab["output_id"].isin(by_id)].reset_index(drop=True)
    if lab.empty:
        raise ValueError("no labelled items match the verify rows")

    def src_text(sid):
        s = (sources or {}).get(sid)
        return s.get("text") if isinstance(s, dict) else s

    feats = pd.DataFrame([features(by_id[o], src_text(s), use_critic) for o, s in zip(lab["output_id"], lab["source_id"])])
    X, unsafe = feats.to_numpy(float), (1 - lab["SAFE"].astype(int)).to_numpy()
    grp = lab["_group"].to_numpy()
    flags = np.array([det_flags(by_id[o]) for o in lab["output_id"]])
    rej, anyf = flags[:, 0], flags[:, 1]
    p = leave_source_out_proba(X, unsafe, grp, model, seed)

    out = [_row("det_only_reject", "-", rej, unsafe, rej.astype(float)),
           _row("det_only_any", "-", anyf, unsafe, anyf.astype(float))]
    rates = [("distilled@matched_reject_rate", rej.mean()), ("distilled@matched_any_rate", anyf.mean())]
    if review_rate_match is not None:
        rates.append((f"distilled@rate_{review_rate_match:g}", review_rate_match))
    for name, rate in rates:
        flag, thr = top_k_flags(p, rate, seed)
        out.append(_row(name, model, flag, unsafe, p, thr))
    df = pd.DataFrame(out)
    det_recall = {"distilled@matched_reject_rate": out[0]["recall_unsafe"], "distilled@matched_any_rate": out[1]["recall_unsafe"]}
    df["recall_minus_det"] = df["method"].map(lambda m: np.nan)
    for m, r in det_recall.items():
        df.loc[df["method"] == m, "recall_minus_det"] = df.loc[df["method"] == m, "recall_unsafe"] - r
    return df


# ------------------------------------------------------------------ synthetic data

def synthetic(n_sources: int = 150, per_source: int = 5, seed: int = 0) -> tuple[pd.DataFrame, list[dict]]:
    """Planted structure: unsafe items carry specific flags, more flags, longer text and a higher reading level.
    About a third of unsafe items carry no hard flag and can only be ranked through counts and readability."""
    rng = np.random.default_rng(seed)
    trans = ["plain", "chunked", "naive"]
    p_unsafe = {"plain": 0.2, "chunked": 0.15, "naive": 0.4}
    bad_codes = ["QTY_OMIT_OR_CHANGE", "LEAK_DERIVED_VALUE", "QTY_ADD", "LEAK_STEPS", "TARGET_WORDING_CHANGED"]
    soft_codes = ["RELATION_OR_QUANTIFIER_LOST", "UNIT_SET_CHANGED", "LENGTH_EXPANDED", "STRUCTURE_OR_RELEVANCE_CUE"]
    reject_codes = set(FLAG_CODES[:6])
    labels, rows = [], []
    for s in range(n_sources):
        sid = f"syn-{s:04d}"
        shift = rng.normal(0, 0.6)
        for j in range(per_source):
            t = trans[j % len(trans)]
            p = 1 / (1 + np.exp(-(np.log(p_unsafe[t] / (1 - p_unsafe[t])) + shift)))
            bad = rng.random() < p
            codes: list[str] = []
            if bad and rng.random() < 0.65:
                codes.append(str(rng.choice(bad_codes)))
            codes += [str(c) for c in rng.choice(soft_codes, size=min(len(soft_codes), rng.poisson(0.9 if bad else 0.3)),
                                                 replace=False)]
            flags = [{"code": c, "severity": "REJECT" if c in reject_codes else "REVIEW", "detail": "synthetic"}
                     for c in dict.fromkeys(codes)]
            src_w = int(rng.integers(25, 70))
            ratio = rng.normal(1.12 if bad else 1.0, 0.25 if bad else 0.18)
            read = {"source_fkgl": round(float(rng.normal(5.0, 1.0)), 2), "source_words": src_w,
                    "candidate_words": max(3, int(src_w * ratio)),
                    "candidate_max_sentence_words": int(max(4, rng.normal(19 if bad else 14, 5)))}
            read["candidate_fkgl"] = round(read["source_fkgl"] + float(rng.normal(0.6 if bad else -0.1, 1.0)), 2)
            det = {"decision": "REJECT" if any(f["severity"] == "REJECT" for f in flags) else
                   ("REVIEW" if flags else "PASS"), "flags": flags, "readability": read}
            overall = str(rng.choice(["UNSAFE", "UNSURE", "SAFE"], p=[0.6, 0.15, 0.25] if bad else [0.03, 0.08, 0.89]))
            critic = {"math_fidelity": "FAIL" if overall == "UNSAFE" else "PASS", "target_preserved": "PASS",
                      "instructional_leakage": "NONE", "ambiguity_introduced": "NO", "failure_codes": [],
                      "evidence": [], "overall": overall}
            oid = f"{sid}-{j}"
            rows.append({"output_id": oid, "decision": det["decision"], "reasons": [], "deterministic": det,
                         "critic": critic, "program": None})
            labels.append({"output_id": oid, "source_id": sid, "generator": "synthetic", "transformation": t,
                           "partition": "main", "SAFE": int(not bad)})
    return pd.DataFrame(labels), rows


# ------------------------------------------------------------------ cli

def _load_run(run: Path, labels: str | None, key: str | None) -> tuple[pd.DataFrame, list[dict], dict]:
    from common import ROOT, primary_verify_files, read_jsonl
    from evaluate import _primary, load_source_rows, prepare
    ann = ROOT / "data" / "annotations" / run.name
    df = _primary(prepare(labels or ann / "adjudicated.csv", key or ann / "KEY_DO_NOT_OPEN.csv"))
    files = primary_verify_files(run)
    if not files:
        raise SystemExit(f"no *.verify-*.jsonl in {run}")
    rows: dict[str, dict] = {}
    for f in files:  # a row with the critic layer beats a det-only row for the same output
        for r in read_jsonl(f):
            if r["output_id"] not in rows or (r.get("critic") is not None and rows[r["output_id"]].get("critic") is None):
                rows[r["output_id"]] = r
    return df, list(rows.values()), load_source_rows()


def _md(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False, floatfmt=".3f")
    except ImportError:
        return df.to_string(index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run dir, e.g. data/outputs/main-v1")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--model", choices=["logreg", "gbt", "both"], default="both")
    ap.add_argument("--use-critic", action="store_true", help="add critic fields (no longer a free layer)")
    ap.add_argument("--rate", type=float, default=None, help="extra matched review rate")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.synthetic:
        df, rows = synthetic()
        sources, out = None, (Path(args.out) if args.out else None)
    elif args.run:
        run = Path(args.run)
        df, rows, sources = _load_run(run, args.labels, args.key)
        out = Path(args.out) if args.out else run / "analysis" / "distill.csv"
    else:
        ap.error("give --run or --synthetic")
    models = ["logreg", "gbt"] if args.model == "both" else [args.model]
    res = []
    for m in models:
        r = fit_eval(rows, df, model=m, review_rate_match=args.rate, seed=args.seed, sources=sources,
                     use_critic=args.use_critic)
        res.append(r if not res else r[~r["method"].str.startswith("det_only")])  # det-only rows once
    res = pd.concat(res, ignore_index=True)
    print(f"## Distilled free layer: {len(df)} labelled items, {df['source_id'].nunique()} sources, "
          f"leave-source-out {FOLDS}-fold, critic features {'ON' if args.use_critic else 'off'}\n")
    print(_md(res))
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        res.to_csv(out, index=False)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
