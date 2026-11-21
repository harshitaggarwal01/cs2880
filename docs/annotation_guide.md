# Annotation Guide (rubric v1.2, frozen 2026-11-20 after the owner's review of the calibration)

**Read this before labelling anything.** The schema is `schemas/annotation_schema.json`. Examples come from the real dev pilot (`docs/professor_examples.md`).

## The standard
The adaptation must ask the learner to solve **exactly the same task as the original, unassisted**. It may change *how* the problem is presented (an accommodation). It may not change *what* is asked or *how much of the thinking is done for the learner* (a modification).

## Procedure for each item
Make three passes, in this order:

1. **Fidelity pass.** Go through the original clause by clause and tick off in the adaptation:
   - every quantity, with its unit and its owner (who or what it belongs to);
   - every relation, including its direction ("3 times as many" is not "3 more"; "more than" is not "fewer than");
   - every condition and quantifier ("each", "all", "remaining", "at least", "if…");
   - the time order;
   - the unknown being asked for.

   Then check that the adaptation adds no quantity or condition.
2. **Leakage pass.** Compare against the original. Look for anything the original made the learner work out:
   - an answer or intermediate value;
   - an operation word, equation, or plan;
   - layout that mirrors the solution order;
   - a cue about which facts matter.
3. **Presentation pass.** Did it achieve the requested transformation? Is it actually easier to read?

For every FAIL, leakage, or ambiguity label, quote the exact span in `evidence`.

## Labels

### math_fidelity: PASS / FAIL / UNSURE
- **FAIL** if any quantity, unit, entity binding, relation, condition, quantifier or temporal dependency is missing, changed or added.
- **UNSURE** only if, after checking, you cannot decide. Explain why in `notes`.

### target_preserved: PASS / FAIL / UNSURE
Same unknown, same unit. Rewording the question is fine ("How many pages does Cora need to read on Thursday?"). Changing what is asked is not (e.g., "how many does she sell" → "how many does she have").

### solvability_changed: NO / YES / UNSURE
YES if the adaptation can no longer be solved (e.g., "each" → "some"), has a different unique answer, or became solvable when the original was not.

### ambiguity: NONE / NEW / RESOLVED
- **NEW:** the adaptation allows a reading the original did not.
- **RESOLVED:** the adaptation commits to one reading of a phrase that was ambiguous in the original, e.g. "1/4 times more time" read as 20 + ¼·20 (pilot Example 8). Say in `notes` whether that reading matches the GSM8K solution. RESOLVED does not make an item unsafe on its own; it is reported separately.

### leakage_level 0–3, and leakage_type

| Level | Meaning | Pilot examples |
|---|---|---|
| 0 | Nothing the learner had to work out is given away | Opus chunked, Mary's marbles (Example 1) |
| 1 · STRUCTURE | Layout or labels that mirror the solution order, with no values or operations named | "Step 1: Purple beads / Step 2: Blue beads / Step 3: Gold beads" (Example 7) |
| 2 · STEPS / OPERATION / RELEVANCE | Names operations, sets up equations, gives a plan, or says which facts matter or don't | "Steps to try: 1. Find 30% of 200. Subtract it from 200…"; "The red marble facts are extra information you don't need" (Examples 4, 5) |
| 3 · INTERMEDIATE / ANSWER | States an intermediate result or the answer, in any form | "Stories 11 to 20"; "The other 10 floors" (Example 6) |

Record the most severe level and type. An intermediate value counts even when it is written in another form: a range, a heading, or "20 + 4" written for 24.

### presentation 0–3 (judge the student-facing problem only; v1.1 anchors)
- **0** harder to read than the original: longer, denser, or reordered so the facts are harder to find.
- **1** near-copy: word swaps or trims with the densest sentence left unchanged (`NO_ADAPT`); broken fragments (`HARMFUL_FRAGMENT`); or an already-clear original buried under added text (`OVER_EDIT`).
- **2** clearly easier: every long sentence split or shortened, but still prose. **Added text caps presentation at 2:** any solution steps, hints, tips or teacher notes, whatever the layout.
- **3** much easier: one fact per line or facts grouped under headings, the question set apart, every base and referent kept ("5% *of her weekly earnings*"), and nothing added.

Leave blank for `NO_REWRITE_NEEDED` outputs and fill `abstention_appropriate` instead.

### abstention_appropriate (NO_REWRITE_NEEDED only)
- **YES** if the original is already short and clear (Example 2: "Lisa has 18 more dresses than Ana…").
- **NO** if it was dense enough to benefit from the transformation (Sonnet on the payroll problem).

### adaptation_needed (judged on the original, once per source; v1.2 rule)
**YES** if any sentence of the original has more than 20 words, or carries three or more given quantities or relations, or the task depends on a word a struggling reader is unlikely to know, or a relation or reference is unclear (short is not the same as clear). Otherwise **NO**. UNCLEAR only with a note.
- YES: Vikki (one sentence holds three deductions), Cora, Katherine, Javier, Mary, Carly, James's building ("3 feet taller" never says than what), John's missions ("It took 60% longer" never names the mission).
- NO: Lisa (two short sentences), Karl's stickers.

### Clarifications (v1.1, revised in v1.2 by the owner's adjudication, 2026-11-20)
- **"If" clauses are conditions.** In "If he ate half of the remaining cookies, how many…?" the question is asked *under* the condition. Keep the condition attached to the question ("Question: If Javier ate half of the remaining cookies, how many are left?"). Restating it as an event ("Javier ate half of the remaining cookies.") drops the condition: **math FAIL, solvability YES**, codes `COND_OMIT, SOLVABILITY_CHANGE`. Not SAFE.
- **Dangling "If" fragments.** A bullet that keeps the "If" as a fragment ("- If Jenny collected 30 red marbles and 25 blue marbles.") is neither a fact nor the question; a student can read it as a hypothesis or drop it. **ambiguity NEW, math and solvability UNSURE**, codes `AMBIGUITY_NEW, HARMFUL_FRAGMENT, COND_OMIT`, presentation ≤ 1. Not SAFE.
- **Bases.** A split line that loses its base ("20% for tax" with no "of her earnings") is ambiguity NEW (`AMBIGUITY_NEW`). A flat amount ("$5") needs no base.
- **Level 3 is any intermediate the student had to set up.** A stated value, range or count ("Stories 11 to 20", "the other 10 floors") and an expression that sets up a derived quantity ("20 hours, plus an extra 1/4 of 20 hours") are level 3 INTERMEDIATE.
- **Headings and relevance cues.** A heading that only groups facts ("What she has read so far", colour blocks) is level 0. Marking which facts matter or don't ("Here is what you need to know", "The red marble facts are extra information you don't need") is level 2 RELEVANCE.
- **Step labels.** "Step 1 / Step 2 / Step 3" in solution order is level 1 STRUCTURE, not an operation. A solution-order layout or any leak caps presentation at 2.
- **Target wording.** A reworded question is the same target only if it keeps the same agent and action. "How many were not eaten?" for "how many did they not eat?" changes the target when the original separates "took" from "ate": target FAIL, `TARGET_CHANGE`. Choosing one reading of an ambiguous original is ambiguity RESOLVED.

## Allowed versus not allowed

**Allowed (accommodation):**
- shorter sentences;
- conditional or relative clauses split into separate sentences;
- passive voice made active;
- simpler non-math vocabulary ("fond of" → "like");
- pronoun → unambiguous referent;
- one fact per line;
- filler removed;
- an "If…" condition kept attached to the question ("Question: If X, how many…?");
- regrouping facts by person or object, as long as no fact is misattributed and no values or operations are added.

**Not allowed (modification):**
- changing or dropping any quantity, unit, relation, quantifier, condition, time order, or the unknown (including turning an "If" condition into a stated event, or leaving it as a dangling fragment);
- operation words or equations not in the original;
- numbered or "Step" labels in solution order;
- hints, tips, "steps to try";
- any derived value;
- saying a fact is irrelevant, or deleting it;
- bolding only *some* quantities (bolding all of them is fine).

**Whole reply rule (realistic prompt):** annotate everything the model returned, including preambles ("Here's a simpler version…") and teacher notes. A teacher may paste the whole reply into a worksheet. Preambles and notes addressed only to the teacher get the `EXTRA_TEXT` code. Anything a learner could use to solve the problem counts as leakage.

## Derived outcomes (computed, not entered)
```text
SAFE            = math PASS and target PASS and solvability NO and ambiguity != NEW and leakage_level == 0
SAFE_AND_USEFUL = SAFE and ((presentation >= 2 and no NO_ADAPT/HARMFUL_FRAGMENT) or abstention_appropriate == YES)
```

## Calibration protocol (week 1)
1. Both annotators independently re-label the 70 pilot outputs (`pilot/pilot_outputs.jsonl`) without looking at the preliminary labels.
2. Compute agreement (`src/evaluate.py --double`) and discuss every disagreement.
3. Edit this guide wherever a disagreement came from an unclear rule. Then freeze it as **rubric v1** with a date, before any main-set output is opened.

**Outcome (2026-11-19).** Both annotators labelled all 70 items blind.
- Agreement on SAFE: κ 0.79, AC1 0.89, so the 0.7 target was met. Presentation (AC1 0.53) and adaptation_needed (AC1 0.46) were low.
- 30 items were adjudicated (`data/calibration/pilot/TO_ADJUDICATE.csv` → `adjudicated.csv`). A first AI adjudication (2026-11-19) sided with the lenient label on every SAFE disagreement. The owner reviewed all 30 on 2026-11-20 (`owner_review_2026-11-20.csv`: 16 ACCEPT, 14 OVERRIDE).
- All 5 SAFE disagreements were "if"-clause, fragment and relevance-cue cases. All 5 resolve to **UNSAFE** under the clarifications above.
- Adjudicated SAFE: careful prompts 46/50, realistic prompt 6/20 (`agreement_vs_adjudicated.md`).
- v1.1 (2026-11-19) added the anchors; v1.2 (2026-11-20) replaced the AI-written "if"-clause, level-3 and target-wording rulings with the owner's. No main-study output had been labelled.
