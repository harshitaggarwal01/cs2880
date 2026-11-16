# SafeAdapt-Math — Nov 16 presentation (10 slides + backup, ~11 min)

> **Status (Nov 15, 21:45):** both annotators have finished the 70 calibration items (blind). Slide 7 still uses annotator A's labels, because adjudication hasn't happened yet. **Check before presenting:** B-vs-A on SAFE (13 / 5 / 0 / 52) is cell-for-cell the same table as the AI-labeller-vs-A comparison. Confirm that B's SAFE labels are not the AI's: `python src/calibrate.py --compare-preliminary data/calibration/pilot/sheet_B.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv` prints aggregate agreement only. If they match exactly, drop the "second human" bullet on slide 8.
> **Accuracy rules:** every number states its n. "Preliminary" = labels not yet adjudicated, 10 practice problems. OSCAR numbers are checker decisions on practice problems, not human labels.

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
- **Conditions:** plain language · chunked · the *realistic* teacher prompt ("make this easier for a student with ADHD or dyslexia") · a non-AI baseline that only splits sentences.
- **Rewriters:** paid (Claude Haiku, Sonnet) and free open-weight models run locally (Qwen, Gemma, Llama), about 1,430 outputs.
- **Three-layer checker:**
  - **Rules (free):** numbers, relations, quantifiers, leaked operations and derived values.
  - **AI critic:** rubric-based verdict with cited evidence.
  - **Program check:** extract both versions as programs and recompute; a different answer means a REJECT.
- **Labels:** two annotators, blind; rubric calibrated first (target κ/AC1 ≥ 0.7). **Calibration done: SAFE κ 0.79, AC1 0.89, 93% raw (n = 70).** Two labels missed the bar and are being revised before the freeze: "adaptation needed" (AC1 0.46) and presentation (AC1 0.53). After that, about 850 items, about 14 h each.

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
**Careful prompts: 92% safe. The realistic teacher prompt: 30%.**

| Prompt | SAFE | 95% CI |
|---|---|---|
| Careful prompts (plain + chunked, n = 50) | **92%** (46/50) | 81–97% |
| Realistic teacher prompt (n = 20) | **30%** (6/20) | 15–52% |
| · Claude Opus, realistic | **0/10** | 0–28% |
| · Claude Haiku, realistic | 6/10 | 31–83% |

- **What it means:** the risk lives in how teachers ask, not in model capability. The most capable model was the *least* safe: Opus added "steps to try" to every rewrite.
- A more helpful model is more eager to scaffold, and scaffolding is exactly the modification we're trying to catch.
- So a safeguard can't rely on prompt discipline. It has to check the output.

*Footnote:* Preliminary: annotator A's labels, 70 outputs on 10 practice problems. The second annotator has finished; adjudication is pending. The CIs are wide; the main study has 124 problems.

---

## 8 · Result 2: no single judge can be trusted with the line (1.5 min)
**Large AI judges wave everything through, small ones flag everything, and even humans split in one direction.**
- **Free AI critics on OSCAR, same 50 rewrites:**
  - Qwen 32B: **SAFE on 50 of 50.**
  - Gemma 12B: unsafe on 5.
  - Llama 3B: **unsafe on 45 of 50.**
  - One critic is a rubber stamp and another is an alarm. All 20 flags that mattered came from the rules and the recomputation layer.
- **The example that matters** (Llama 3B rewrite, plain): *"The remaining floors are each 3 feet taller."* → *"The remaining **10** stories are **15** feet tall each."*
  - Qwen 32B and Gemma 12B critics: SAFE.
  - The free rule: **REJECT**, because two intermediate values were computed for the student.
- **Humans:** two blind annotators agree on SAFE at κ 0.79 (93%, n = 70), and every disagreement runs the same way: A said unsafe, B said safe (5 of A's 18). The Claude labeller showed the identical pattern against A.
  - The accommodation/modification line is where judgment diverges, for people and models alike.
- **What it means:** an AI verdict is a signal, not a decision. Rules and recomputation can't be talked into "looks fine". Adjudicated human labels stay the ground truth, and AI verdicts enter only as a bias-corrected predictor (PPI).

*Footnote:* OSCAR: checker decisions on 10 practice problems, no human labels. Humans: calibration set, before adjudication.

---

## 9 · What we're testing next and want feedback on (1 min)
**Early signal from the free tier: models a school can afford break the output contract.**
- Rewrites that came back in the required format, chunked style, 10 practice problems:
  - Qwen 14B and Gemma 12B: 10/10.
  - Mistral 7B: 8/10. Gemma 4B: 10/10.
  - **Llama 3B, Phi-3 3.8B: 0/10.** **Qwen 4B: 0/10:** it reasons until it is cut off.
- A small model isn't automatically cheap: the Qwen 4B critic used 2,300–4,000 tokens per verdict, **~25× slower** than the 32B (~200 s vs ~8.5 s).
- **Next:**
  - Main run on OSCAR: running, all three free rewriters, about 1.5 days.
  - Claude (Haiku, Sonnet) and GPT (Luna, Sol) critics judge the same rewrites, under $30 with no new labels. This gives a free vs frontier judge comparison.
  - Revise the two weak labels, freeze the rubric, then labelling (about 1 week).
  - Guarantees, cascade and audit game on real labels.
- **Feedback we want:**
  1. Is "accommodation vs modification" the right operational line for leakage?
  2. Which deployment framing is most useful: teacher tool, district audit, or vendor certification?
  3. How should we report a cheap model whose outputs often can't be checked at all?

---

## 10 · Summary (45 s)
- **The failure is real:** with the prompt teachers type, most rewrites stopped being the same task (6/20 safe, preliminary).
- **The obvious fix doesn't hold:** a 32B AI judge passed 50 of 50 rewrites, including ones the rules rejected, and a 3B judge flagged 45 of 50. Layered checks and adjudicated human labels are required.
- **The safeguard:** free rules + AI critic + answer recomputation, wrapped in guarantees ("of what we pass, ≤ α is unsafe"), label-efficient statistics and an audit budget.
- **Equity:** we test whether a $0 model on a school's own hardware can rewrite *and* check safely. Early answer: only above a size threshold.
- **Same problem, easier to read, and verified before it reaches a student.**

---

# Backup slides

## B1 · Free models on OSCAR: dev pilot (checker decisions)
| Rewriter (local, $0) | rewrites checked | pass | review | reject | same answer recomputed |
|---|---|---|---|---|---|
| Qwen3 14B | 20 | 12 | 8 | 0 | 19/20 |
| Gemma3 12B | 20* | 11 | 9 | 0 | 18/20 |
| Llama3.2 3B | 10** | 7 | 0 | 3 | 10/10 |

- Final dev pilot, job 9153208: gate passed, and the main run started on the same GPU at 20:59, Nov 15.
- \*All 20 Gemma rewrites became readable after a parser fix (raw line breaks inside its JSON).
- \*\*Llama 3B produced no usable chunked rewrites (0/10). That's kept as a result, not tuned away.
- Critics on the 50 rewrites:
  - Qwen 32B (primary): SAFE 50 of 50, about 7.5 s each.
  - Gemma 12B: unsafe on 5.
  - Llama 3B: unsafe on 45, with one invalid reply.
  - Program check: 47 MATCH, 3 uncheckable.
- Brown OSCAR, one L40S GPU, no API keys; student materials never leave campus. 10 practice problems; no human labels.
- **Clean (Qwen 14B, chunked):** "Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?" → "- Lisa has 18 more dresses than Ana. / - The number of their dresses combined is 48. / Question: How many dresses does Ana have?" PASS; both versions recompute to 15.
- **Flagged (Llama 3B, plain):** "The remaining floors are each 3 feet taller" → "The remaining 10 stories are 15 feet tall each." REJECT (`LEAK_DERIVED_VALUE`, `QTY_OMIT_OR_CHANGE`).

## B2 · Checker tuning (Claude pilot, practice problems only)
- False alarms halved: 17 / 22 / 1 → **29 / 11 / 0** (pass / review / reject, n = 40), with the real catch kept: chunking detached "from her weekly earnings" from the 5%.

## B3 · Cost
- Whole study: **$0** local · ≈ $7 Haiku checker · ≈ $18 Sonnet · ≈ $58 Opus (upper bounds; a hard cap stops overruns).
- Frontier judges on the free rewrites (OpenRouter, list prices checked Nov 15): Haiku 5.5 and GPT-6 Luna ≈ $0.40 each, Sonnet 5.5 and GPT-6.1 Sol ≈ $8 each. All four come to about $17 upper bound, against a $30 cap enforced per critic.
- At today's flag rate, about 16 min of teacher review per 20 problems vs about 60¢ of API. **Teacher time, not dollars, is the binding cost**, which is why false alarms matter.

## B4 · Labelling design
- Calibration (two blind annotators, n = 70; κ / Gwet AC1):
  - SAFE: 0.79 / 0.89.
  - Leakage level: 0.95 / 0.97.
  - Leakage type: 0.92 / 0.97.
  - Ambiguity: 0.62 / 0.94.
  - Math fidelity: κ 0 / AC1 0.90. Almost every item is faithful, so κ collapses; that prevalence effect is why AC1 is prespecified alongside it.
  - Presentation: 0.50 / 0.53. Being revised.
  - Adaptation needed: 0.13 / 0.46. Being revised.
- Lean, prespecified: about 850 of about 1,430 outputs labelled (all realistic-prompt outputs, half of the careful-prompt sources paired across models, all repairs of labelled items); 30% double-labelled.
- Remaining rates by PPI: human labels correct the checker's bias.
