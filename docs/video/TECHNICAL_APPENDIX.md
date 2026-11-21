# SafeAdapt-Math — Technical appendix (to accompany the Nov 23 video)

Harshit Aggarwal · Cathy Liu · CS 2880 · branch `oscar-free-tier` of `harshitaggarwal01/cs2880`

How to read this:
- Every number states its n.
- **Checker** = automated decisions on the main run (`ollama-v1`).
- **Human** = adjudicated labels on the 70 calibration items (10 practice problems).
- Main-study human labels (1,062 items) are due 2026-12-01. Results that depend on them are listed in A7 with status only, not values.

## A1. Problem and definitions
- **Task:** given an original math word problem *x* and an AI rewrite *x′*, decide whether *x′* is an **accommodation** (same task) or a **modification**.
- **SAFE** (derived from human labels):
  - math fidelity PASS;
  - target (the question) preserved;
  - solvability unchanged;
  - no new ambiguity;
  - leakage level 0.
- **Leakage levels:**
  - 1: STRUCTURE (solution-order step labels);
  - 2: STEPS / OPERATION / RELEVANCE;
  - 3: INTERMEDIATE / ANSWER (any value, range or expression the student had to set up).
- **Rubric v1.2** (frozen 2026-11-20, `docs/annotation_guide.md`):
  - "If…" is a condition. Stating it as an event is math FAIL + solvability YES; a dangling "If" bullet is ambiguity NEW.
  - A line that loses its base is ambiguity NEW.
  - Relevance cues are level 2.
  - Any leak caps presentation at 2.
  - A target must keep the same agent and action.

## A2. Design (frozen before any study data was generated)
- **Problems:** 124 study problems, stratified by solution steps × relational cues (`data/frozen/`):
  - GSM8K test (100);
  - ASDiv (12);
  - GSM1K (12; contamination control).
- 10 separate practice problems are used for tuning and calibration only.
- **Conditions:**
  - plain language;
  - chunked;
  - the realistic teacher prompt (first 100 problems);
  - a non-AI sentence splitter (control).
- **Rewriters (free, open weights, Ollama on one OSCAR GPU):** Qwen 14B, Gemma 3 12B and Llama 3.2 3B. Total: 1,044 rewrites + 124 control rewrites.
- **Checker:**
  - deterministic rules (v1.1.1);
  - AI critic (primary: Qwen3 32B);
  - program recomputation (Qwen3 32B extractor).
  - Decision rule:
    - **REJECT** on a rule reject, a critic UNSAFE with a math or leak code, or an answer MISMATCH;
    - **REVIEW** on soft flags, critic UNSURE, or an uncheckable program;
    - **PASS** otherwise.
- **Judges compared on the same rewrites:**
  - free: Qwen3 32B, Gemma 3 12B, Llama 3.2 3B;
  - paid, via OpenRouter with `data_collection: deny` and `zdr: true`: Claude Haiku 5.5, Claude Sonnet 5.5, GPT-6 Luna, GPT-6.1 Sol.
- **Labelling plan (lean, prespecified, seed 2880):**
  - 1,597 items, of which 1,062 are labelled and 323 double-labelled;
  - realistic prompt 100%, careful 50% (paired across models), control 30%;
  - about 693 items and about 17.3 h per annotator.

## A3. Main run: checker decisions (n = 1,044 AI rewrites; automated, not human labels)

| Rewriter | Prompt | Outputs | Unusable format | Checked | PASS | REVIEW | REJECT | Answer MATCH | MISMATCH | Leak flag |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen 14B | plain | 124 | 0 | 124 | 87 | 26 | 11 | 108 | 5 | 5 |
| Qwen 14B | chunked | 124 | 0 | 124 | 51 | 61 | 12 | 103 | 11 | 0 |
| Qwen 14B | realistic | 100 | 0 | 100 | 0 | 3 | 97 | 76 | 16 | 97 |
| Gemma 12B | plain | 124 | 0 | 124 | 58 | 47 | 19 | 101 | 14 | 5 |
| Gemma 12B | chunked | 124 | 0 | 124 | 57 | 44 | 23 | 97 | 16 | 7 |
| Gemma 12B | realistic | 100 | 0 | 100 | 0 | 0 | 100 | 74 | 18 | 100 |
| Llama 3B | plain | 124 | 1 | 123 | 81 | 25 | 17 | 104 | 8 | 6 |
| Llama 3B | chunked | 124 | **123** | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| Llama 3B | realistic | 100 | 0 | 100 | 0 | 0 | 100 | 68 | 24 | 100 |
| Sentence splitter (control) | — | 124 | 0 | 124 | 116 | 8 | **0** | — | — | 0 |

- **Careful prompts** (n = 620): PASS 335 (54%), REVIEW 203 (33%), REJECT 82 (13%).
  - By dataset: GSM8K 67/499 (13%), ASDiv 5/60 (8%), GSM1K 10/61 (16%).
  - Program check: 514 MATCH, 54 MISMATCH, 52 uncheckable.
- **Realistic prompt** (n = 300): rules REJECT 297. The rewrites add:
  - an operation (266);
  - a derived value (260);
  - equations or symbols (239);
  - numbered steps (201);
  - a quantity (95).
- **Repair** of flagged rewrites: 585 repaired and rechecked.
- **Variance:**
  - 93% of regenerations are text-identical;
  - the rules decision flips on 1 of 99;
  - human SAFE flipped on 2 of the 10 regenerations whose text changed (Clopper–Pearson 95% CI 3–56%).

## A4. Seven judges on the same rewrites (label-free)

| Judge | Cost, main run | Careful: unsafe (n = 620) | Of 54 answer-changed | Of 75 rejected by rules or recompute | Of 24 leak-flagged | Realistic: unsafe (n = 300) | No verdict |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3 32B (free, primary) | $0 | 18 (3%) | 7 | 11 | 4 | 286 | 0 |
| Gemma 3 12B (free) | $0 | 19 (3%) | 4 | 10 | 6 | 296 | 0 |
| Llama 3.2 3B (free) | $0 | 524 (85%) | 45 | 64 | 22 | 274 | 29 |
| Claude Haiku 5.5 | $0.47 | 41 (7%) | 13 | 23 | 11 | 253 | 15 |
| Claude Sonnet 5.5 | $7.08 | 41 (7%) | 16 | 25 | 10 | 298 | 0 |
| GPT-6 Luna | $0.16 | 53 (9%) | 12 | 18 | 7 | 294 | 0 |
| GPT-6.1 Sol | $3.71 | 63 (10%) | 18 | 28 | 12 | 293 | 0 |

- Qwen 32B and Gemma 12B agree on only 4 of the rewrites they flag.
- Total paid spend, including the pilot and retries, was $11.42 of a $30 cap.
- The small Qwen 4B critic was about 25× slower than the 32B (about 200 s vs 8.5 s per verdict).

## A5. Calibration (human, n = 70 rewrites of 10 practice problems)

**Agreement, A vs B, before adjudication:**

| Label | κ | Gwet AC1 |
|---|---:|---:|
| SAFE | 0.79 | 0.89 |
| Leakage level | 0.95 | 0.97 |
| Leakage type | 0.92 | 0.97 |
| Abstention appropriate | 0.89 | 0.99 |
| Ambiguity | 0.62 | 0.94 |
| Math fidelity | 0 (prevalence effect) | 0.90 |
| Presentation | 0.50 | 0.53 |
| Adaptation needed | 0.13 | 0.46 |

**Adjudication:**
- 45 items agreed; 30 disagreements went to adjudication.
  - A first AI adjudicator sided with the lenient label on all 5 SAFE disagreements.
  - The owner then reviewed all 30: 16 ACCEPT, 14 OVERRIDE. All 5 SAFE disagreements became UNSAFE.
- Final SAFE: careful prompts 46/50 (92%); realistic prompt 6/20 (30%).

**Agreement with the final labels, on SAFE:**
- Annotator A: κ 1.00. This is partly by construction: the owner adjudicated.
- Annotator B: κ 0.79.
- AI labeller (Mistral Small 3.2 24B, rubric v1.1): κ 0.79. Against the earlier AI adjudication it scored κ 1.00.

**Interpretation:** the disputed cases are dropped "if" conditions, dangling fragments and relevance cues. AI reads these leniently.

## A6. Robustness and methods with label-free results
- **Iterated red-team** (an attacker learns to leak while passing the checker): held-out recall goes 0.73 → 0.67 over 3 rounds (n = 15 per round).
- **Conformal under distribution shift** (synthetic, planted shift): weighted CRC holds α; unweighted CRC does not.
- **Unsupervised critic ensemble** (Dawid–Skene-style posterior): `data/outputs/ollama-v1/analysis/critic_ensemble*.csv`.

## A7. Methods awaiting human labels (built, unit-tested, and run end to end on an AI stand-in labelling)
These need the human labels before they produce final values:
- **Outcome rates per condition:** source-clustered bootstrap; prespecified McNemar families with Holm correction.
- **PPI / PPI++ failure rates:** per stratum, plus a **stratum-weighted pooled rate** (`src/ppi_pooled.py`). The unweighted pooled row is invalid under unequal labelling fractions.
- **Conformal risk control and Learn-then-Test:** the guaranteed-PASS threshold (α = 0.02 / 0.05 / 0.10).
- **Cost-aware cascade:** the Pareto frontier of unsafe-shipped vs teacher minutes vs dollars, per judge.
- **Critic matrix:** each judge's recall and precision against human labels; a self-preference test (Firth logistic, bootstrap).
- **Stackelberg audit game:** the district's audit allocation across tool × prompt.
- **Rewrite policy:** offline and online contextual bandit with off-policy evaluation, including "don't use AI".
- **Distillation, and a small trained checker.**

Status:
- Every step ran cleanly on stand-in labels (job 9403951).
- **No stand-in value is reported as a result:** the stand-in agrees with the lenient human (A5).
- The final values come from rerunning the same commands on the human labels after joint adjudication (Dec 2–3).

## A8. Cost and compute
- **Free tier:** one A40 GPU for 21.5 h of wall time; $0; 6,483 local model calls. Generation took about 1.9 GPU-hours. The critic plus extraction take about 36–44 s per rewrite.
- **Teacher time:** one REVIEW is about 1.5 minutes. With careful prompts a third of rewrites go to REVIEW, about 10 minutes per 20 rewrites.

## A9. Ethics, limitations, reproducibility
- **Ethics** (summary of video slide 13):
  - the risk of false reassurance;
  - the line is a value judgement;
  - over-blocking also hurts students;
  - cheaper models fail more, so there is an equity gap;
  - the red team is dual-use.
  - Mitigations: stated error guarantees, routing to a person, local free models, and human final authority.
- **Limitations:**
  - human labels so far cover 70 practice items;
  - 8% of rewrites can't be checked by recomputation;
  - 3 rewriters, English only, GSM-style arithmetic;
  - two annotators, not special-education teachers;
  - no student outcomes.
- **Reproducibility:**
  - Frozen config: `config.ollama.yaml` (`run_id: ollama-v1`).
  - Paid judges: `config.ollama-paid.yaml`.
  - Jobs: `scripts/oscar_ollama.sbatch`, `scripts/paid_critics.sbatch`, `scripts/standin_methods.sbatch`.
  - 230 unit tests.
  - Full status: `docs/results/STATUS_REPORT_2026-11-20.md`.
  - What humans still do: `docs/HUMAN_ACTIONS.md`.
