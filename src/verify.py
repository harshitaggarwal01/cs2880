"""Hybrid verifier: deterministic checks + structured extraction/program check + LLM critic.

  python src/verify.py data/outputs/main-v1/generations.jsonl --config config.yaml
  python src/verify.py ... --layers det            # deterministic layer only (no API)
  python src/verify.py ... --layers det,critic     # ablations for RQ3
When a full (det,critic,program) verify file for the same generations already exists, --layers
subsets are computed offline from it (no API calls); rows are tagged "derived_from".
Baseline rows (generator "deterministic") get the deterministic layer only unless
--include-baseline-llm is given.

Extractions are cached in <run_dir>/extractions.jsonl keyed by sha256(text), so a text
(e.g. a source problem shared by many candidates) is extracted and paid for once.

Decision policy (frozen before looking at main-set labels; thresholds tuned on dev only)
  REJECT  any deterministic REJECT flag, OR critic overall=UNSAFE with a math/leak code,
          OR source and candidate programs evaluate to different values
  REVIEW  any REVIEW flag, critic UNSURE, critic refusal/parse failure, program not checkable
  PASS    otherwise
"""
from __future__ import annotations

import argparse
import ast
import json
import operator
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import yaml

from common import FROZEN, append_jsonl, read_jsonl, sha256_text
from deterministic_checks import check
from llm import call_with_one_retry, done_ids, fill, load_prompt, make_provider, parse_json_block

ALL_LAYERS = {"det", "critic", "program"}
META_KEYS = ("returned_model", "response_id", "usage", "latency_s", "stop_reason")
_CACHES: dict[Path, dict[str, dict]] = {}

HARD_CODES = {"QTY_CHANGE", "QTY_OMIT", "QTY_ADD", "UNIT_CHANGE", "ENTITY_CHANGE", "REL_CHANGE", "COND_OMIT", "COND_ADD",
              "QUANTIFIER_CHANGE", "ORDER_CHANGE", "TARGET_CHANGE", "SOLVABILITY_CHANGE", "CONTRADICTION",
              "LEAK_ANSWER", "LEAK_INTERMEDIATE", "LEAK_OPERATION", "LEAK_STEPS", "LEAK_RELEVANCE"}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg}


def safe_eval(expr: str) -> Fraction | None:
    """Evaluate an arithmetic expression with exact fractions; anything else -> None."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return Fraction(str(n.value))
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            if isinstance(n.op, ast.Pow) and abs(ev(n.right)) > 10:
                raise ValueError("exponent too large")
            return Fraction(_OPS[type(n.op)](ev(n.left), ev(n.right)))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") in {"round", "int", "abs", "min", "max"}:
            args = [ev(a) for a in n.args]
            f = {"round": lambda x, *k: Fraction(round(x, *[int(i) for i in k])), "int": lambda x: Fraction(int(x)),
                 "abs": abs, "min": min, "max": max}[n.func.id]
            return Fraction(f(*args))
        raise ValueError(f"unsupported node {type(n).__name__}")
    try:
        return ev(ast.parse(expr.strip(), mode="eval"))
    except Exception:  # noqa: BLE001
        return None


def program_check(src_ex: dict | None, cand_ex: dict | None) -> dict:
    if not src_ex or not cand_ex:
        return {"status": "UNCHECKABLE", "detail": "extraction failed"}
    a, b = safe_eval(str(src_ex.get("program", ""))), safe_eval(str(cand_ex.get("program", "")))
    if a is None or b is None:
        return {"status": "UNCHECKABLE", "detail": "program not evaluable"}
    rel_a = sorted(r.get("type", "") for r in src_ex.get("relations", []))
    rel_b = sorted(r.get("type", "") for r in cand_ex.get("relations", []))
    return {"status": "MATCH" if a == b else "MISMATCH", "source_value": float(a), "candidate_value": float(b),
            "relation_types_equal": rel_a == rel_b}


def decide(det: dict, critic: dict | None, prog: dict | None, require_critic: bool = True) -> tuple[str, list[str]]:
    """Decision policy (frozen before main labels are opened; see dossier 12.4).

    require_critic=True (the online run): a missing or failed critic is uncertainty -> REVIEW.
    require_critic=False (det-only ablations, the deterministic baseline): the critic was intentionally not run,
    so the decision rests on the layers that did run.
    """
    reasons = []
    if det["decision"] == "REJECT":
        reasons += [f"det:{f['code']}" for f in det["flags"] if f["severity"] == "REJECT"]
    if critic is not None:
        codes = set(critic.get("failure_codes") or [])
        if critic.get("overall") == "UNSAFE" and (codes & HARD_CODES or critic.get("math_fidelity") == "FAIL"
                                                  or critic.get("instructional_leakage") not in (None, "NONE", "UNSURE")):
            reasons.append("critic:UNSAFE:" + ",".join(sorted(codes)))
    if prog and prog.get("status") == "MISMATCH":
        reasons.append("program:MISMATCH")
    if reasons:
        return "REJECT", reasons
    review = [f"det:{f['code']}" for f in det["flags"]]
    if critic is None:
        if require_critic:
            review.append("critic:missing")
    elif critic.get("_error") or critic.get("overall") in ("UNSURE", "UNSAFE"):
        review.append("critic:" + ("missing" if critic.get("_error") else critic.get("overall")))
    if prog and prog.get("status") == "UNCHECKABLE":
        review.append("program:UNCHECKABLE")
    if prog and prog.get("status") == "MATCH" and not prog.get("relation_types_equal", True):
        review.append("program:RELATIONS_DIFFER")
    return ("REVIEW", review) if review else ("PASS", [])


def decide_subset(row: dict, layers: set[str]) -> tuple[str, list[str]]:
    """Recompute a stored verify row's decision as if only `layers` had run."""
    det = row["deterministic"] if "det" in layers else {"decision": "PASS", "flags": []}
    critic = row.get("critic") if "critic" in layers else None
    prog = row.get("program") if "program" in layers else None
    return decide(det, critic, prog, require_critic="critic" in layers)


def extract(text: str, provider, cache_path: Path) -> tuple[dict | None, dict]:
    """Structured extraction with a persistent cache keyed by sha256(text).

    Returns (parsed extraction or None, call meta). Technical failures (no reply) are not cached.
    """
    if cache_path not in _CACHES or not cache_path.exists():
        _CACHES[cache_path] = {r["key"]: r for r in read_jsonl(cache_path)} if cache_path.exists() else {}
    cache = _CACHES[cache_path]
    key = sha256_text(text)
    if key not in cache:
        system, user_t, _ = load_prompt("extract_v1")
        r = call_with_one_retry(provider, system, fill(user_t, problem_text=text))
        raw = r.get("raw_output")
        rec = {"key": key, "text_sha256": key, "extraction": parse_json_block(raw or ""),
               "meta": {k: r.get(k) for k in META_KEYS}}
        if raw is None:
            return None, {**rec["meta"], "text_sha256": key, "cached": False}
        append_jsonl(cache_path, rec)
        cache[key] = rec
        return rec["extraction"], {**rec["meta"], "text_sha256": key, "cached": False}
    rec = cache[key]
    return rec["extraction"], {**rec["meta"], "text_sha256": key, "cached": True}


def is_baseline(g: dict) -> bool:
    return g.get("generator") == "deterministic"


def derive_subset(full_path: Path, out_path: Path, layers: set[str]) -> None:
    """Write subset-layer decisions from an existing full verify file, with no API calls."""
    seen = done_ids(out_path)
    for v in read_jsonl(full_path):
        if v["output_id"] in seen:
            continue
        decision, reasons = decide_subset(v, layers)
        critic = {k: x for k, x in v["critic"].items() if k != "_meta"} if v.get("critic") and "critic" in layers else None
        row = {**{k: x for k, x in v.items() if k != "extract_meta"}, "layers": sorted(layers), "decision": decision,
               "reasons": reasons, "critic": critic, "program": v.get("program") if "program" in layers else None,
               "derived_from": full_path.name}
        append_jsonl(out_path, row)
        print(v["output_id"], decision, reasons[:3], "(derived)")


def load_sources() -> dict[str, str]:
    out = {}
    for p in FROZEN.glob("*.jsonl"):
        for r in read_jsonl(p):
            if r.get("text"):
                out[r["source_id"]] = r["text"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("generations")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--layers", default="det,critic,program")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--include-baseline-llm", action="store_true",
                    help="also run critic/program layers on deterministic-baseline rows (default: det only)")
    args = ap.parse_args()
    layers = set(args.layers.split(","))
    cfg = yaml.safe_load(open(args.config))
    src = load_sources()
    gen_path = Path(args.generations)
    gens = read_jsonl(gen_path)
    if gens and all(is_baseline(g) for g in gens) and not args.include_baseline_llm:
        layers &= {"det"}
    layers |= {"det"}  # the deterministic layer always runs
    stem = gen_path.stem + ".verify-"
    out_path = Path(args.out) if args.out else gen_path.with_name(stem + "-".join(sorted(layers)) + ".jsonl")
    full_path = gen_path.with_name(stem + "-".join(sorted(ALL_LAYERS)) + ".jsonl")
    if layers != ALL_LAYERS and full_path.exists() and full_path != out_path:
        derive_subset(full_path, out_path, layers)
        return

    seen = done_ids(out_path)
    mock = {"provider": "mock", "model": "mock"}
    use_llm = any(not is_baseline(g) or args.include_baseline_llm for g in gens)
    critic_p = make_provider(mock if args.mock else cfg["critic"]) if "critic" in layers and use_llm else None
    extract_p = make_provider(mock if args.mock else cfg["extractor"]) if "program" in layers and use_llm else None
    c_sys, c_user, c_sha = load_prompt("critic_v1")
    _, _, e_sha = load_prompt("extract_v1")
    cache_path = gen_path.parent / "extractions.jsonl"

    for g in gens:
        if g["output_id"] in seen or not g.get("adapted_problem"):
            continue
        skip_llm = is_baseline(g) and not args.include_baseline_llm
        row_layers = layers & {"det"} if skip_llm else layers
        source, cand = src[g["source_id"]], g["adapted_problem"]
        det = check(source, cand, g["transformation"])
        critic = prog = extract_meta = None
        if critic_p and not skip_llm:
            r = call_with_one_retry(critic_p, c_sys, fill(c_user, problem_text=source, candidate_text=cand,
                                                          transformation=g["transformation"]))
            critic = parse_json_block(r.get("raw_output") or "") or {"_error": r.get("error") or r.get("stop_reason")}
            critic["_meta"] = {k: r.get(k) for k in META_KEYS}
        if extract_p and not skip_llm:
            src_ex, meta_src = extract(source, extract_p, cache_path)
            cand_ex, meta_cand = extract(cand, extract_p, cache_path)
            prog = program_check(src_ex, cand_ex)
            extract_meta = {"source": meta_src, "candidate": meta_cand}
        decision, reasons = decide(det, critic, prog, require_critic="critic" in row_layers)
        append_jsonl(out_path, {"output_id": g["output_id"], "raw_output": "", "layers": sorted(row_layers),
                                "decision": decision, "reasons": reasons, "deterministic": det, "critic": critic,
                                "program": prog, "critic_prompt_sha256": c_sha, "extract_prompt_sha256": e_sha,
                                "extract_meta": extract_meta,
                                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        print(g["output_id"], decision, reasons[:3])


if __name__ == "__main__":
    main()
