# SafeAdapt-Math: status report, 2026-11-20

Run `ollama-v1` (free tier, Brown OSCAR), branch `oscar-free-tier`.

> **Read this first.** Part 1 needs no labels and is final for this run. Part 3 uses **AI stand-in labels**
> (mistral-small3.2:24b), **not human ground truth**: it is a dry run of every label-dependent method, to be
> rerun unchanged on human labels. No claim in Part 3 is reportable as a finding.

## Summary

- **What ran:** 1,044 AI rewrites plus 124 control rewrites, all on one A40 GPU in 21.5 h at $0. Each one was checked three ways: deterministic rules, an AI judge (critic), and answer recomputation. All 585 flagged rewrites were repaired and checked again.
- **Seven judges on the same rewrites:** three free local models and four paid models (OpenRouter, no data retention). Paid spend was **$11.42 of the $30 cap**.
- **Prompting is the main risk:**
  - With the realistic teacher prompt, almost every judge calls 85–99% of rewrites unsafe, because they hand the student steps.
  - With the careful prompts, judges call only 3–10% unsafe.
- **No judge is reliable enough to decide on its own:**
  - On the 54 careful-prompt rewrites whose recomputed answer changed, the best paid judge (GPT-6.1 Sol) catches 18 and the best free large judge catches 7.
  - The 3B judge "catches" 45, but only because it flags 85% of everything.
- **Calibration:** the two annotators agree on SAFE at κ 0.79. After the owner's adjudication (2026-11-20), careful-prompt rewrites are 46/50 SAFE and realistic-prompt rewrites 6/20. Rubric **v1.2** is frozen.
- **Every method runs end-to-end:** PPI, conformal control (CRC and LTT), the cascade, the critic matrix with the self-preference test, the audit game, the rewrite policy (offline and online), distillation, a trained checker and the report all run on stand-in labels (exit 0).
- **Blocking item:** human labels for the 1,062 items (about 17.3 h per annotator).

## Part 1 — Label-free results (final for this run)

### 1.1 Generation and checker decisions

- **Careful prompts** (plain and chunked, 620 rewrites):
  - Primary verifier (rules + Qwen 32B + recomputation): PASS 335, REVIEW 203, REJECT 82 (13%).
  - **Realistic prompt** (100 problems × 3 generators = 300): the rules REJECT 297 of 300.
- **Output contract:** Llama 3.2 3B returned a usable chunked rewrite for 1 of 124 problems (kept as a finding, `tier: cheap`). Qwen 14B and Gemma 12B returned 124/124.
- **Variance:** 93% of regenerations are text-identical, and the rules decision flips on 1 of 99.
- **Iterated red team:** held-out recall goes 0.73 → 0.67 over 3 rounds (n = 15 per round).
- **Conformal shift demo (synthetic):** weighted CRC holds α under a planted shift; unweighted CRC does not.

### 1.2 Seven judges on the same rewrites

Counts are the judge's own verdicts (critic `overall = UNSAFE`). The "rejected by rules or recomputation" column covers the 75 careful-prompt rewrites with a rules REJECT or a recomputation MISMATCH. "Verifier REJECT" is the full decision with that judge in the critic slot.

| Judge | Cost (main run) | Careful: unsafe (n = 620) | Of 54 answer-changed | Of 75 rejected by rules/recompute | Of 24 leak-flagged | Realistic: unsafe (n = 300) | Verifier REJECT, careful |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3 32B (free, primary) | $0 | 18 (3%) | 7 | 11 | 4 | 286 | 82 |
| Gemma 3 12B (free) | $0 | 19 (3%) | 4 | 10 | 6 | 296 | 84 |
| Llama 3.2 3B (free) | $0 | 524 (85%) | 45 | 64 | 22 | 274 | 465 |
| Claude Haiku 5.5 | $0.47 | 41 (7%) | 13 | 23 | 11 | 253 | 92 |
| Claude Sonnet 5.5 | $7.08 | 41 (7%) | 16 | 25 | 10 | 298 | 91 |
| GPT-6 Luna | $0.16 | 53 (9%) | 12 | 18 | 7 | 294 | 98 |
| GPT-6.1 Sol | $3.71 | 63 (10%) | 18 | 28 | 12 | 293 | 109 |

Reading:

- **Paid judges catch 2–3× more than the large free judges, but still miss most errors.** Even Sol misses 36 of the 54 rewrites whose answer the recomputation shows changed.
- **Price buys little past the cheapest paid tier.**
  - Haiku ($0.47) catches about as much as Sonnet ($7.08).
  - Luna ($0.16) flags more but catches fewer answer changes than Haiku.
- **Llama 3B is not a judge:** its high catch counts come from flagging 85% of everything.
- **Haiku is the most lenient on realistic-prompt scaffolding** (253 of 300 against 286–298). That matters because those rewrites hand the student steps.
- **No-verdict rates:**
  - Haiku: 15 parse failures, routed to REVIEW.
  - Llama 3B: 29.
  - All others: 0.
- **Spend:** the total, including the pilot and the reruns of rate-limited rows, is $11.42 of $30. The paid calls run with `data_collection: deny` and `zdr: true`.

## Part 2 — Calibration and rubric

- **Annotators A vs B (70 items, 10 practice problems):** SAFE κ 0.79, AC1 0.89, 93% raw. All 5 SAFE disagreements were A unsafe / B safe.
- **Adjudication:** 45 items agreed and 25 were adjudicated, giving `data/calibration/pilot/adjudicated.csv`.
  - A first AI adjudication (2026-11-19) sided with the lenient label on all 5 SAFE disagreements.
  - The owner reviewed all 30 disagreements on 2026-11-20 (`owner_review_2026-11-20.csv`, applied by `scripts/apply_owner_review.py`): 16 ACCEPT, 14 OVERRIDE. **All 5 SAFE disagreements resolve to UNSAFE**, for dropped "if" conditions, dangling "If" fragments and relevance cues.
  - Adjudicated SAFE is now **careful 46/50 (92%) and realistic 6/20 (30%)**. That equals annotator A's rates; the AI adjudication had given 50/50 and 7/20.
- **Agreement with the final labels, on SAFE** (`agreement_vs_adjudicated.md`):
  - Annotator A: κ 1.00.
  - Annotator B: κ 0.79.
  - AI stand-in (Mistral): κ 0.79, down from 1.00 against the AI adjudication.
  - The stand-in agrees with the lenient side, the same failure as the AI judges.
  - Caveat: the owner adjudicating their own disagreements favours A. The main-study adjudication is joint (A + B).
- **Rubric v1.2, frozen 2026-11-20** (`docs/annotation_guide.md`, `LABELLING_GUIDE.md`, the sheet instructions). It replaces the AI-written v1.1 rulings with the owner's:
  - "If…" is a condition. Stating it as an event is math FAIL + solvability YES; a dangling "If" bullet is ambiguity NEW.
  - A line that loses its base is ambiguity NEW.
  - Any set-up intermediate is level 3.
  - Relevance cues are level 2; Step labels are level 1. Any leak caps presentation at 2.
  - A target must keep the same agent and action.
  - "Short is not clear" for adaptation_needed.
  - The blank main sheets were re-exported with these instructions. No main-study item had been labelled.
- **Stand-in labels (Part 3) used v1.1.** This is one more reason they are a dry run only.

## Part 3 — Every method on AI stand-in labels (dry run, not ground truth)

Labels come from `data/annotations/ollama-v1-standin/` (1,062 of 1,062 items, Mistral Small 3.2 24B, $0). The full auto-generated report is `docs/results/ollama-v1-standin_report.md`, and aggregate tables are in `docs/results/ollama-v1-standin_analysis/`.

### 3.1 Outcome rates (SAFE, source-clustered bootstrap)

- **Careful prompts:** 92–100% SAFE per generator and transformation. The lowest is Llama 3B plain, 57/62 = 92% (CI 84–98%).
- **Realistic prompt:** 0–15% SAFE (Qwen 15/100, Gemma 1/100, Llama 0/100).
- **Paired comparisons (prespecified):** realistic vs constrained-chunked differs by −0.98 for Gemma and −0.82 for Qwen (Holm p < 0.001). The generator and plain-vs-chunked contrasts are not significant.

### 3.2 Methods

| Method | Result on stand-in labels |
|---|---|
| **Pooled rate, stratum-weighted** (new `src/ppi_pooled.py`, owner decision D2) | Overall unsafe rate 28.6% (classical, CI 27.4–29.7%); PPI++ 28.5% (27.4–29.6%). This replaces the invalid unweighted "all" row of `ppi.csv` (44.9% classical, 12.4% PPI). The per-stratum rows are unchanged. |
| **PPI / PPI++** (per stratum) | Under the careful prompts the strata sit at 0–8% unsafe; under the realistic prompt, 85–100%. Checker flags fire on about 55% of rewrites while few are unsafe, so they are a weak predictor and PPI is *wider* than classical: no labelling saved here. |
| **CRC** (guaranteed-PASS threshold) | At α = 0.05 it passes 53% of rewrites, with realized risk 4.0% (81% of splits under α). At α = 0.10 it passes 57%. |
| **LTT** (high-probability version) | Passes nothing at α = 0.02 or 0.05, and 35% at α = 0.10 (risk 0.5%). Too few labelled unsafe items to certify tighter levels. |
| **Cascade** | The full verifier plus human review ships 27% with **0 unsafe per 100** and sends 17% to a human. Rules plus Qwen with no human ships 44% at 0.16 unsafe per 100. |
| **Critic matrix** | All seven judges have risk AUC 0.987–0.991 against the stand-in, so the overall numbers are dominated by the easy realistic-prompt items. On the hard subset (careful prompts) the stand-in finds only 7 unsafe items, too few to rank the judges. |
| **Self-preference** (Firth bootstrap) | The same-family odds ratio is 1.08 (CI 0.25–2.31): no evidence either way. |
| **Audit game** (Stackelberg) | At a 10% audit budget the loss is 61.4 under SSE, 63.4 under the robust allocation, 64.9 under the proportional one and 90.0 under uniform audits. At 20%: 28.7, 29.6, 34.3 and 80.0. |
| **Rewrite policy** | Always-AI scores 1.00 against never-AI's 0.68 (diff +0.32, CI 0.18–0.47). The learned policy is no better than the best single arm. |
| **Repair** | 414 rewrites repaired: 259 go unsafe → safe and 0 go safe → unsafe. Mean presentation changes by −0.80. |
| **Distillation** | The logistic regression matches the rules at the same flag rate (recall 0.990 vs 0.986). |
| **Trained checker** (TF-IDF) | Weak: recall 0.14 against 0.43 for the rules at the same flag rate (n_unsafe = 7). |

### 3.3 Why Part 3 is not evidence

1. **The stand-in is itself an AI judge, and it is lenient.**
   - It calls only 7 of the 310 labelled careful-prompt rewrites unsafe, despite 54 recomputation mismatches across the careful set.
   - Every judge metric above therefore measures agreement with Mistral, not with the truth.
2. **Its perfect calibration score fell to κ 0.79 once the owner adjudicated.** It matched the lenient AI adjudication, not the owner. Do not quote κ 1.00.
3. **The pooled "all" row in `ppi.csv` is invalid** (strata are labelled at different rates). Use `ppi_pooled.csv` instead; the per-stratum rows are valid.
4. **Seven unsafe items** in the hard stratum is too few for LTT, self-preference or the trained checker to say anything.

## Part 4 — What remains (full checklist: `docs/HUMAN_ACTIONS.md`)

Done 2026-11-20 by the owner:
- calibration review (16 ACCEPT, 14 OVERRIDE);
- rubric v1.2 approved;
- flip check scored. 2 SAFE flips among the 10 regenerations whose text changed (CI 3–56%). Identical text can't flip and 93% of regenerations were identical, so that is about 1–2% of all regenerations (`variance/flip_check_scored.json`);
- decisions D1–D6.

Still blocking:
1. **Human labelling** of `data/annotations/ollama-v1/sheet_A.xlsx` and `sheet_B.xlsx` (re-exported with v1.2). Both are due **2026-12-01**: 1,062 items, 323 double-labelled, about 17.3 h per annotator, labelled independently. B must not see the owner's calibration overrides before finishing.
2. **Joint adjudication** (A + B), 2026-12-02 to 12-03. Adjudicate the strict-vs-lenient gap; don't average it away.
3. **Rerun Part 3 on human labels** with the same steps as `scripts/standin_methods.sbatch`, using `ANN=data/annotations/ollama-v1` and `--run data/outputs/ollama-v1`, plus `src/ppi_pooled.py`. Check the careful-prompt rate against the five calibration overrides before quoting it.
4. **Rotate the OpenRouter key.** Revoke the pasted key and write the new one to `~/.config/safeadapt/openrouter.env` (chmod 600). Only the owner can do this.
5. The remaining OpenRouter credit (about $18.58) stays unused (D3).

## Reproduce

- Free run: `sbatch scripts/oscar_ollama.sbatch` (job 9153208).
- Paid judges: `STAGE=main CRITICS=<name> sbatch scripts/paid_critics.sbatch` (key via `OPENROUTER_API_KEY` only).
- Stand-in labels: `scripts/ai_label.sbatch` (4 shards).
- Stand-in methods: `scripts/standin_methods.sbatch` (job 9403951, all 15 steps exit 0); pooled rate: `python src/ppi_pooled.py --run <run>`.
- Owner review: `python scripts/apply_owner_review.py data/calibration/pilot/owner_review_2026-11-20.csv`, then `python src/adjudicate.py --ann data/calibration/pilot --resolved TO_ADJUDICATE.csv`.
- Tests: `python -m unittest discover -s tests` (230 OK).
