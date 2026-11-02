# Real Examples from Our Runs

**SafeAdapt-Math · CS 2880 · for discussion with the professor**

Every rewrite and every checker verdict below is copied programmatically from the run files, not retyped. Sources are real GSM8K problems from our 10 practice (dev) problems; the 124 study problems have not been used.

## What was run (Nov 2, run `anthropic-v1`)

| | |
|---|---|
| Problems | 10 practice problems (GSM8K train, frozen with seed 2880) |
| Rewriters | Claude Haiku 5.5 and Claude Sonnet 5.5, real API calls |
| Styles | `plain_v1` (plain language) and `chunked_v1` (one fact per line), our careful prompts |
| Outputs | 40 rewrites |
| Checker | rules → AI reviewer (Claude Opus 5.5) → extract both versions as a program and recompute the answer |
| Cost | $1.19 total: rewriting $0.05, AI reviewer $0.59, answer recompute $0.56 (123 API calls) |
| Checker decisions | 17 PASS · 22 REVIEW · 1 REJECT |

**Read these as examples, not rates.** There are no human labels yet (calibration labelling is next), the realistic teacher prompt was not part of this run, and the reviewer is from the same company as the rewriters.

### Decisions by model and style

| Model · style | PASS | REVIEW | REJECT | Same answer when recomputed |
|---|---:|---:|---:|---:|
| Claude Haiku 5.5 · plain language | 3 | 7 | 0 | 10/10 |
| Claude Haiku 5.5 · chunked | 4 | 6 | 0 | 10/10 |
| Claude Sonnet 5.5 · plain language | 4 | 5 | 1 | 10/10 |
| Claude Sonnet 5.5 · chunked | 6 | 4 | 0 | 10/10 |

---

## Example 1: one problem, four rewrites (false alarm, real catch, clean pass)

**Original** (`gsm8k-train-2016`, GSM8K train; answer 310)

> Vikki worked 42 hours in one week. Her hourly pay rate is $10. From her weekly earnings, 20% is deducted as tax, 5% is deducted as insurance cover, and $5 is deducted for union dues. How much money, in dollars, does Vikki take home after deductions?


**Claude Sonnet 5.5 · plain language** (status `REWRITTEN`)

```text
Vikki worked 42 hours in one week. She is paid $10 per hour. Money is taken out of her weekly earnings in three ways: 20% is taken out for tax, 5% is taken out for insurance, and $5 is taken out for union dues. How much money, in dollars, does Vikki take home after these deductions?
```

- **Decision: REJECT** (reasons: `det:LEAK_DERIVED_VALUE`)
- Rules (layer 1): `LEAK_DERIVED_VALUE` (REJECT): new numbers equal to values derivable from the source: 3; `RELATION_OR_QUANTIFIER_ADDED` (REVIEW): phrases not in source: per
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 310 vs rewrite 310

**Our read: false alarm.** The rewrite is faithful and the answer is unchanged. The rule for leaked derived values fired because the new word "three" (counting the deductions) happens to equal a number that can be computed from the problem. Counting words should not count as leaks; this rule gets tuned on practice problems.

**Claude Haiku 5.5 · chunked** (status `REWRITTEN`)

```text
- Vikki worked 42 hours in one week.
- Her hourly pay rate is $10.
- From her weekly earnings, 20% is deducted as tax.
- 5% is deducted as insurance cover.
- $5 is deducted for union dues.
Question: How much money, in dollars, does Vikki take home after deductions?
```

- **Decision: REVIEW** (reasons: `critic:UNSURE`)
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **UNSURE**, codes AMBIGUITY_NEW
- Answer recompute (layer 3): MATCH, original 310 vs rewrite 310

  - Reviewer's evidence, quoted: *"In the original, one sentence makes 'From her weekly earnings' govern all three deductions. Once split into bullets, the phrase attaches only to the tax line. The insurance line no longer says what the 5% is taken from. A learner could now read it as 5% of the amount left after tax, which gives a different result."*

**Our read: real catch.** Splitting the sentence into bullets detached "from her weekly earnings" from the 5% line. A student could take 5% of what is left after tax and get a different answer. No word-matching rule sees this; the AI reviewer did, and the item goes to a human.

**Claude Sonnet 5.5 · chunked** (status `REWRITTEN`)

```text
- Vikki worked 42 hours in one week.
- Her hourly pay rate is $10.
- From her weekly earnings, 20% is deducted as tax.
- From her weekly earnings, 5% is deducted as insurance cover.
- From her weekly earnings, $5 is deducted for union dues.
Question: How much money, in dollars, does Vikki take home after deductions?
```

- **Decision: PASS**
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 310 vs rewrite 310

**Our read: the right way to chunk it.** Sonnet repeated "From her weekly earnings" on every deduction line, which keeps the meaning that Haiku's version lost. Same layout, and this time the math is unchanged.

**Claude Haiku 5.5 · plain language** (status `NO_REWRITE_NEEDED`)

```text
Vikki worked 42 hours in one week. Her hourly pay rate is $10. From her weekly earnings, 20% is deducted as tax, 5% is deducted as insurance cover, and $5 is deducted for union dues. How much money, in dollars, does Vikki take home after deductions?
```

- **Decision: PASS**
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 310 vs rewrite 310

**Our read: correct abstention.** Haiku judged the problem already clear and returned it unchanged.

**Takeaway.** Same problem, four outputs: a false alarm, a real catch, the fix done right, and a safe no-change. The checker needs every layer, and the review step needs to stay.

---

## Example 2: a faithful rewrite flagged by an over-strict rule

**Original** (`gsm8k-train-1795`, GSM8K train; answer 100)

> Mary and her two friends came up with the idea of collecting marbles each day for their play on weekends. From Monday to Friday, Mary collected twice as many red marbles as Jenny and half the number of blue marbles collected by Anie, who collected 20 more red marbles than Mary and twice the number of blue marbles Jenny collected. If Jenny collected 30 red marbles and 25 blue marbles, what's the total number of blue marbles collected by the friends together?


**Claude Sonnet 5.5 · chunked** (status `REWRITTEN`)

```text
- Mary and her two friends came up with the idea of collecting marbles each day for their play on weekends.
- From Monday to Friday, Mary collected twice as many red marbles as Jenny.
- From Monday to Friday, Mary collected half the number of blue marbles collected by Anie.
- Anie collected 20 more red marbles than Mary.
- Anie collected twice the number of blue marbles Jenny collected.
- Jenny collected 30 red marbles.
- Jenny collected 25 blue marbles.
Question: What's the total number of blue marbles collected by the friends together?
```

- **Decision: REVIEW** (reasons: `program:RELATIONS_DIFFER`)
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 100 vs rewrite 100; extracted relation types differ

**Our read: false alarm.** One fact per line, every relation kept, same answer. The recompute layer compares the *types* of relations it extracts, and splitting compound sentences changes how they are extracted. That comparison fired on 18 of 40 rewrites, all with matching answers; it is the main cause of the review load.

---

## Example 3: one word changed, one rule fires

**Original** (`gsm8k-train-5510`, GSM8K train; answer 105)

> Karl, Ryan, and Ben are fond of collecting stickers. Karl has 25 stickers. Ryan has 20 more stickers than Karl. Ben has 10 fewer stickers than Ryan. They placed all their stickers in one sticker book. How many stickers did they place altogether?


**Claude Haiku 5.5 · plain language** (status `REWRITTEN`)

```text
Karl, Ryan, and Ben like to collect stickers. Karl has 25 stickers. Ryan has 20 more stickers than Karl. Ben has 10 fewer stickers than Ryan. They put all of their stickers into one sticker book. How many stickers did they put in the book in total?
```

- **Decision: REVIEW** (reasons: `det:RELATION_OR_QUANTIFIER_LOST`, `det:RELATION_OR_QUANTIFIER_ADDED`, `det:TARGET_WORDING_CHANGED`)
- Rules (layer 1): `RELATION_OR_QUANTIFIER_LOST` (REVIEW): phrases fewer than in source: altogether; `RELATION_OR_QUANTIFIER_ADDED` (REVIEW): phrases not in source: total; `TARGET_WORDING_CHANGED` (REVIEW): question content-word overlap 0.33
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 105 vs rewrite 105

**Claude Sonnet 5.5 · plain language** (status `REWRITTEN`)

```text
Karl, Ryan, and Ben like to collect stickers. Karl has 25 stickers. Ryan has 20 more stickers than Karl. Ben has 10 fewer stickers than Ryan. They put all their stickers in one sticker book. How many stickers did they put in the book altogether?
```

- **Decision: PASS**
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 105 vs rewrite 105

**Our read.** Both plain rewrites are faithful. Haiku changed "altogether" to "in total" and "placed" to "put … into the book", so the rules saw a quantifier lost, one added, and the question reworded: REVIEW. Sonnet kept "altogether": PASS. The rules are deliberately sensitive to math words; the question for tuning is how much synonym change to allow.

---

## Example 4: a rewrite that quietly resolves an ambiguity

**Original** (`gsm8k-train-5378`, GSM8K train; answer 270)

> James builds a 20 story building. The first 10 stories are each 12 feet tall each. The remaining floors are each 3 feet taller. How tall is the building?


**Claude Sonnet 5.5 · plain language** (status `REWRITTEN`)

```text
James builds a building with 20 stories. Each of the first 10 stories is 12 feet tall. Each of the remaining stories is 3 feet taller than each of the first 10 stories. How tall is the building?
```

- **Decision: REVIEW** (reasons: `program:RELATIONS_DIFFER`)
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 270 vs rewrite 270; extracted relation types differ

**Our read: worth discussing.** The original says the remaining floors are "3 feet taller" without saying taller than what. Sonnet made it explicit: "3 feet taller than each of the first 10 stories." That is the intended reading (answer 270 either way), but it removes an interpretation step the original left to the student. Our rubric records this as *resolved ambiguity*: is that a fair accommodation or a small modification?

---

## Example 5: repeating the original's own words triggers a soft flag

**Original** (`gsm8k-train-5508`, GSM8K train; answer 180)

> Carly is making a beaded corset. She's going to add 50 rows of purple beads with 20 beads per row, 40 rows of blue beads with 18 beads per row, and 80 gold beads. If beads cost $1 per 10 beads, how much do all the beads she bought cost?


**Claude Sonnet 5.5 · chunked** (status `REWRITTEN`)

```text
- Carly is making a beaded corset.
- She's going to add 50 rows of purple beads with 20 beads per row.
- She's going to add 40 rows of blue beads with 18 beads per row.
- She's going to add 80 gold beads.
- Beads cost $1 per 10 beads.
Question: How much do all the beads she bought cost?
```

- **Decision: REVIEW** (reasons: `det:LEAK_OPERATION`)
- Rules (layer 1): `LEAK_OPERATION` (REVIEW): more uses of source cue words: addinged
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 180 vs rewrite 180

  - Reviewer's evidence, quoted: *"Only the layout changed: one list became three sentences. Every quantity, unit and color is kept, and each quantity stays with the same color. Repeating 'She's going to add' does not introduce an operation or steps beyond the original listing."*
  - Reviewer's evidence, quoted: *"The conditional became a plain statement. The pricing condition is the same, so the meaning is unchanged."*
  - Reviewer's evidence, quoted: *"The target is identical, including 'all' and the original's 'bought' wording."*

**Our read: safe, correctly sent to REVIEW rather than rejected.** "Add" is an operation word, but it already appears in the original ("add 50 rows of beads"), so the rule downgrades it to REVIEW. The reviewer explains why it is fine.

---

## Example 6: the model correctly declines to rewrite

**Original** (`gsm8k-train-3578`, GSM8K train; answer 15)

> Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?


**Claude Haiku 5.5 · plain language** (status `NO_REWRITE_NEEDED`)

```text
Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?
```

- **Decision: PASS**
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 15 vs rewrite 15

**Our read: correct abstention.** The problem is already short and clear, and the prompt allows `NO_REWRITE_NEEDED`. Changing nothing is the safe choice here.

---

## Example 7: clean chunking

**Original** (`gsm8k-train-1097`, GSM8K train; answer 50)

> Out of the 200 cookies that Javier baked from the recipe he learned online, his wife took 30%, and his daughter took 40 from the remaining cookies. If he ate half of the remaining cookies, how many cookies did they not eat?


**Claude Sonnet 5.5 · chunked** (status `REWRITTEN`)

```text
- Javier baked 200 cookies from the recipe he learned online.
- His wife took 30% of the 200 cookies.
- His daughter took 40 from the remaining cookies.
- Javier ate half of the remaining cookies.
Question: How many cookies did they not eat?
```

- **Decision: PASS**
- Rules (layer 1): no flags
- AI reviewer (layer 2, Claude Opus 5.5): **SAFE**
- Answer recompute (layer 3): MATCH, original 50 vs rewrite 50

**Our read: what we want.** One fact per line, original wording, nothing added, question last. Compare it with what the realistic teacher prompt produced on the same problem (next section).

---

## From the earlier pilot (Oct 16): the realistic teacher prompt

These outputs are from our first, smaller pilot. They were generated through Claude Code subagents, not the API pipeline, and their labels are preliminary (AI-proposed, being re-labelled by both teammates). The prompt is what a teacher might actually type: *"Rewrite this math word problem so it is easier to understand for a student with ADHD or dyslexia. Use simple language and break it into small chunks."* With preliminary labels, 13 of 20 realistic-prompt rewrites were unsafe, against 0 of 50 under our careful prompts.

**Claude Opus 5.5 · realistic teacher prompt** on `gsm8k-train-1097` (answer 50)

> Out of the 200 cookies that Javier baked from the recipe he learned online, his wife took 30%, and his daughter took 40 from the remaining cookies. If he ate half of the remaining cookies, how many cookies did they not eat?

```text
Here's a rewritten version in small steps:

**Javier's Cookies**

1. Javier baked **200** cookies.
2. His wife took **30%** of the cookies.
3. Then his daughter took **40** of the cookies that were left.
4. Then Javier ate **half** of the cookies that were left.

**Question:** How many cookies were **not** eaten?

---

**Steps to try:**
1. Find 30% of 200. Subtract it from 200.
2. Subtract the 40 cookies his daughter took.
3. Find half of what is left. That is how many Javier ate.
4. The cookies still left at the end are the ones not eaten.

Tip: Have the student write the number of cookies left after each step so they can keep track.
```

**Strategy leakage.** The rewritten problem is faithful, but the appended "Steps to try" tell the student which operations to do and in what order. The answer is unchanged; the task is not. Opus did this in 10 of 10 realistic-prompt outputs.

**Claude Haiku 5.5 · realistic teacher prompt** on `gsm8k-train-5378` (answer 270)

> James builds a 20 story building. The first 10 stories are each 12 feet tall each. The remaining floors are each 3 feet taller. How tall is the building?

```text
James builds a building that has 20 stories (floors).

Stories 1 to 10:
- Each story is 12 feet tall.

Stories 11 to 20:
- Each story is 3 feet taller than each of the first 10 stories.

Question: How tall is the whole building?
```

**Intermediate-result leakage.** Splitting the building into stories 1–10 and 11–20 gives the student the count of the remaining floors (10), a value they were meant to work out.

---

## Appendix: all 40 checker decisions from this week's run

| Problem | Model · style | Decision | Reasons |
|---|---|---|---|
| `gsm8k-train-1097` | Haiku 5.5 · chunked | PASS | — |
| `gsm8k-train-1097` | Haiku 5.5 · plain | REVIEW | det:RELATION_OR_QUANTIFIER_LOST, det:TARGET_WORDING_CHANGED, program:RELATIONS_DIFFER |
| `gsm8k-train-1097` | Sonnet 5.5 · chunked | PASS | — |
| `gsm8k-train-1097` | Sonnet 5.5 · plain | PASS | — |
| `gsm8k-train-1795` | Haiku 5.5 · chunked | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-1795` | Haiku 5.5 · plain | REVIEW | det:RELATION_OR_QUANTIFIER_LOST, det:RELATION_OR_QUANTIFIER_ADDED, program:RELATIONS_DIFFER |
| `gsm8k-train-1795` | Sonnet 5.5 · chunked | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-1795` | Sonnet 5.5 · plain | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-2016` | Haiku 5.5 · chunked | REVIEW | critic:UNSURE |
| `gsm8k-train-2016` | Haiku 5.5 · plain | PASS | — |
| `gsm8k-train-2016` | Sonnet 5.5 · chunked | PASS | — |
| `gsm8k-train-2016` | Sonnet 5.5 · plain | REJECT | det:LEAK_DERIVED_VALUE |
| `gsm8k-train-2998` | Haiku 5.5 · chunked | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-2998` | Haiku 5.5 · plain | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-2998` | Sonnet 5.5 · chunked | PASS | — |
| `gsm8k-train-2998` | Sonnet 5.5 · plain | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-3578` | Haiku 5.5 · chunked | PASS | — |
| `gsm8k-train-3578` | Haiku 5.5 · plain | PASS | — |
| `gsm8k-train-3578` | Sonnet 5.5 · chunked | PASS | — |
| `gsm8k-train-3578` | Sonnet 5.5 · plain | PASS | — |
| `gsm8k-train-5378` | Haiku 5.5 · chunked | REVIEW | det:RELATION_OR_QUANTIFIER_LOST, program:RELATIONS_DIFFER |
| `gsm8k-train-5378` | Haiku 5.5 · plain | REVIEW | det:RELATION_OR_QUANTIFIER_LOST, program:RELATIONS_DIFFER |
| `gsm8k-train-5378` | Sonnet 5.5 · chunked | REVIEW | det:RELATION_OR_QUANTIFIER_LOST, program:RELATIONS_DIFFER |
| `gsm8k-train-5378` | Sonnet 5.5 · plain | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-5508` | Haiku 5.5 · chunked | REVIEW | det:LEAK_OPERATION |
| `gsm8k-train-5508` | Haiku 5.5 · plain | REVIEW | det:LEAK_OPERATION, det:RELATION_OR_QUANTIFIER_LOST, det:RELATION_OR_QUANTIFIER_ADDED, program:RELATIONS_DIFFER |
| `gsm8k-train-5508` | Sonnet 5.5 · chunked | REVIEW | det:LEAK_OPERATION |
| `gsm8k-train-5508` | Sonnet 5.5 · plain | REVIEW | det:LEAK_OPERATION, det:RELATION_OR_QUANTIFIER_LOST, det:RELATION_OR_QUANTIFIER_ADDED, program:RELATIONS_DIFFER |
| `gsm8k-train-5510` | Haiku 5.5 · chunked | PASS | — |
| `gsm8k-train-5510` | Haiku 5.5 · plain | REVIEW | det:RELATION_OR_QUANTIFIER_LOST, det:RELATION_OR_QUANTIFIER_ADDED, det:TARGET_WORDING_CHANGED |
| `gsm8k-train-5510` | Sonnet 5.5 · chunked | PASS | — |
| `gsm8k-train-5510` | Sonnet 5.5 · plain | PASS | — |
| `gsm8k-train-5951` | Haiku 5.5 · chunked | PASS | — |
| `gsm8k-train-5951` | Haiku 5.5 · plain | PASS | — |
| `gsm8k-train-5951` | Sonnet 5.5 · chunked | PASS | — |
| `gsm8k-train-5951` | Sonnet 5.5 · plain | PASS | — |
| `gsm8k-train-6838` | Haiku 5.5 · chunked | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-6838` | Haiku 5.5 · plain | REVIEW | det:RELATION_OR_QUANTIFIER_ADDED, program:RELATIONS_DIFFER |
| `gsm8k-train-6838` | Sonnet 5.5 · chunked | REVIEW | program:RELATIONS_DIFFER |
| `gsm8k-train-6838` | Sonnet 5.5 · plain | REVIEW | program:RELATIONS_DIFFER |

Files: `data/outputs/anthropic-v1/pilot_generations.jsonl` (rewrites), `pilot_generations.verify-critic-det-program.jsonl` (checker), `ledger.csv` (cost); earlier pilot in `pilot/`.
