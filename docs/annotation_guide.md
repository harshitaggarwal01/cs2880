# Annotation Guide (rubric v1, to be frozen after dev calibration)

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

### presentation 0–3
- **0** harder to read than the original;
- **1** negligible change (near-copy, `NO_ADAPT`) or a flawed result (fragments: `HARMFUL_FRAGMENT`);
- **2** clearly improved;
- **3** substantially improved.

Leave blank for `NO_REWRITE_NEEDED` outputs and fill `abstention_appropriate` instead.

### abstention_appropriate (NO_REWRITE_NEEDED only)
- **YES** if the original is already short and clear (Example 2: "Lisa has 18 more dresses than Ana…").
- **NO** if it was dense enough to benefit from the transformation (Sonnet on the payroll problem).

### adaptation_needed (judged on the original, once per source)
Would a reader who struggles with dense text plausibly benefit from the requested transformation? YES / NO / UNCLEAR.

## Allowed versus not allowed

**Allowed (accommodation):**
- shorter sentences;
- conditional or relative clauses split into separate sentences;
- passive voice made active;
- simpler non-math vocabulary ("fond of" → "like");
- pronoun → unambiguous referent;
- one fact per line;
- filler removed;
- "If X, how many…?" restated as "X. How many…?" when X is clearly intended as given;
- regrouping facts by person or object, as long as no fact is misattributed and no values or operations are added.

**Not allowed (modification):**
- changing or dropping any quantity, unit, relation, quantifier, condition, time order, or the unknown;
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
