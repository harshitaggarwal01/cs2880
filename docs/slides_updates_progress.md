# SafeAdapt-Math — Updates and Progress (slide content)

Deck brief for the designer:
- 8 slides, 16:9. Clean and calm: dark navy title slide, light content slides.
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

Bottom line, highlighted: **Same problem, easier to read — and a way to check it before it reaches a student.**

**Speaker notes:** The rewrite should change how the problem looks, not what it asks. In an earlier small pilot, rewrites from a casual, realistic teacher prompt often added solution steps. That is the core risk: the AI being too helpful, in exactly the way teachers use it.

---

## Slide 3 — What we're building

**Headline:** Four steps, one pipeline

| 1 Measure | 2 Detect | 3 Fix | 4 Decide |
|---|---|---|---|
| 124 real math problems rewritten by AI models, plain and chunked, with careful and realistic teacher prompts, plus a simple non-AI split as a baseline | A three-layer checker says PASS / REVIEW / REJECT: free rule checks, an AI reviewer, and recomputing the answer | Rejected rewrites get one repair attempt, then are checked again | When to use AI, which setup, and when the simple split is good enough; with a guarantee on what PASS means |

Footer: *Human labels are the ground truth: every rewrite is labelled blind, and 30% are labelled twice to check agreement.*

**Speaker notes:** Measure how often rewrites go wrong, detect the bad ones cheaply, try to fix them, and turn it into a decision rule a school could actually use. Human labels (blind, with 30% labelled twice) are what everything is judged against.

---

## Slide 4 — Progress: what's built

**Headline:** Everything that doesn't need human labels is built

Four big-number cards:

| **4 / 4** | **108** | **40** | **$1.19** |
|---|---|---|---|
| project phases coded: core study, methods, real-world audit, write-up | automated tests passing; the whole pipeline runs end to end | real AI rewrites produced and checked this week | total cost of that pilot, including checking: about 3¢ per rewrite |

Below the cards, a short list:
- **Core study pipeline:** sample → rewrite → check → repair → blind labelling sheets → cost ledger → analysis → report, in one command.
- **Methods (coded, tested on simulated data):**
  - a guaranteed PASS ("of what we pass, at most X% is unsafe")
  - cost-aware checking (cheapest mix of rules, AI reviewer and human)
  - honest failure rates from fewer human labels
  - a rule for picking the safest useful rewrite style
- **Real-world pieces:** a harness to audit actual classroom AI tools, a teacher prompt survey, a demo app.
- **Quality:** the statistics were reviewed and two methods were fixed before any results are reported.

**Speaker notes:** All the code that doesn't need human labels is done and tested, including the methods that make this more than a better prompt. Labelling is now the bottleneck, so that is where the time goes next.

---

## Slide 5 — First real pilot

**Headline:** First run on real models: what the checker said

Setup line: *10 practice problems × 2 Claude models (Haiku, Sonnet) × plain and chunked = 40 rewrites*

Four big-number cards (coral, amber, teal, navy):

| **1** | **22** | **17** | **40 / 40** |
|---|---|---|---|
| REJECT: blocked automatically | REVIEW: sent to a human | PASS: no problems found | rewrites still give the original answer when recomputed |

Highlighted insight bar: **The checker over-flags.** One rule fires on 18 of 40 rewrites even though every answer still matches. That would waste teachers' time, so it gets tuned first.

Footnote (small): *Checker decisions, not human labels: not failure rates. AI reviewer: Claude Opus (same company as the rewriting models; disclosed).*

**Speaker notes:** Good news first: every rewrite kept the original answer, and the AI reviewer called 39 of 40 safe. The issue is the cheap rule layer, which sent more than half to human review. The cost is tiny: about three cents per rewrite, so the full study is about twenty dollars.

---

## Slide 6 — What the pilot taught us

**Headline:** Two false alarms, one real catch

A table with a coloured verdict pill per row:

| Rewrite (real output) | Verdict | Why |
|---|---|---|
| Vikki's pay: "Money is taken out of her weekly earnings **in three ways**: 20% … 5% … $5" | REJECT (coral) | **False alarm:** "three" just counts the deductions; it isn't a leaked answer |
| Marble problem split into one fact per bullet; the answer is 100 both times | REVIEW (amber) | **False alarm:** the "relations differ" rule is too strict |
| Vikki as bullets: "From her weekly earnings, 20% is deducted as tax." / "5% is deducted as insurance cover." | REVIEW (amber) | **Real catch (AI reviewer):** the 5% no longer says what it's 5% of, so a student could compute it on what's left after tax |
| Website problem: same facts as bullets, same question | PASS (teal) | Nothing changed except the layout |

Takeaway bar: **Cheap rules raise false alarms; the AI reviewer caught the subtle problem.** We tune the rules on practice problems only, so the 124 study problems stay untouched.

**Speaker notes:** All three are from this week's run. The third row is the kind of error word-matching can never see: splitting a sentence into bullets quietly changed what "5%" refers to. That is why the checker has an AI layer and a human-review option, not just rules.

---

## Slide 7 — Next steps and plan

**Headline:** What's next

Left column, **Next up** (numbered steps with arrows):
1. **Tune the checker:** fix the two false-alarm rules on the practice problems; re-check the pilot (about $1).
2. **Calibrate the labels:** both of us label the same 70 items blind; agreement ≥ 0.7; freeze the labelling guide.
3. **Main run:** about 700 rewrites across all conditions, checked, repaired and put on blind sheets (about $20, about 4 days).
4. **Label:** one person labels everything, the second labels 30% for agreement; disagreements resolved together.

Right column, **Then**, as a simple timeline:
- **Analysis:** failure and answer-leak rates with uncertainty; how much the realistic teacher prompt matters; how well the checker catches problems; whether repair helps.
- **Methods on real labels:** the PASS guarantee curve, the cost-vs-safety trade-off, fewer-labels estimates, the rewrite-style rule.
- **Real-world audit:** a small, manually captured sample from classroom AI tools, checked the same way.
- **Wrap-up:** final report, demo, data release (what the licences allow), failure gallery.

Footer: *Rule we keep: nothing touches the 124 study problems until the checker and labelling guide are frozen.*

**Speaker notes:** The order is set by the bottleneck. Tuning and calibration are quick and cheap, the main run is mostly waiting on the API, and labelling is the long part. The methods are already coded, so they run as soon as the labels exist.

---

## Slide 8 — Summary

**Headline:** Where we stand

Three short lines with icons:
- ✅ **Built:** the full pipeline and every method, tested.
- 🔬 **Real data:** first run done; the checker works, cheap, and needs one round of tuning.
- ➡️ **Next:** tune, calibrate, run the full study, label.

Closing line, large: **Same problem, easier to read — and a way to check it before it reaches a student.**

**Speaker notes:** In one sentence: the system is built and running on real models for a few cents per problem, the first data already showed us exactly what to tune, and the main study is next.
