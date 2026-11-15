# SafeAdapt-Math: Progress and First Results (slide content for Claude Design)

**Brief for the designer:**
- 12 slides, 16:9, about 10 minutes (about 50 seconds a slide).
- Same visual style as our earlier deck: dark navy title slide, light content slides; coral = problems, teal = safe/pass, amber = review.
- One idea per slide. Use big numbers and simple bar charts where numbers appear.
- Keep speaker notes in the notes, not on the slide.
- **Accuracy rule:**
  - Slides 5 and 6 are *preliminary*: one annotator, 70 outputs from 10 practice problems. Keep the small "preliminary" footnotes and the n's.
  - Slide 7 shows checker decisions, not human labels.
  - Slide 8 is a placeholder until the OSCAR run is in.

> **Before presenting:** Cathy is still labelling the same 70 calibration items. Slides 5–6 show the results of those items, so ideally she finishes her sheet before she sees this deck.

---

## Slide 1 — Title
**SafeAdapt-Math: Progress and First Results**
Auditing AI accessibility rewrites of math word problems · CS 2880 AI for Social Impact · November 2026
*Visual:* teacher → AI → student icons.

**Speaker notes:** A quick reminder of the problem, then three new things: our first human labels, what they say about AI labelling, and free models a school could run. Then the study design, the methods, and the plan to the end of term.

---

## Slide 2 — The problem in one picture
**Headline:** Teachers ask AI to make math problems easier to read. Sometimes the AI makes them easier to *solve*.

Left card: **Original:** "Out of the 200 cookies that Javier baked…, his wife took 30%, and his daughter took 40 from the remaining cookies. If he ate half of the remaining cookies, how many cookies did they not eat?"
Right card (coral): **AI rewrite with the prompt teachers actually type:** "… **Steps to try:** 1. Find 30% of 200. Subtract it from 200. 2. Subtract the 40 cookies… 3. Find half of what is left…"

Bottom bar: An *accommodation* (same task, easier to access) is fair. A *modification* (easier task) is not, and nobody notices.

**Speaker notes:** This is a real output from our earlier pilot. Same numbers, same answer, but the thinking is done for the student. That's the risk we measure and try to catch.

---

## Slide 3 — Three ways to ask the AI
**Headline:** Plain changes the words. Chunked changes the layout. The realistic prompt is what teachers really type.

Three columns:
- **Plain language:** shorter sentences, simpler words, same numbers and math phrases.
- **Chunked:** one fact per line, question last.
- **Realistic teacher prompt:** "Rewrite this … easier to understand for a student with ADHD or dyslexia. Use simple language and break it into small chunks."

Footer: Plus a non-AI baseline that only splits the original into sentences. **Safe** = same numbers, relations and question, with nothing given away.

**Speaker notes:** Our careful prompts forbid hints and changes. The realistic prompt is the casual request a busy teacher types, and the gap between the two is our main comparison.

---

## Slide 4 — What we built
**Headline:** A pipeline that rewrites, checks, repairs and gets humans to label, end to end

Flow diagram, left to right: **124 real problems** → **rewrites** (3 AI models × 3 prompts + non-AI baseline) → **3-layer checker** (free rules → AI reviewer → recompute the answer) → **one repair try** → **blind human labels** → **analysis & guarantees**.

Small stat chips: 225 automated tests · runs in one command · every number traceable to a file.

**Speaker notes:** Everything that doesn't need human labels is built and tested, including the methods on slide 10. Human labels are the ground truth everything is judged against.

---

## Slide 5 — First human labels (preliminary)
**Headline:** With the realistic prompt, most rewrites stopped being the same task

Big bar chart, share of rewrites labelled SAFE:
| Prompt | SAFE | 95% CI |
|---|---|---|
| Careful prompts (plain + chunked, 50 rewrites) | **92%** (46/50) | 81–97% |
| Realistic teacher prompt (20 rewrites) | **30%** (6/20) | 15–52% |
| … Claude Opus, realistic prompt | 0/10 | 0–28% |
| … Claude Haiku, realistic prompt | 6/10 | 31–83% |

Footnote: *Preliminary: one annotator, 70 outputs on 10 practice problems; the second annotator is still labelling. Not study results.*

**Speaker notes:** Our first human labels. The careful prompts were mostly safe; the realistic prompt mostly wasn't. The more capable model leaked more: Opus added "steps to try" every time. Even careful prompts weren't perfect: 4 of 50 changed the math. The sample is tiny, so the intervals are wide; the main study has 124 problems.

---

## Slide 6 — Can an AI do the labelling?
**Headline:** An AI labeller agreed 93% of the time, but every miss was an unsafe rewrite it called safe

Left: big number **κ = 0.79** (Cohen's kappa, human vs AI on SAFE; 93% raw agreement, n = 70).
Right: 2×2 table:
| | AI: safe | AI: unsafe |
|---|---|---|
| **Human: safe** | 52 | 0 |
| **Human: unsafe** | **5** | 13 |

Takeaway bar: **The AI missed 5 of 18 unsafe rewrites. Human labels stay the ground truth;** AI labels are a predictor we correct with prediction-powered inference.

Footnote: *AI labels proposed by Claude using our rubric; human = one annotator, preliminary.*

**Speaker notes:** High agreement sounds good, but every disagreement went the same way: the AI was too lenient. That's exactly why the study uses human labels as ground truth and uses AI judgments only as a cheap predictor that a statistical correction fixes.

---

## Slide 7 — The automatic checker on real outputs
**Headline:** We cut false alarms by half without losing the real catch

Two big-number pairs (40 Claude rewrites, practice problems):
- **Before tuning:** 17 pass · 22 review · 1 reject
- **After tuning (v1.1):** 29 pass · 11 review · 0 reject
- Real catch kept: chunking detached "from her weekly earnings" from the 5% → still flagged.

Footnote: *Checker decisions, not human labels. Tuned on the 10 practice problems only; the 124 study problems were never used for tuning.*

**Speaker notes:** Over-flagging wastes teacher time. Two over-strict rules caused most of it. We fixed them on practice problems only, and the subtle real catch is still caught.

---

## Slide 8 — Free models a school could run (PLACEHOLDER: fill in after tonight's OSCAR run)
**Headline:** Open models on our own GPU: $0 per rewrite

Table to fill in:
| Rewriter (local, via Ollama) | rewrites | pass | review | reject | same answer recomputed |
|---|---|---|---|---|---|
| Qwen (open-weight) | [n] | [ ] | [ ] | [ ] | [ ]/[n] |
| Llama (open-weight) | [n] | [ ] | [ ] | [ ] | [ ]/[n] |

Side note: Runs on Brown's OSCAR cluster; no API keys; the data never leaves campus.
Footnote: *Checker decisions on 10 practice problems; no human labels yet.*

**Speaker notes:** A school can't always pay per request or send student materials to a company. So we test open-weight models served locally: is a free model as safe a rewriter, and can a free model do the checking? [Fill in one sentence from tonight's numbers.]

---

## Slide 9 — The full study
**Headline:** Every checker judges every rewrite, and humans label a smart half

Left column (design):
- 124 problems (GSM8K, ASDiv, GSM1K), frozen.
- 3 rewriters (2 Claude + 1 open-weight) × plain, chunked, realistic + non-AI baseline: about 1,430 outputs.
- Every checker model judges every output. Labels attach to rewrites, so extra checkers cost no extra labelling.

Right column (labelling):
- Half the problems fully labelled for the careful prompts (paired across models); all realistic-prompt outputs; all repairs of labelled items.
- **About 850 labels, about 14 h per person**, 30% double-labelled for agreement.
- Rates for the rest by **prediction-powered inference** (human labels correct the checker's bias).

Footer: *All of this was fixed before any study data was generated (prespecified).*

**Speaker notes:** Labelling is our bottleneck, so we label smartly. Fully label where failures are expected, half-label where they're rare, and use PPI to get unbiased rates for everything.

---

## Slide 10 — More than a better prompt
**Headline:** Methods that turn a checker into a decision tool (all coded and tested)

Grid of six cards:
1. **Guaranteed PASS** (conformal): "of what we pass, at most X% is unsafe".
2. **Cost-aware checking** (cascade): free rules → cheap model → strong model → human.
3. **Fewer labels** (PPI): honest rates from a labelled sample.
4. **Which rewrite to use** (contextual bandit, plus online learning from teacher feedback).
5. **Where to audit** (Stackelberg audit game): spend a limited audit budget where it prevents the most harm.
6. **Checkers without labels** (Dawid–Skene) and a **small free checker** trained on our labels.

Footer: *Built and tested on simulated data; they run on the real labels next.*

**Speaker notes:** This is what makes the project more than prompt engineering: guarantees, cost-aware decisions, label-efficient statistics, and a game-theoretic audit plan in the style of this course's security games.

---

## Slide 11 — Cost
**Headline:** Money isn't the constraint; teacher time is

Four tier cards: **$0** local open models · **$7** Haiku checker · **$18** Sonnet checker · **$58** Opus checker (whole study, upper bounds). A hard spending cap stops any run that would exceed its budget.

Bottom bar: At today's flag rate, 20 problems a week costs a teacher about 16 minutes of review against about 60¢ of API. **That's why false alarms matter more than API cents.**

**Speaker notes:** We can run the whole study for free on OSCAR, or for a few dollars with a stronger checker. The cost that matters in a school is review time, which is what our checker tuning and cost-aware cascade target.

---

## Slide 12 — Next steps
**Headline:** Next steps

Timeline (left to right):
1. **This week:** second annotator finishes calibration → agreement → freeze the labelling rubric.
2. **Main run:** about 1,430 outputs (free on OSCAR, plus a Claude checker).
3. **Labelling:** about 14 h each over about a week.
4. **Analysis:** rates, prompt comparison, checker recall, repair, guarantees, cost frontier, rewrite rule, audit game.
5. **Final:** report, demo, open data (as licences allow).

Closing line: **Same problem, easier to read, and a way to check it before it reaches a student.**

**Speaker notes:** Everything is built. The path now is labels: calibrate, run, label, analyse. Thank you.
