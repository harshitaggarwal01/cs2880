# SafeAdapt-Math — Updates and Progress (slide content)

Deck brief for the designer:
- 11 slides, 16:9. Clean and calm: dark navy title slide, light content slides.
- Accents: coral (problems), teal (safe / pass), amber (review).
- One idea per slide, with big numbers where there are numbers and short phrases rather than paragraphs.
- Speaker notes are included under each slide; keep them in the notes, not on the slide.
- Accuracy rule: the pilot numbers are the checker's decisions, not human-labelled failure rates. Keep the small footnotes where shown.

---

## Slide 1 — Title

**SafeAdapt-Math: Updates and Progress**

Auditing AI accessibility rewrites of math word problems

CS 2880 · AI for Social Impact · November 2026

*Visual:* three icons in a row or arc: teacher → AI → student.

**Speaker notes:** Quick update on where SafeAdapt-Math stands: what it is, what we've built, the first results on real models, and what comes next.

---

## Slide 2 — Context: why this matters

**Headline:** Teachers use AI to make math problems easier to read. Sometimes the AI changes the problem.

Three short blocks, left to right:

1. **What teachers do.** They paste a word problem into an AI tool and ask for plainer wording, or for it to be broken into steps, for students with reading or attention difficulties.
2. **What can go wrong.**
   - The math changes: a number or relationship is lost or altered.
   - The answer leaks: hints like "Steps to try: find 30% of 200, then subtract…" do the thinking for the student.
3. **Why it matters.** An *accommodation* (same task, easier to access) is fair. A *modification* (an easier or different task) is not, and nobody notices.

Bottom bar, highlighted: **Earlier small pilot:** 13 of 20 realistic-prompt rewrites were unsafe, vs 0 of 50 careful-prompt ones (preliminary labels).

**Speaker notes:** The rewrite should change how the problem looks, not what it asks. In an earlier small pilot, rewrites from a casual, realistic teacher prompt often added solution steps. That is the core risk: the AI being too helpful, in exactly the way teachers use it. In that earlier pilot, 13 of 20 realistic-prompt rewrites were unsafe against 0 of 50 careful ones. The labels were preliminary, so it's a signal, not a rate, but it's why the realistic prompt is a main condition.

---

## Slide 3 — Two kinds of rewrite

**Headline:** Plain changes the words. Chunked changes the layout. Neither may change the math.

Three cards, left to right (real outputs, one problem):

| Original | Plain language | Chunked |
|---|---|---|
| Vikki worked 42 hours in one week. Her hourly pay rate is $10. From her weekly earnings, 20% is deducted as tax, 5% is deducted as insurance cover, and $5 is deducted for union dues. How much money, in dollars, does Vikki take home after deductions? | Vikki worked 42 hours in one week. She is paid $10 per hour. Money is taken out of her weekly earnings in three ways: 20% is taken out for tax, 5% is taken out for insurance, and $5 is taken out for union dues. How much money, in dollars, does Vikki take home after these deductions? | – Vikki worked 42 hours in one week. / – Her hourly pay rate is $10. / – From her weekly earnings, 20% is deducted as tax. / – 5% is deducted as insurance cover. / – $5 is deducted for union dues. / Question: How much money, in dollars, does Vikki take home after deductions? |

Bottom bar: **Safe =** same numbers, relations and question, with no added steps, hints or answer. Real outputs from Claude Sonnet (plain) and Haiku (chunked).

**Speaker notes:** These are the two kinds of rewrite we test, and they match what teachers ask AI tools to do. Plain language keeps the same problem in simpler words: shorter sentences, common words, names instead of pronouns, every number and every math phrase like "twice as many" or "per". It's aimed at students who find dense text hard to read. Chunked keeps the same words but puts one fact per line and the question last, for students who lose track in long blocks of text. Neither may solve, hint at an operation, add steps, or drop or reorder facts. Keep an eye on the chunked one: it comes back later as the checker's real catch. We also test the casual prompt teachers actually type, and a non-AI split that only breaks the original at sentences.

---

## Slide 4 — What we're building

**Headline:** Four steps, one pipeline

| 1 Measure | 2 Detect | 3 Fix | 4 Decide |
|---|---|---|---|
| 124 real math problems × 2 AI models × plain and chunked, plus the prompt teachers actually type, and a non-AI split (original sentences, no words changed) as the baseline | A three-layer checker says PASS / REVIEW / REJECT: free rule checks, an AI reviewer, and recomputing the answer | Rejected rewrites get one repair attempt, then are checked again | When to use AI, which setup, and when the simple split is good enough; with a guarantee on what PASS means |

Footer: *Human labels are the ground truth: every rewrite is labelled blind, and 30% are labelled twice to check agreement.*

**Speaker notes:** Measure how often rewrites go wrong, detect the bad ones cheaply, try to fix them, and turn it into a decision rule a school could actually use. Human labels (blind, with 30% labelled twice) are what everything is judged against.

---

## Slide 5 — Methods

**Headline:** Four methods that turn a checker into a decision system

Table (status pill "CODED", teal, on every row):

| Method | What it gives a school or tool |
|---|---|
| **Guaranteed PASS** (conformal risk control) | **A promise, not a hope:** "of the rewrites we pass, at most 5% are unsafe", with a statistical guarantee |
| **Cost-aware checking** (cascade) | **Cheapest safe order:** free rules first, AI reviewer only when unsure, a human last |
| **Fewer labels needed** (prediction-powered inference) | **Affordable audits:** accurate failure rates from a small labelled sample plus the checker on everything; makes testing real classroom tools feasible |
| **Which rewrite to use** (contextual bandit) | **A rule a tool can ship:** picks plain, chunked or the non-AI split for each kind of problem |

Bottom bar: **Also trying: red-teaming and a free checker.** An attacker AI tries to sneak hints past the checker; a small model trained on our labels lets schools check for free. All coded and tested on simulated data.

**Speaker notes:** This is what makes it more than a better prompt. A guarantee: we calibrate the checker so we can say "of what we pass, at most 5 percent is unsafe", with a statistical guarantee from conformal risk control. Cost-aware checking: free rules first, the expensive AI reviewer only when needed, a human last, so the cheapest safe order. Prediction-powered inference: accurate failure rates from a few human labels plus the checker on everything, which makes auditing real classroom tools affordable. A contextual bandit: it learns, per kind of problem, whether plain, chunked or the simple split is the safest useful choice, as a readable rule a tool could ship. We're also red-teaming the checker and training a free checker. All coded and tested on simulated data; they run on the real labels next.

---

## Slide 6 — Progress: what's built

**Headline:** Everything that doesn't need human labels is built

Four big-number cards:

| **124** | **108** | **40** | **$1.19** |
|---|---|---|---|
| real math problems chosen and locked for the study, from three public datasets | automated tests passing; the whole pipeline runs end to end | real AI rewrites produced and checked this week | total cost of that pilot, including checking: about 3¢ per rewrite |

Below the cards, a short list:
- **Core study pipeline:** pick problems → rewrite → check → repair → blind labelling sheets → cost tracking → analysis → report, in one command.
- **Methods (coded, tested on simulated data):**
  - a guaranteed PASS ("of what we pass, at most X% is unsafe")
  - cost-aware checking (cheapest mix of rules, AI reviewer and human)
  - honest failure rates from fewer human labels
  - a rule for picking the safest useful rewrite style
- **Real-world pieces:** a way to test actual classroom AI tools with the same checks, a survey of how teachers prompt, and a demo app.
- **Quality:** the statistics were reviewed and two methods were fixed before any results are reported.

**Speaker notes:** All the code that doesn't need human labels is done and tested, including the methods that make this more than a better prompt. Labelling is now the bottleneck, so that is where the time goes next.

---

## Slide 7 — First real pilot

**Headline:** First run on real models: what the checker said

Setup line: *10 practice problems × 2 Claude models (Haiku, Sonnet) × plain and chunked, careful prompts only = 40 rewrites*

Four big-number cards (coral, amber, teal, navy):

| **1** | **22** | **17** | **40 / 40** |
|---|---|---|---|
| REJECT: blocked automatically | REVIEW: sent to a human | PASS: no problems found | rewrites still give the original answer when recomputed |

Highlighted insight bar: **The checker over-flags.** One rule fires on 18 of 40 rewrites even though every answer still matches. That would waste teachers' time, so it gets tuned first.

Footnote (small): *Checker decisions, not human labels: not failure rates. The realistic teacher prompt runs in the main study. Reviewer: Claude Opus (same company; disclosed).*

**Speaker notes:** Good news first: every rewrite kept the original answer, and the AI reviewer called 39 of 40 safe. The issue is the cheap rule layer, which sent more than half to human review. The cost is tiny: about three cents per rewrite, so the full study is about twenty dollars.

---

## Slide 8 — What the pilot taught us

**Headline:** Two false alarms, one real catch

A table with a coloured verdict pill per row:

| Rewrite (real output) | Verdict | Why |
|---|---|---|
| Vikki's pay: "Money is taken out of her weekly earnings **in three ways**: 20% … 5% … $5" | REJECT (coral) | **False alarm:** "three" just counts the deductions; it isn't a leaked answer |
| Marble problem split into one fact per bullet; the answer is 100 both times | REVIEW (amber) | **False alarm:** the "relations differ" rule is too strict |
| Vikki as bullets: "From her weekly earnings, 20% is deducted as tax." / "5% is deducted as insurance cover." | REVIEW (amber) | **Real catch (AI reviewer):** the 5% no longer says what it's 5% of, so a student could compute it on what's left after tax |
| Website problem: same facts as bullets, same question | PASS (teal) | Nothing changed except the layout |

Takeaway bar: **Cheap rules raise false alarms; the AI reviewer caught the subtle problem.** We tune the rules on practice problems only, so the 124 study problems stay untouched.

**Speaker notes:** All four rows are real outputs from this week's run. The third row is the kind of error word-matching can never see: splitting a sentence into bullets quietly changed what "5%" refers to. That is why the checker has an AI layer and a human-review option, not just rules.

---

## Slide 9 — Final outputs

**Headline:** Final outputs

| 01 Benchmark | 02 Checker | 03 Policy | 04 Release |
|---|---|---|---|
| About 700 AI rewrites of 124 problems with blind human labels: failure and answer-leak rates by model and prompt, with uncertainty | Three-layer checker with a guarantee on PASS, its catch rate, and how much human review it costs | When to use AI, which style, and when the simple split is enough, learned from the labels (bandit) | Audit of real classroom AI tools, open data and code (as licences allow), a demo, and a failure gallery |

Footer: *Built to sit behind the "make it easier" button in tools teachers already use: a check before an adapted problem reaches a student.*

**Speaker notes:** At the end of the semester we deliver four things. A benchmark: about 700 AI rewrites with blind human labels, giving the first measured failure and answer-leak rates for this use, by model and prompt. A checker with a guarantee on what PASS means and an honest number for how much human review it costs. A policy: a simple learned rule for when to use AI, which style, and when the simple split is enough. And a release: a small audit of real classroom tools, open data and code where licences allow, a demo and a failure gallery. This can sit behind the "make it easier" button in tools teachers already use.

---

## Slide 10 — Next steps and plan

**Headline:** What's next

Left column, **Next up · coming weeks** (numbered steps):
1. **Tune the checker:** fix the two false-alarm rules on the practice problems; re-check the pilot (about $1).
2. **Calibrate the labels:** both of us label the same 70 items blind; agreement ≥ 0.7; freeze the labelling guide.
3. **Main run:** about 700 rewrites across all conditions, checked, repaired and put on blind sheets (about $20, about 4 days).
4. **Label:** one person labels everything, the second labels 30% for agreement; disagreements resolved together.

Right column, **Then · through the end of semester**:
- **Analysis:** failure and answer-leak rates with uncertainty; how much the realistic teacher prompt matters; how well the checker catches problems; whether repair helps.
- **Methods on real labels:** PASS guarantee, cost-vs-safety trade-off, fewer-labels estimates, the bandit rewrite rule; red-team as stretch.
- **Real-world audit:** a small, manually captured sample from classroom AI tools, checked the same way.
- **Wrap-up:** final report, demo, data release (what the licences allow), failure gallery.

Footer: *Rule we keep: nothing touches the 124 study problems until the checker and labelling guide are frozen.*

**Speaker notes:** The order is set by the bottleneck. Tuning and calibration are quick and cheap, the main run is mostly waiting on the API, and labelling is the long part. The methods are already coded, so they run as soon as the labels exist.

---

## Slide 11 — Summary

**Headline:** Where we stand

Three short lines with icons:
- ✅ **Built:** the full pipeline and every method, tested on simulated data.
- 🔬 **Real data:** first run done; the checker works, costs cents, and needs one round of tuning.
- ➡️ **Next:** tune, calibrate, run the full study, label.

Closing line, large: **Same problem, easier to read — and a way to check it before it reaches a student.**

**Speaker notes:** In one sentence: the system is built and running on real models for a few cents per problem, the first data already showed us exactly what to tune, and the main study is next.
