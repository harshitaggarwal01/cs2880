"""Pure functions behind demo/app.py (no streamlit import, so they can be unit-tested).

  load_run(run_dir)          index a data/outputs/<run_id>/ folder (generations, verify rows, ledger) plus frozen sources
  offline_view(index, sid)   one dict per stored output of a source: adaptation, verdict, reasons, flags, risk, cost
  live_check(src, cand, t)   deterministic checks + decision policy on any pasted pair (no API, no critic)
  live_rewrite(src, t, spec) one real or mock provider call with the project's prompt; parsed and priced
  deterministic_rewrite(src) the model-free chunking baseline (src/baseline.py)

Conformal, ledger and policy modules are imported lazily; a missing one only blanks the field that needs it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

DEFAULT_CONFIG = ROOT / "config.anthropic.yaml"
GEN_GLOBS = ["*generations*.jsonl", "baseline.jsonl", "repairs*.jsonl"]
PROMPT_FOR = {"plain": "plain_v1", "chunked": "chunked_v1", "naive": "naive_v1"}
BADGES = {"PASS": "✅ PASS", "REVIEW": "🟨 REVIEW", "REJECT": "🟥 REJECT"}
CRITIC_NOTE = "critic not run: a deterministic-only score never falls below 2.0 (critic missing)"


def _index_by_id(paths: list[Path]) -> dict[str, dict]:
    from common import read_jsonl
    out: dict[str, dict] = {}
    for p in paths:
        for r in read_jsonl(p):
            if r.get("output_id"):
                out[r["output_id"]] = r
    return out


def load_run(run_dir: Path, frozen_dir: Path | None = None) -> dict:
    """Index a run folder: sources, generations, verify rows (full-layer rows win over derived subsets)."""
    from common import FROZEN, read_jsonl
    run_dir = Path(run_dir)
    sources: dict[str, dict] = {}
    for p in sorted(Path(frozen_dir or FROZEN).glob("*.jsonl")):
        for r in read_jsonl(p):
            if r.get("text"):
                sources[r["source_id"]] = r
    gen_files = sorted({p for g in GEN_GLOBS for p in run_dir.glob(g) if ".verify-" not in p.name})
    gens = _index_by_id(gen_files)
    vfiles = sorted(run_dir.glob("*.verify-*.jsonl"))
    # derived subsets first, full-layer files last so the richest row for an output_id survives
    derived, full = [], []
    for p in vfiles:
        (full if "critic-det-program" in p.name else derived).append(p)
    verify = _index_by_id(derived + full)
    by_source: dict[str, list[str]] = {}
    for oid, g in gens.items():
        by_source.setdefault(g["source_id"], []).append(oid)
    ledger_path = run_dir / "ledger.csv"
    ledger = pd.read_csv(ledger_path) if ledger_path.exists() else None
    return {"run_dir": run_dir, "sources": sources, "gens": gens, "verify": verify, "by_source": by_source,
            "ledger": ledger}


def risk_of(row: dict) -> float | None:
    try:
        from conformal import risk_score
        return float(risk_score(row))
    except Exception:  # noqa: BLE001 - module absent or row malformed: the field is optional
        return None


def output_cost(ledger: pd.DataFrame | None, output_id: str) -> float | None:
    """USD over every ledger row of this output (repair rows fold into the original)."""
    if ledger is None or "output_id" not in ledger:
        return None
    base = ledger["output_id"].astype(str).str.replace(r"\|repair\d+$", "", regex=True)
    return float(ledger.loc[base == output_id, "usd"].sum())


def offline_view(index: dict, source_id: str) -> list[dict]:
    rows = []
    for oid in index["by_source"].get(source_id, []):
        g, v = index["gens"][oid], index["verify"].get(oid)
        det = (v or {}).get("deterministic") or {}
        rows.append({"output_id": oid, "generator": g.get("generator"), "transformation": g.get("transformation"),
                     "status": g.get("status"), "adapted_problem": g.get("adapted_problem"),
                     "decision": v.get("decision") if v else None, "reasons": (v or {}).get("reasons") or [],
                     "flags": det.get("flags") or [], "readability": det.get("readability") or {},
                     "risk_score": risk_of(v) if v else None, "cost": output_cost(index.get("ledger"), oid)})
    return sorted(rows, key=lambda r: (str(r["transformation"]), str(r["generator"])))


def live_check(source_text: str, candidate_text: str, transformation: str = "plain") -> dict:
    from deterministic_checks import check
    from verify import decide
    det = check(source_text, candidate_text, transformation)
    decision, reasons = decide(det, None, None, require_critic=False)
    row = {"deterministic": det, "critic": None, "program": None}
    return {"decision": decision, "reasons": reasons, "det": det, "flags": det["flags"],
            "readability": det["readability"], "risk_score": risk_of(row), "risk_note": CRITIC_NOTE}


def _prices(config_path: Path = DEFAULT_CONFIG) -> dict:
    try:
        return yaml.safe_load(Path(config_path).read_text(encoding="utf-8")).get("prices", {})
    except OSError:
        return {}


def load_generators(config_path: Path = DEFAULT_CONFIG) -> list[dict]:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    return [{"name": g["name"], "provider": g["provider"], "model": g["model"], "settings": g.get("settings", {})}
            for g in cfg.get("generators", [])]


def live_rewrite(source_text: str, transformation: str, provider_spec: dict, prices: dict | None = None) -> dict:
    from llm import call_with_one_retry, fill, load_prompt, make_provider, parse_json_block
    system, user_t, sha = load_prompt(PROMPT_FOR.get(transformation, f"{transformation}_v1"))
    r = call_with_one_retry(make_provider(provider_spec), system, fill(user_t, problem_text=source_text))
    raw = r.get("raw_output")
    parsed = parse_json_block(raw or "") or {}
    status = parsed.get("status") or ("ERROR" if raw is None else "PARSE_ERROR")
    usage = r.get("usage") or {}
    try:
        from ledger import price_call
        usd = price_call(usage, r.get("returned_model") or provider_spec["model"],
                         prices if prices is not None else _prices())
    except Exception:  # noqa: BLE001 - ledger module absent
        usd = None
    return {"adapted_problem": parsed.get("adapted_problem"), "status": status, "raw": raw,
            "returned_model": r.get("returned_model"), "usage": usage, "usd": usd, "error": r.get("error"),
            "prompt_sha256": sha}


def deterministic_rewrite(source_text: str) -> str:
    from baseline import render
    return render(source_text)


def verdict_badge(decision: str | None) -> str:
    return BADGES.get(decision or "", "⬜ NOT VERIFIED")
