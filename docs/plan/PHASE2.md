# Phase 2 — Methods: what makes this more than a better prompt

**Status:** code done with synthetic tests (Nov 2); statistical review done; real-label runs pending · **Owner:** code by Person 1, review by both · **Dates:** coded Nov 7–20 on synthetic data; run on real labels Nov 23–29 · **Effort:** ≈ 40 h

## Objective

Turn the verifier and the comparison into things a school or vendor can rely on: a PASS with a stated guarantee, a checking order with known cost, failure rates that stay trustworthy with few human labels, and a readable policy for when to use AI at all. All four run **offline** on Phase-1 outputs; no new API calls except the stretch item.

## Entry criteria

- Phase-1 verify outputs with all three layers stored per row (`deterministic`, `critic`, `program`, `extract_meta`).
- `ledger.csv` (per-item cost).
- Adjudicated labels for the real run (synthetic data until then).

## Modules

### 2A `src/conformal.py` — risk-controlled PASS

- **Claim it supports:** "Of the rewrites we PASS, at most α are unsafe" (α chosen by the user, e.g. 5%), with a finite-sample guarantee under exchangeability of source problems.
- **Risk score** (monotone in evidence of harm): det REJECT (5) > critic UNSAFE (4) > program MISMATCH (3) > critic UNSURE/missing or program UNCHECKABLE (2) > REVIEW flags only (1) > clean (0), plus 0.1 × number of flags (capped). Optional learned score from the Phase-1 logistic model.
- **Two calibrations:** Conformal Risk Control on the monotone loss "fraction of a source's outputs unsafely passed" (`crc_threshold`), and Learn-then-Test fixed-sequence testing for the conditional target P(unsafe | PASS) ≤ α (`ltt_threshold`). Calibration/test split by `source_id`; the guarantee curve (α vs review rate vs realized unsafe-pass rate) averaged over repeated splits.
- **Output:** `analysis/conformal.csv`, one figure.
- **Tests:** empirical risk ≤ α on synthetic data; score monotone in layers; LTT stops at the first failing threshold.
- **Cite:** Angelopoulos, Bates, Fisch, Lei & Schuster (2024) *Conformal Risk Control*, ICLR; Angelopoulos, Bates, Candès, Jordan & Lei (2021) *Learn then Test*, arXiv:2110.01052; Bates, Angelopoulos, Lei, Malik & Jordan (2021) *Distribution-free, risk-controlling prediction sets*, JACM 68(6); Vovk, Gammerman & Shafer (2005).

### 2B `src/cascade.py` — cost-aware checking order

- **Decision:** det (free) → stop if confident; else critic + program (≈ 1¢) → stop if confident; else human (minutes). Policy space is finite (which det/critic outcomes stop at each stage); enumerate it.
- **Objective:** unsafe shipped + λ · USD + μ · human minutes, per 100 items; report the Pareto frontier rather than one λ, μ.
- **Inputs:** stored verifier fields; `ledger.per_item_cost`; `minutes_per_review` from config.
- **Output:** `analysis/cascade.csv`, one figure.
- **Tests:** policies distinct; frontier has no dominated point; det-only policy reproduces `verifier_metrics`.
- **Cite:** Viola & Jones (2001) CVPR; Chen, Zaharia & Zou (2023) *FrugalGPT*; Madras, Pitassi & Zemel (2018) *Predict Responsibly*, NeurIPS; Mozannar & Sontag (2020) ICML.

### 2C `src/ppi.py` — prediction-powered inference

- **Claim it supports:** unbiased failure-rate estimates with narrower intervals by combining a small human-labelled subset with critic/verifier labels on everything.
- **Estimators:** classical mean; PPI mean; PPI++ with tuned λ. Intervals by source-cluster bootstrap (not asymptotic) to respect clustering.
- **Output:** `analysis/ppi.csv` (CI width vs labelled fraction, per condition), one figure. Also used in Phase 3A to keep external-tool labels to ≈ 30 per tool.
- **Tests:** unbiased under a biased predictor; narrower when the predictor is accurate; λ bounded.
- **Cite:** Angelopoulos, Bates, Fannjiang, Jordan & Zrnic (2023) *Prediction-powered inference*, Science 382:669–674; Angelopoulos, Duchi & Zrnic (2023) *PPI++*, arXiv:2311.01453; Zrnic & Candès (2024) *Cross-prediction-powered inference*, PNAS.

### 2D `src/policy.py` — offline contextual-bandit policy

- **Arms:** deterministic split; generator × {plain, chunked}; each with "+ one repair" variants. **Context:** `common.tags`, step bucket, length tercile, number of quantities. **Reward:** SAFE_AND_USEFUL − λ · cost.
- **Because every arm is observed for every source** (full-information logs), the direct method is exact: per-context argmax with leave-source-out evaluation, compared against "always AI" and "never AI" with bootstrap CIs. A Thompson-sampling replay over random source orders shows cumulative regret vs the best fixed arm, as a bridge to a live deployment.
- **Output:** a readable depth-2 policy tree; `analysis/policy.csv`; one figure.
- **Tests:** oracle recovers a planted best arm; no leakage in leave-source-out; sublinear regret on synthetic data.
- **Cite:** Li, Chu, Langford & Schapire (2010) WWW; Dudík, Langford & Li (2011) ICML; Agrawal & Goyal (2013) AISTATS; Chapelle & Li (2011) NeurIPS; Russo, Van Roy, Kazerouni, Osband & Wen (2018) *A Tutorial on Thompson Sampling*.

### 2E `src/redteam.py` + `prompts/attacker_v1.txt` — robustness (stretch, ≈ $2)

- An attacker prompt rewrites 50 main sources to leak *subtly* while passing the det layer; measure verifier recall under attack; blind-label 30 to confirm they leak. Outputs quarantined under `redteam/` and never enter main sheets.
- **Cite:** Perez et al. (2022) *Red Teaming Language Models with Language Models*, EMNLP; Ganguli et al. (2022) arXiv:2209.07858; Zhao, Knežević & Käser (2026) ACL.

## Review gate before "done" (passed Nov 2; see CHANGELOG)

The statistical modules (2A, 2C, and the clustered logit from Phase 1) get a second review focused on correctness of the guarantee and the estimators, before results are quoted. Checklist: exchangeability unit = source; calibration/test split by source; loss monotone in the threshold; PPI rectifier uses the same predictor on labelled and unlabelled items; intervals respect clustering.

## Exit gate

Each module: tests green; `analysis/<module>.csv` from the real run; `docs/methods/<module>.md` with the citations above; one figure in the report. Decisions: 2A/2B/2C always; 2D only if at least two arms differ on SAFE_AND_USEFUL; 2E only if labels are done by Nov 22.
