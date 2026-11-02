"""SafeAdapt demo (Streamlit).

  streamlit run demo/app.py -- --offline data/outputs/anthropic-v1     # no API key needed
  ANTHROPIC_API_KEY=... streamlit run demo/app.py                       # live mode available in the sidebar

Offline mode reads stored generations and verifier rows; live mode rewrites a pasted problem with the chosen
generator and checks it with the deterministic layer only (no critic call).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

BUTTONS = {"Deterministic split": None, "Plain language": "plain", "Chunked": "chunked",
           "Realistic teacher prompt": "naive"}
CAVEAT = ("Same-family caveat: in the Anthropic-only configuration the generators and the critic are all Claude "
          "models, so their errors may be correlated and the verdicts can look better than they are. "
          "PASS = no problems detected under these checks, not a guarantee that the problem is safe.")


def cli_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", default=None, help="run dir, e.g. data/outputs/anthropic-v1")
    argv = sys.argv[1:]
    return ap.parse_known_args(argv[1:] if argv[:1] == ["--"] else argv)[0]


@st.cache_data(show_spinner=False)
def cached_run(run_dir: str) -> dict:
    return core.load_run(Path(run_dir))


def default_run_dir(arg: str | None) -> str | None:
    if arg:
        return arg
    runs = sorted(p for p in (core.ROOT / "data" / "outputs").glob("*") if p.is_dir())
    preferred = core.ROOT / "data" / "outputs" / "anthropic-v1"
    return str(preferred if preferred.exists() else runs[0]) if runs else None


def show_result(source: str, res: dict, title: str) -> None:
    """Original on the left, adaptation on the right, then verdict, reasons, flags, risk and cost."""
    left, right = st.columns(2)
    left.markdown("**Original**")
    left.text(source)
    right.markdown(f"**{title}**")
    right.text(res.get("adapted_problem") or "(no adaptation returned)")
    st.subheader(core.verdict_badge(res.get("decision")))
    if res.get("reasons"):
        st.write("Reasons: " + ", ".join(res["reasons"]))
    elif res.get("decision") == "PASS":
        st.write("No problems detected under these checks.")
    if res.get("flags"):
        st.dataframe(pd.DataFrame(res["flags"]), hide_index=True, width="stretch")
    cols = st.columns(3)
    risk = res.get("risk_score")
    cols[0].metric("Risk score", "n/a" if risk is None else f"{risk:.1f}")
    cost = res.get("cost", res.get("usd"))
    cols[1].metric("Cost (USD)", "n/a" if cost is None else f"{cost:.5f}")
    cols[2].metric("Words", res.get("readability", {}).get("candidate_words", "n/a"))
    if res.get("risk_note"):
        st.caption(res["risk_note"])


def offline_mode(args: argparse.Namespace) -> None:
    run_dir = st.sidebar.text_input("Run directory", default_run_dir(args.offline) or "")
    if not run_dir or not Path(run_dir).is_dir():
        st.warning("Give a run directory such as data/outputs/anthropic-v1 (run `make phase1` first).")
        return
    idx = cached_run(run_dir)
    ids = sorted(idx["by_source"])
    if not ids:
        st.warning(f"No stored outputs in {run_dir}.")
        return
    sid = st.sidebar.selectbox("Source problem", ids, format_func=lambda s: f"{s}: {idx['sources'].get(s, {}).get('text', '')[:50]}")
    source = idx["sources"].get(sid, {}).get("text", "(source not found in data/frozen)")
    views = core.offline_view(idx, sid)
    st.markdown("**Original problem**")
    st.info(source)
    pick = st.radio("Show", list(BUTTONS), horizontal=True)
    if BUTTONS[pick] is None:
        res = {**core.live_check(source, core.deterministic_rewrite(source), "chunked"),
               "adapted_problem": core.deterministic_rewrite(source)}
        show_result(source, res, "Deterministic split (no model)")
    else:
        match = [v for v in views if v["transformation"] == BUTTONS[pick]]
        if not match:
            st.write(f"No stored output for '{BUTTONS[pick]}' on this source.")
        for v in match:
            show_result(source, v, f"{v['generator']} / {v['transformation']}")
    st.divider()
    st.markdown(f"**All {len(views)} stored outputs for this source**")
    table = pd.DataFrame([{"generator": v["generator"], "transformation": v["transformation"],
                           "verdict": core.verdict_badge(v["decision"]), "risk": v["risk_score"], "cost_usd": v["cost"],
                           "reasons": "; ".join(v["reasons"]), "adapted_problem": v["adapted_problem"]} for v in views])
    st.dataframe(table, hide_index=True, width="stretch")


def live_mode() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.error("Live mode needs ANTHROPIC_API_KEY in the environment. Use Offline mode, or restart with the key set.")
        return
    gens = core.load_generators()
    gen = st.sidebar.selectbox("Generator", gens, format_func=lambda g: f"{g['name']} ({g['model']})")
    source = st.text_area("Paste a math word problem", "Lisa has 18 more dresses than Ana. If the number of their "
                          "dresses combined is 48, how many dresses does Ana have?", height=120)
    pick = st.radio("Adapt with", list(BUTTONS), horizontal=True)
    if st.button("Run"):
        t = BUTTONS[pick]
        if t is None:
            cand = core.deterministic_rewrite(source)
            st.session_state["live"] = ({**core.live_check(source, cand, "chunked"), "adapted_problem": cand},
                                        "Deterministic split (no model)")
        else:
            with st.spinner("Calling the model..."):
                rw = core.live_rewrite(source, t, gen)
            cand = rw["adapted_problem"] or ""
            res = {**core.live_check(source, cand, t), **rw} if cand else {**rw, "decision": None}
            st.session_state["live"] = (res, f"{gen['name']} / {t} ({rw['status']})")
    if "live" in st.session_state:
        show_result(source, *st.session_state["live"])


def main() -> None:
    st.set_page_config(page_title="SafeAdapt demo", layout="wide")
    st.title("SafeAdapt: checking AI rewrites of math word problems")
    args = cli_args()
    mode = st.sidebar.radio("Mode", ["Offline", "Live"], index=0 if (args.offline or not os.environ.get("ANTHROPIC_API_KEY")) else 1)
    offline_mode(args) if mode == "Offline" else live_mode()
    st.divider()
    st.caption(CAVEAT)


main()
