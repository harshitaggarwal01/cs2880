# Roadmap

**Project:** SafeAdapt-Math — auditing and verifying LLM accessibility rewrites of math word problems
**Course:** Harvard COMPSCI 2880, AI for Social Impact, Fall 2026 · two-person team
**Plan version:** 1.0 (2026-11-02) · **Active branch:** `dev-phases` (merge to `main` at phase gates only)

## The phases in one table

| Phase | Scope | Dates | Exit gate |
|---|---|---|---|
| **1 · MVP** (current) | Run the dossier study end to end on real APIs: 124 frozen problems × 2 generators × {plain, chunked} + realistic teacher prompt on the 100 main problems + deterministic baseline; 3-layer verifier; one repair pass; blinded human labels; prespecified analysis; report | Nov 2 – Nov 29 | Labels adjudicated (κ/AC1 ≥ 0.7 on SAFE); `phase1_report.md` generated; ledger ≤ $30 |
| **2 · Methods** | Four offline methods on Phase-1 outputs: conformal risk control (guaranteed PASS), cost-aware cascade, prediction-powered inference, offline contextual-bandit policy; red-team robustness as stretch | Coded Nov 7–20 on synthetic data; run on real labels Nov 23–29 | Tests green; `analysis/<module>.csv`; method notes; one figure each in the report |
| **3 · Real-world** | External-tool audit harness (manual capture + loader), teacher-prompt survey instrument, Streamlit demo, distilled free verifier layer (stretch) | Nov 10 – Dec 1 | Demo runs offline from the main run; template + loader tested; protocol and survey docs reviewed |
| **4 · Write-up & release** | Final report, reproducibility doc, data-release packaging, failure gallery, handoffs | Nov 30 – Dec 5 | Report complete; `make release` reproduces checksums; all tests green |

Detailed phase docs: [PHASE1.md](PHASE1.md) · [PHASE2.md](PHASE2.md) · [PHASE3.md](PHASE3.md) · [PHASE4.md](PHASE4.md). Handoffs: [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md), `HANDOFF_PHASE<n>.md`.

## Schedule against the check-ins

| Dates | What exists by then | Check-in |
|---|---|---|
| Nov 2–3 | Plan docs; Phase-1 gaps fixed; calibration sheets; orchestrator passes mock end-to-end; Anthropic-only config | **Check-in 1 (Nov 3):** show the pilot, the plan, and the running pipeline |
| Nov 3–5 | Both teammates relabel the 70 pilot outputs blind → agreement → rubric v1 frozen; real `--pilot` on the dev set; config frozen; GSM-IC go/no-go | |
| Nov 5–7 | Main generation, realistic condition, baseline, verify, repair, re-verify, sheets, ledger (API-only, blind to labels) | |
| Nov 7–10 | Annotation started; Phase-2 modules coded and unit-tested on synthetic data; variance run | **Check-in 2 (~Nov 10):** real outputs, first labels, method notes |
| Nov 10–22 | Annotation: A labels everything, B labels the 30% stratified subset; agreement before adjudication | |
| Nov 23–29 | Adjudication; evaluate + report; Phase-2 methods on real labels; demo in offline mode | |
| Nov 30 – Dec 5 | Final report, release packaging, handoffs | **Final** |

## Why the order is this way

- **Human annotation is the bottleneck** (~16 h per person). Everything the sheets need — generation, verification, repair — is API-only and blind to labels, so it runs in the first four days. Phase-2 code is written against synthetic data while labels are being produced, then re-run on the real labels.
- **Layer ablations, the cascade and the conformal calibration are computed offline** from stored verifier fields. No extra API calls.
- **The realistic teacher prompt is co-primary** (RQ2). The pilot showed that is where leakage lives.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-16 | Realistic teacher prompt promoted from side ablation to co-primary condition on all 100 main problems | Pilot: 13/20 unsafe under the realistic prompt vs 0/50 under constrained prompts |
| 2026-10-16 | Sample frozen: 10 dev (GSM8K train) + 100 main (GSM8K test, stratified) + 12 ASDiv + 12 GSM1K row ids; seed 2880 | Resolves the 124/135 inconsistency in the earlier documents |
| 2026-11-02 | **Anthropic-only Phase-1 run first (`anthropic-v1`)**: generators `claude-haiku-5-5` + `claude-sonnet-5-5`, critic/extractor `claude-opus-5-5` | Only an Anthropic key is available. Same-family caveat (judge favours its own family; Panickssery et al. 2024, Kim et al. 2025) is disclosed. The cross-family run `main-v1` (gpt-6-luna + gemini-3.8-flash, Sonnet critic) is a config swap when keys arrive; together they give a 4-generator comparison |
| 2026-11-02 | GSM-IC distractor set optional, default off; decide before main generation | GSM8K has few irrelevant details, so relevance leakage would be under-observed; adds ~48 annotation items |
| 2026-11-02 | All development on `dev-phases`; commits authored by the project owner only | Keeps `main` at the check-in state; attribution policy |
| 2026-11-02 | Cheaper models implement, orchestration reviews; statistical modules (conformal/LTT, PPI, clustered logit) get a second review before being declared done | Cost control without lowering the bar on the parts a reviewer will check |

## Status (update at each gate)

| Item | Status |
|---|---|
| Plan docs, Makefile, CHANGELOG, Anthropic config | in progress (Nov 2) |
| Phase-1 gap fixes, ledger, orchestrator, calibration, evaluate extensions, report, variance, GSM-IC fetch | in progress (Nov 2) |
| Real pilot with Anthropic key | blocked: `ANTHROPIC_API_KEY` not yet in the environment |
| Rubric v1 frozen | pending calibration relabel |
| Main generation | pending key + rubric |
| Phase 2 modules | pending |
| Phase 3 | pending |
| Phase 4 | pending |

## Budget

| Item | Estimate |
|---|---|
| API, Anthropic-only run (≈700 generations, ≈900 critic calls on Opus, ≈1,000 extractions, ≈200 repairs) | ≈ $20; plan for $30 |
| API, cross-family run when keys arrive | ≈ $13 |
| Human annotation | ≈ 32 h total, ≈ 16 h per person |

If over budget, scope down in this order: external sets to 6 + 6 → realistic condition to 60 problems → drop the program layer.
