# Check-in 1 (Nov 3): SafeAdapt-Math

**Project.** Teachers use AI to rewrite math word problems for students with disabilities, as plainer wording or broken into chunks. We measure whether those rewrites keep the math the same and avoid giving away the answer. We also build a checker that catches the ones that don't, at a cost a school can afford.

## Done since the proposal

| | Status |
|---|---|
| Plan | Four phases with dates and exit gates, tied to the three check-ins (`docs/plan/ROADMAP.md`) |
| Phase 1 pipeline (MVP) | Frozen sample of 124 problems → rewrites (2 models × plain/chunked + a realistic teacher-style prompt) + a non-AI baseline → 3-layer checker → one repair pass → blind labelling sheets → cost ledger → prespecified analysis → report |
| Phases 2–4 code | Guaranteed PASS (conformal), cost-aware checking, fewer-labels estimation (PPI), choosing the rewrite style (bandit), red-team, classroom-tool audit harness, teacher survey, demo, release packaging. All tested on simulated data; they run on real labels later |
| Tests | 108 pass; the full pipeline also runs end to end offline |
| Statistics review | Fixed the fewer-labels estimator (intervals were too wide) and the regression's fallback when a condition has no failures; corrected the wording of the PASS guarantee |
| **Real pilot (today)** | 10 practice problems (GSM8K train) × Claude Haiku and Sonnet × plain and chunked = 40 rewrites, all run through the 3-layer checker |
| Calibration sheets | 70 earlier pilot items, blinded, ready for both of us to label |

## Real pilot results
These are the checker's decisions, not human labels, so they are not failure rates.

| | Result |
|---|---|
| Rewrites | 40 (3 plain ones came back unchanged as "no rewrite needed") |
| Checker | **17 PASS, 22 REVIEW, 1 REJECT** |
| AI reviewer (Opus) | 39 SAFE, 1 UNSURE |
| Recompute the answer | 40 / 40 give the same answer as the original |
| Cost | **$1.19 total, about $0.03 per rewrite** (writing $0.05, checking $1.14). The main run comes to about $20, as budgeted |

## What we learned: the checker over-flags, in two places

1. **"Relations differ" fires on 18 of 40, even though every recomputed answer matches.** Example: Sonnet's chunked rewrite of the marble problem splits each sentence into its own bullet ("Mary collected twice as many red marbles as Jenny." / "Anie collected 20 more red marbles than Mary." …). It is faithful, and the answer is 100 both times, yet it is flagged because the relation list extracted from it differs. This one flag causes most of the review queue.
2. **The only REJECT is a false alarm.** Sonnet rewrote the Vikki pay problem as *"Money is taken out of her weekly earnings in three ways: 20% is taken out for tax, 5% … and $5 …"*. The word "three" matched a number that can be derived from the problem, so the leak rule fired. Counting words like this are not leaks.

**And one real catch.** When Haiku split the Vikki problem into bullets ("From her weekly earnings, 20% is deducted as tax." / "5% is deducted as insurance cover."), "from her weekly earnings" no longer covered the 5% line. A student could then take 5% of what's left after tax and get a different answer. The AI reviewer flagged it (UNSURE → REVIEW). Word-matching rules can't see this kind of subtle error, which is why the AI layer exists.

**Fix:** tune both rules on the 10 practice problems only, re-check the pilot (about $1), and record the change. The 124 study problems are never used for tuning.

## Next 7 days (to check-in 2)
1. Fix the two false alarms on the practice set and re-check the pilot.
2. Both of us label the 70 calibration items blind; check agreement (target κ/AC1 ≥ 0.7); freeze the rubric.
3. Main run: about 700 rewrites, checking, repair and sheets (about $20, about 4 days of API time).
4. Start labelling. Check-in 2 shows real outputs, first labels and the method notes.

## Questions for you
1. Is an Anthropic-only first run acceptable? The rewriting models and the AI reviewer come from the same company, which we disclose. OpenAI and Gemini get added when we have keys.
2. Should we add the distractor set (GSM-IC)? It costs about 48 more items to label, and it tests whether rewrites wrongly drop irrelevant details.
3. Which real classroom tools should we audit (manual capture, after a terms-of-service check)?
4. Should we submit the teacher survey for an ethics-board (CUHS) determination this semester, or defer it?

*Claims we don't make: no learning gains or diagnosis-specific benefit; PASS means "no problems detected under these checks", not "proven equivalent"; pilot numbers are never quoted as rates.*
