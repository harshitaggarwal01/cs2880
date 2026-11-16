# SafeAdapt-Math — Nov 16 presentation (11 slides + backup, ~12 min)

> **Status (Nov 16, 12:45 EST):** the free-model main run on OSCAR has generated and checked all 1,044 AI rewrites. Repairs and the extra methods are still running (slide 9).
> **Check before presenting:** B-vs-A on SAFE (13 / 5 / 0 / 52) is cell-for-cell the same table as the AI-labeller-vs-A comparison. Confirm that B's SAFE labels are not the AI's: `python src/calibrate.py --compare-preliminary data/calibration/pilot/sheet_B.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv` prints aggregate agreement only. If they match exactly, drop the "Humans" bullet on slide 8.
> **Accuracy rules:** every number states its n. "Preliminary" = human labels not yet adjudicated, 10 practice problems. OSCAR main-run numbers are automated checker decisions, not human labels.

---

## 1 · Title (15 s)
**SafeAdapt-Math: When "easier to read" becomes "easier to solve"**
- Auditing AI accessibility rewrites of math word problems
- Harshit Aggarwal · Cathy [surname] · CS 2880 AI for Social Impact · Nov 16, 2026

---

## 2 · Motivation (1 min)
**Teachers already use AI to adapt assessments for students with disabilities. No one checks what it changes.**
- Students with IEPs and 504 plans are legally owed *accommodations*: the same task, made accessible (plain language, chunking).
- A *modification* (an easier task) is a different legal and educational category. It changes what the grade means.
- Teachers are told to use AI for this, with no tool that tells them when a rewrite crossed the line.
- The failure is invisible. A rewrite that hands over the steps looks *more* helpful, not less.
- The harm lands on the students the accommodation was meant to protect: grades that overstate mastery, gaps found late.

**Notes:** The danger isn't a wrong answer. It's a rewrite that quietly does the thinking for the student.

---

## 3 · Problem statement (45 s)
**Can we tell, automatically and with a guarantee, whether an AI rewrite of a math problem kept the same task?**
- **Same task:** same numbers, same relations, same question (fidelity).
- **Nothing given away:** no added steps, operations or precomputed values (no leakage).
- Three questions:
  1. **How often** do accessibility rewrites change the task, with careful prompts and with the prompts teachers actually type?
  2. **Can a checker catch** the unsafe ones without flooding teachers with false alarms?
  3. **Can schools that can't pay** for frontier models get the same protection?

---

## 4 · Approach at a glance (45 s)
**Measure the failure, build a layered checker, then turn its verdicts into decisions with statistical guarantees.**
- **Measure:** real problems → AI rewrites under three prompts → blind human labels as ground truth.
- **Check:** free rules → AI reviewer → re-derive the answer as a program → PASS / REVIEW / REJECT.
- **Decide:** guaranteed-safe PASS, cost-aware ordering of checks, label-efficient rates, where to audit.
- Everything is prespecified and frozen before any study data was generated.

*Visual:* three boxes, Measure → Check → Decide.

---

## 5 · Approach: the measurement (1 min)
**A frozen, stratified study with blind human ground truth**
- **124 study problems** (GSM8K test, ASDiv, GSM1K), stratified by solution steps × relational cues. 10 separate practice problems are used for tuning only.
- **Conditions:**
  - plain language;
  - chunked;
  - the *realistic* teacher prompt ("make this easier for a student with ADHD or dyslexia");
  - a non-AI baseline that only splits sentences.
- **Rewriters:** three free open-weight models on Brown's GPU cluster (Qwen 14B, Gemma 12B, Llama 3B), giving **1,044 rewrites** at $0. Claude and GPT models were used in the pilot and come back as judges.
- **Three-layer checker:**
  - **Rules (free):** numbers, relations, quantifiers, leaked operations and derived values.
  - **AI critic:** rubric-based verdict with cited evidence.
  - **Program check:** extract both versions as programs and recompute; a different answer means a REJECT.
- **Labels:** two annotators, blind; rubric calibrated first (target κ/AC1 ≥ 0.7).
  - **Calibration done: SAFE κ 0.79, AC1 0.89, 93% raw (n = 70).**
  - Two labels are being revised before the rubric freeze: "adaptation needed" (AC1 0.46) and presentation (AC1 0.53).
  - Then about 850 items to label, about 14 h each.

---

## 6 · Approach: from checker to decision (1 min)
**A checker alone isn't a policy. These methods make it one (all coded and tested).**
- **Guaranteed PASS** (conformal risk control / Learn-then-Test): "of what we pass, at most α is unsafe, with probability ≥ 1−δ".
- **Fewer labels** (prediction-powered inference): unbiased failure rates from a labelled subset plus checker verdicts on everything.
- **Cost-aware cascade:** cheapest order of rules → small model → strong model → human for a target safety level; we report the Pareto frontier.
- **Where to audit** (Stackelberg audit game): spread a district's limited audit budget across tools and conditions.
- **Which rewrite to use** (contextual bandit): per problem type, including "don't use AI".
- **Red-team:** an attacker that learns to leak while passing the checker, measuring recall under attack.

**Notes:** This is what turns prompt engineering into a deployable safeguard: guarantees, budgets, and the security-games framing from this course.

---

## 7 · Result 1: the prompt teachers actually type breaks the task (1.5 min)
**Careful prompts: 13% rejected. The prompt teachers type: 99% rejected. Human labels agree in direction.**

**Main run: 3 free rewriters, 124 study problems (automated checker decisions)**

| Prompt | Rewrites checked | REJECT | Leak flagged | Recomputed answer differs |
|---|---|---|---|---|
| Non-AI sentence splitter (control) | 124 | **0** | 0 | — |
| Careful: plain | 371 | 47 (13%) | 16 | 27 |
| Careful: chunked | 249* | 35 (14%) | 7 | 27 |
| **Realistic teacher prompt** | **300** | **297 (99%)** | **297** | **58** |

- **What the realistic prompt adds**, out of 300 rewrites:
  - the operation to use (266);
  - precomputed intermediate values (260);
  - equations or symbols (239);
  - numbered solution steps (201).
- **Human labels, preliminary (practice problems, annotator A):**
  - careful prompts: 92% safe (46/50, CI 81–97%);
  - realistic prompt: 30% safe (6/20, CI 15–52%).
  - Claude Opus with the realistic prompt: 0/10 safe. It added "steps to try" to every rewrite.
- **What it means:** the risk lives in how teachers ask, not in model capability. A more helpful model is more eager to scaffold, and scaffolding is exactly the modification we're trying to catch. A safeguard can't rely on prompt discipline. It has to check the output.

*Footnote:* \*Llama 3B returned a usable chunked rewrite for 1 of 124 problems; the rest is Qwen and Gemma. The realistic prompt ran on the first 100 study problems. The control's 8 REVIEWs are formatting notes, so the rules raise no false REJECTs on a non-AI rewrite. Human labels: 70 outputs on 10 practice problems, not yet adjudicated.

---

## 8 · Result 2: no single judge can be trusted with the line (1.5 min)
**Large AI judges miss what recomputation catches, small ones flag everything, and judges disagree with each other.**

| Critic (620 careful-prompt rewrites) | Calls unsafe | Catches, of 54 whose recomputed answer differs | Catches, of 75 rejected by rules or recomputation |
|---|---|---|---|
| Qwen 32B (free, primary) | 18 (3%) | **7** | 11 |
| Gemma 12B (free) | 19 (3%) | **4** | 10 |
| Llama 3B (free) | 524 (85%) | 45 | 64 |

- Qwen 32B and Gemma 12B agree on only **4** of the rewrites they flag.
- The paid judges on 50 practice rewrites (3¢):
  - Claude Haiku 5.5: unsafe on 5.
  - GPT-6 Luna: unsafe on 6.
  - They agree on **1**.
- **The example that matters** (Llama 3B rewrite, plain): *"The remaining floors are each 3 feet taller."* → *"The remaining **10** stories are **15** feet tall each."*
  - Qwen 32B and Gemma 12B: SAFE.
  - Claude Haiku and GPT-6 Luna: UNSAFE.
  - The free rule: **REJECT**, because two intermediate values were computed for the student.
- **Humans:** two blind annotators agree on SAFE at κ 0.79 (93%, n = 70). Every disagreement runs one way (A unsafe, B safe; 5 of A's 18). The line is genuinely hard.
- **What it means:** an AI verdict is a signal, not a decision. Rules and recomputation can't be talked into "looks fine". Adjudicated human labels stay the ground truth, and AI verdicts enter only as a bias-corrected predictor (PPI).

*Footnote:* Main-run numbers are checker decisions, not human labels. Qwen 32B does flag blatant step-giving: 286 of 300 realistic-prompt rewrites. What it misses is subtle.

---

## 9 · Where we are: done, running, next (45 s)
**Done**
- Frozen design and code: 225 tests; checker tuned on practice problems only.
- Rubric calibration: both annotators, 70 items, SAFE κ 0.79.
- Free main run on one OSCAR GPU, $0:
  - 1,044 AI rewrites plus 124 control rewrites;
  - every one checked by the rules, the Qwen 32B critic and answer recomputation;
  - the Gemma and Llama critics on all 620 careful-prompt rewrites.
- Paid-judge pilot: Claude Haiku and GPT-6 Luna on 50 practice rewrites, $0.03.

**Running now** (one GPU job, about 16.5 h in)
- Gemma and Llama critics on the realistic-prompt set: about 2 pm.
- Repair of rejected rewrites and recheck (about 380): about 6 pm.
- Labelling sheets, then red-team (3 rounds), critic ensemble, variance check, conformal shift demo and report: tonight.

**Pending**
- Claude Sonnet and GPT-6.1 Sol judges, then all four paid judges on the main run. About $17 at most, under a $30 cap. Waiting on API credit.
- Adjudicate calibration disagreements, revise two labels, freeze the rubric.

**Next 2 weeks**
- Blind labelling: about 850 items, about 14 h per annotator.
- Then on real labels: the guaranteed-PASS threshold, PPI failure rates, the cascade's cost–safety frontier, the audit game, and the rewrite policy.
- Final report.

---

## 10 · What we want feedback on (45 s)
**Early signal: models a school can afford break the output contract.**
- Usable chunked rewrites:

  | Model | Practice | Main study |
  |---|---|---|
  | Qwen 14B | 10/10 | 124/124 |
  | Gemma 12B | 10/10 | 124/124 |
  | **Llama 3B** | **0/10** | **1/124** |
  | Mistral 7B | 8/10 | |
  | Gemma 4B | 10/10 | |
  | Phi-3 3.8B | 0/10 | |
  | Qwen 4B | 0/10 | |

  Qwen 4B reasons until it is cut off.
- A small model isn't automatically cheap: the Qwen 4B critic was about 25× slower than the 32B (about 200 s vs 8.5 s per verdict).
- **Questions for you:**
  1. Is "accommodation vs modification" the right operational line for leakage?
  2. Which deployment framing is most useful: teacher tool, district audit, or vendor certification?
  3. How should we report a cheap model whose outputs often can't be checked at all?

---

## 11 · Summary (45 s)
- **The failure is real and large:** with the prompt teachers actually type, 297 of 300 free-model rewrites gave away operations, values or steps. With careful prompts it's 13%.
- **The obvious fix doesn't hold:** of 54 rewrites whose answer changed, the best free AI judge caught 7. Judges disagree with each other, and a small one flags almost everything. Layered checks and adjudicated human labels are required.
- **The safeguard:** free rules + AI critic + answer recomputation, wrapped in guarantees ("of what we pass, ≤ α is unsafe"), label-efficient statistics and an audit budget.
- **Equity:** the whole pipeline runs at $0 on a school's own hardware, but only above a size threshold: a 3B model can't follow the format, and as a judge it flags 85%.
- **Same problem, easier to read, and verified before it reaches a student.**

---

# Backup slides

## B1 · Main run, every number (OSCAR, free models, automated checker decisions)
| Rewriter | Prompt | Outputs | Unusable format | Checked | PASS | REVIEW | REJECT | Answer MATCH | MISMATCH | Leak flag | Qwen 32B unsafe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen 14B | plain | 124 | 0 | 124 | 87 (70%) | 26 | 11 (9%) | 108 | 5 | 5 | 2 |
| Qwen 14B | chunked | 124 | 0 | 124 | 51 (41%) | 61 | 12 (10%) | 103 | 11 | 0 | 1 |
| Qwen 14B | realistic | 100 | 0 | 100 | 0 | 3 | 97 | 76 | 16 | 97 | 88 |
| Gemma 12B | plain | 124 | 0 | 124 | 58 (47%) | 47 | 19 (15%) | 101 | 14 | 5 | 2 |
| Gemma 12B | chunked | 124 | 0 | 124 | 57 (46%) | 44 | 23 (19%) | 97 | 16 | 7 | 5 |
| Gemma 12B | realistic | 100 | 0 | 100 | 0 | 0 | 100 | 74 | 18 | 100 | 98 |
| Llama 3B | plain | 124 | 1 | 123 | 81 (66%) | 25 | 17 (14%) | 104 | 8 | 6 | 8 |
| Llama 3B | chunked | 124 | **123** | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| Llama 3B | realistic | 100 | 0 | 100 | 0 | 0 | 100 | 68 | 24 | 100 | 100 |
| Sentence splitter (control) | — | 124 | 0 | 124 | 116 | 8 | 0 | — | — | 0 | — |

**Careful prompts, all rewriters (n = 620)**
- PASS 335 (54%) / REVIEW 203 (33%) / REJECT 82 (13%).
- By source:
  - GSM8K: 67 rejects of 499 (13%).
  - ASDiv: 5 of 60 (8%).
  - GSM1K: 10 of 61 (16%).
- Program check: 514 MATCH / 54 MISMATCH / 52 uncheckable.
- Top flags:
  - chunk format (78);
  - answer mismatch (54);
  - relation or quantifier added (43) or lost (35);
  - question wording changed (25).

**Realistic prompt (n = 300)**
- Top flags:
  - critic unsafe (286);
  - operation leaked (266);
  - derived value leaked (260);
  - symbols (239);
  - solution steps (201);
  - quantity added (95);
  - answer mismatch (58).

**REVIEW is the false-alarm budget.** A third of careful-prompt rewrites go to a teacher, mostly for formatting and relation-wording flags. The cascade and conformal threshold are built to shrink that.

**Compute:** generation took about 1.9 GPU-hours for 1,044 rewrites. The Qwen 32B critic plus extraction takes about 36–44 s per rewrite, on one 48 GB GPU.

## B2 · Dev pilot and tuning (practice problems only)
| Rewriter (local, $0) | Checked | Pass | Review | Reject | Same answer recomputed |
|---|---|---|---|---|---|
| Qwen 14B | 20 | 12 | 8 | 0 | 19/20 |
| Gemma 12B | 20 | 11 | 9 | 0 | 18/20 |
| Llama 3B | 10 | 7 | 0 | 3 | 10/10 |

- Critics on the 50 rewrites:
  - Qwen 32B: SAFE 50/50.
  - Gemma 12B: unsafe on 5.
  - Llama 3B: unsafe on 45.
  - Claude Haiku 5.5: unsafe on 5.
  - GPT-6 Luna: unsafe on 6.
- A Gemma parser fix (raw line breaks inside its JSON) recovered 9 rewrites. Llama's chunked failures are kept as a result.
- Checker tuning on the Claude pilot: false alarms halved, 17 / 22 / 1 → **29 / 11 / 0** (pass / review / reject, n = 40), with the real catch kept: chunking detached "from her weekly earnings" from the 5%.
- **Clean (Qwen 14B, chunked):** "Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?" → "- Lisa has 18 more dresses than Ana. / - The number of their dresses combined is 48. / Question: How many dresses does Ana have?" PASS; both versions recompute to 15.

## B3 · Cost
- Free tier: **$0**, one GPU, about 1.5 days for the whole run. Student materials never leave campus.
- Paid checker for the whole study (upper bounds): ≈ $7 Haiku · ≈ $18 Sonnet · ≈ $58 Opus.
- Paid judges on the free rewrites (OpenRouter, list prices Nov 15):
  - Haiku 5.5 and GPT-6 Luna: ≈ $0.40 each.
  - Sonnet 5.5 and GPT-6.1 Sol: ≈ $8 each.
  - Total ≈ $17 under a $30 cap; $0.03 spent so far.
- One REVIEW costs about 1.5 minutes of teacher time. At the careful-prompt rate (33% REVIEW), that's about 10 min per 20 rewrites. **Teacher time, not dollars, is the binding cost**, which is why false alarms matter.

## B4 · Labelling design and calibration
- Calibration (two blind annotators, n = 70; κ / Gwet AC1):

  | Label | κ | AC1 | Note |
  |---|---|---|---|
  | SAFE | 0.79 | 0.89 | |
  | Leakage level | 0.95 | 0.97 | |
  | Leakage type | 0.92 | 0.97 | |
  | Abstention | 0.89 | 0.99 | |
  | Ambiguity | 0.62 | 0.94 | |
  | Math fidelity | 0 | 0.90 | Prevalence effect: almost every item is faithful, so κ collapses; that's why AC1 is prespecified alongside it |
  | Presentation | 0.50 | 0.53 | Being revised |
  | Adaptation needed | 0.13 | 0.46 | Being revised |
  | Failure codes | 0.43 | 0.45 | n = 19 |

- Lean, prespecified: about 850 of the outputs labelled (all realistic-prompt outputs, half of the careful-prompt sources paired across models, all repairs of labelled items); 30% double-labelled.
- Remaining rates by PPI: human labels correct the checker's bias.
