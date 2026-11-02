# Phase 3 — Real-world: tools teachers use, teachers' own prompts, a demo

**Status:** code done (Nov 2); tool collection and CUHS determination pending · **Owner:** harness by Person 1, collection by Person 2 · **Dates:** Nov 10 – Dec 1 · **Effort:** ≈ 20 h

## Objective

Move from "two API models" toward the systems and people in the actual workflow, without recruiting students: audit real classroom tools, learn how teachers actually phrase the request, and show the pipeline working end to end in a demo.

## 3A External-tool audit harness

- **What:** a manual-capture protocol and a loader that maps captured outputs into the generations schema, so `verify`, `evaluate`, `report` and `ppi` run on them unchanged.
- **Files:** `src/import_external.py` (`load_template(csv)`, `to_generations(rows, run_id="external-v1")` → generator = tool name, transformation = "external"); `data/external/TEMPLATE.csv` with columns `external_id, tool, tool_version_or_date, ui_path, prompt_used, source_id, captured_by, captured_at, raw_response, adapted_problem, tos_checked, notes`; `docs/external_collection_protocol.md`.
- **Protocol essentials:** manual capture only (no scraping or automation); one person captures, the other spot-checks 10%; each tool's terms of service read and the decision recorded in `tos_checked`; captured tool outputs are **not redistributed** (kept local; only labels and aggregate rates are released); the same frozen source problems are used so comparisons stay paired.
- **Labels:** PPI (Phase 2C) keeps human labels to ≈ 30 per tool with the verifier as the predictor on the rest.
- **Candidate tools:** Diffit, MagicSchool, Khanmigo teacher tools, and the consumer ChatGPT/Gemini interfaces with the realistic prompt. Final list after the ToS check.

## 3B Teacher prompts

- **What:** a short survey instrument asking teachers and special-education staff how they actually ask AI tools to simplify a problem, plus a loader that turns responses into additional realistic prompt variants.
- **Files:** `docs/survey/teacher_prompt_survey.md` (instrument, consent text, note on Harvard CUHS determination — likely exempt as a survey of adults about practice, but the determination must come before collection); `src/realistic_prompts.py` (`load_survey(csv)`, `dedupe_cluster(prompts)`, `write_prompt_file(prompts, version)` → `prompts/realistic_v2.txt`).
- **This semester:** instrument and code only. Collection happens if the determination arrives in time; otherwise it is future work.

## 3C Demo

- **What:** `demo/app.py` (Streamlit). Paste a problem → policy choice (Phase 2D) → rewrite (or deterministic split) → verifier verdict with reasons → risk score and guarantee level (Phase 2A) → cost. **Offline mode** reads `data/outputs/<run_id>/` so it runs with no key; live mode uses `llm.make_provider`.
- **Reuses:** `deterministic_checks.check`, `verify.decide`, `baseline.render`, `conformal.risk_score`, `policy.direct_policy`, `ledger.price_call`.

## 3D Distilled free layer (stretch)

- **What:** a scikit-learn classifier on deterministic features (flag one-hots, counts, readability deltas) with leave-source-out CV, to see how much of the critic's recall a free layer recovers at a matched review rate. `src/distill.py` (`features(verify_row)`, `fit_eval(df, labels, groups)`).
- **Cite:** Hinton, Vinyals & Dean (2015) *Distilling the Knowledge in a Neural Network*; Zhao, Knežević & Käser (2026) for the rule-then-judge pattern.

## Ethics notes

- No students, no student data. External-tool captures contain only the frozen public problems and the tool's output.
- The teacher survey collects practice, not personal data beyond role; consent text included; no collection before the CUHS determination.
- Tool outputs are evidence about products, reported in aggregate with the capture protocol attached, not as a takedown.

## Exit gate

Template and loader tested (`test_external_rows_pass_verify_det`); protocol and survey docs reviewed by both; demo runs offline from the main run (`test_demo_offline_index_loads`).
