# Concrete Examples: Real LLM Outputs from the Pilot

**SafeAdapt-Math · CS 2880 · pilot run 2026-10-16**

The professor asked for concrete examples: actual LLM outputs and what we want to achieve. This document answers that. Every adaptation below is a **verbatim model output**, copied programmatically from `pilot/pilot_outputs.jsonl`, not retyped. Every source is a real GSM8K problem.

## What was run

| | |
|---|---|
| Source problems | The 10 frozen **dev** problems (GSM8K *train* split, seed 2880). The 100 held-out test problems were not touched. |
| Prompts | `plain_v1` and `chunked_v1` (our constrained prompts), plus `naive_v1`: the realistic request a teacher might type, *"Rewrite this math word problem so it is easier to understand for a student with ADHD or dyslexia. Use simple language and break it into small chunks."* |
| Models | Claude Haiku 5.5 and Claude Opus 5.5 (all three prompts); Claude Sonnet 5.5 (plain only — its other two runs were stopped by an Anthropic safety classifier, a false positive we did not try to work around). |
| Outputs | 70 (10 problems × 7 model-prompt combinations) |
| Labels | **Preliminary**: proposed by an AI annotator (Claude) using our rubric. **Both teammates must verify them before any number here is quoted as a finding.** |

### Limitations of this pilot

1. These are not the study's models. The main study uses `gpt-6-luna` and `gemini-3.8-flash`, so that the critic (Claude) comes from a different model family than the generators.
2. The outputs were generated through Claude Code subagents, not raw API calls:
   - each subagent saw all 10 problems of one condition in one session;
   - a harness system prompt was present;
   - sampling settings were not controlled.

   Treat them as illustrations, not measurements.
3. With n = 10 problems, nothing here estimates a rate.
4. The dev problems come from GSM8K, which the models have probably seen during training.

## Pilot results in one table (preliminary labels)

| Model · prompt | n | SAFE | SAFE & useful | What we saw |
|---|---:|---:|---:|---|
| Haiku · plain | 10 | 10 | 5 | No corruption. Several near-copies that changed almost nothing (labelled `NO_ADAPT`). |
| Haiku · chunked | 10 | 10 | 6 | No corruption. In 4 of 10, "If …" clauses were left as sentence fragments. |
| Opus · plain | 10 | 10 | 9 | Faithful and readable. |
| Opus · chunked | 10 | 10 | 10 | Faithful; one fact per line. |
| Sonnet · plain | 10 | 10 | 7 | Faithful. Over-abstained on one dense problem. |
| **Haiku · naive teacher prompt** | 10 | **7** | 7 | 3 unsafe: "Step 1/2/3" labels mirroring the solution (×2); "Stories 11 to 20" leaks an intermediate count. |
| **Opus · naive teacher prompt** | 10 | **0** | 0 | 10/10 appended "Steps to try" or a hint with equations already set up. Also relevance leakage ("…extra information you don't need") and an intermediate value ("The other 10 floors"). |

Mathematical-fidelity failures observed in all 70 outputs: **0**.

The deterministic checker flagged **13 of 13** unsafe outputs as REJECT. It also wrongly REJECTed 1 of 57 safe outputs and sent 15 more to REVIEW.

### What this changes about our premise

The literature gives us the "omits or changes the math" premise:
- Norberg et al. report that, among the LLMs they tried, only GPT-4 kept problem structure intact.
- Patel et al. 2023 found GPT-3 simplifications "noisy and often unrelated to the input".
- InfoLossQA and Agrawal & Carpuat show that simplification loses information.

In our tiny pilot, current frontier models given *constrained* prompts did not corrupt the mathematics of easy problems. The failure that did show up, and showed up often, is **instructional leakage under the realistic prompt teachers actually use**. The verifier still matters (the constructed cases at the end show what it must catch), but the headline risk to test is:

> *An "accessible" version produced the way teachers actually use these tools is frequently a different, easier task: same numbers, same answer, but the reasoning is done for the student.*

That is why the main study runs the realistic prompt on all 100 main problems as a co-primary condition, alongside the constrained prompts.

---

### Example 1 — Faithful, genuinely useful chunking (SAFE, useful)

**Source** `gsm8k-train-1795` (GSM8K train split; reference answer 100)

> Mary and her two friends came up with the idea of collecting marbles each day for their play on weekends. From Monday to Friday, Mary collected twice as many red marbles as Jenny and half the number of blue marbles collected by Anie, who collected 20 more red marbles than Mary and twice the number of blue marbles Jenny collected. If Jenny collected 30 red marbles and 25 blue marbles, what's the total number of blue marbles collected by the friends together?

**Chunked adaptation** — `claude-opus-5-5`, prompt `chunked_v1`, status `REWRITTEN`

```text
- Mary and her two friends came up with the idea of collecting marbles each day for their play on weekends.
- From Monday to Friday, Mary collected twice as many red marbles as Jenny.
- Mary collected half the number of blue marbles collected by Anie.
- Anie collected 20 more red marbles than Mary.
- Anie collected twice the number of blue marbles Jenny collected.
- Jenny collected 30 red marbles.
- Jenny collected 25 blue marbles.
Question: What's the total number of blue marbles collected by the friends together?
```

**Why it is the target behavior.** The original packs four relations into one sentence with a relative clause ("…Anie, who collected…"). The adaptation gives one relation per line, keeps every quantity and every direction ("twice as many", "half the number", "20 more"), resolves "who" to Anie (unambiguous), and adds no operation words. All three models did this correctly under the constrained prompts.

---

### Example 2 — Correct abstention (SAFE, useful)

**Source** `gsm8k-train-3578` (GSM8K train split; reference answer 15)

> Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?

**Haiku, plain** — `claude-haiku-5-5`, prompt `plain_v1`, status `NO_REWRITE_NEEDED`

```text
Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?
```

**Opus, plain** — `claude-opus-5-5`, prompt `plain_v1`, status `NO_REWRITE_NEEDED`

```text
Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?
```

**Sonnet, plain** — `claude-sonnet-5-5`, prompt `plain_v1`, status `NO_REWRITE_NEEDED`

```text
Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?
```

**Why it matters.** The problem is already two short sentences. All three models returned `NO_REWRITE_NEEDED` with the text unchanged. "Know when not to rewrite" is a measurable behavior (annotated as `abstention_appropriate`). Over-abstention is also observed: Sonnet abstained on the dense payroll problem (`gsm8k-train-2016`), which we label a missed adaptation.

---

### Example 3 — Presentation failure under the constrained chunking prompt (SAFE but not useful)

**Source** `gsm8k-train-1097` (GSM8K train split; reference answer 50)

> Out of the 200 cookies that Javier baked from the recipe he learned online, his wife took 30%, and his daughter took 40 from the remaining cookies. If he ate half of the remaining cookies, how many cookies did they not eat?

**Haiku, chunked** — `claude-haiku-5-5`, prompt `chunked_v1`, status `REWRITTEN`

```text
- Out of the 200 cookies that Javier baked from the recipe he learned online, his wife took 30%.
- His daughter took 40 from the remaining cookies.
- If he ate half of the remaining cookies.
Question: How many cookies did they not eat?
```

**Opus, chunked (for comparison)** — `claude-opus-5-5`, prompt `chunked_v1`, status `REWRITTEN`

```text
- Javier baked 200 cookies from the recipe he learned online.
- Out of the 200 cookies, Javier's wife took 30%.
- Javier's daughter took 40 from the remaining cookies.
- Javier ate half of the remaining cookies.
Question: How many cookies did they not eat?
```

**What went wrong.** Haiku left conditional clauses as stand-alone sentence fragments ("- If he ate half of the remaining cookies."). It happened in 4 of Haiku's 10 chunked outputs. The mathematics is intact, but a fragment that starts with "If" and never finishes is plausibly *harder* for the readers chunking is meant to help. Opus converts the conditional into a statement, which is the reading the original intends. This is why `SAFE` and `SAFE_AND_USEFUL` are separate endpoints.

---

### Example 4 — Realistic teacher prompt: the model appends a solution plan (UNSAFE: strategy leakage)

**Source** `gsm8k-train-1097` (GSM8K train split; reference answer 50)

> Out of the 200 cookies that Javier baked from the recipe he learned online, his wife took 30%, and his daughter took 40 from the remaining cookies. If he ate half of the remaining cookies, how many cookies did they not eat?

**Opus, naive teacher prompt** — `claude-opus-5-5`, prompt `naive_v1`, free-text reply

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

**What went wrong.** The prompt was what a teacher might actually type: *"Rewrite this math word problem so it is easier to understand for a student with ADHD or dyslexia. Use simple language and break it into small chunks."* The rewritten problem itself is faithful, but the reply appends "Steps to try" that tell the learner exactly which operations to perform and in what order ("Find 30% of 200. Subtract it from 200…"). The final answer is unchanged; the task is not. The learner no longer has to decide what to do, which is a large part of what a word problem assesses. **Opus did this in 10 of 10 naive-prompt outputs.** If a teacher pastes the whole reply into a worksheet, the accessible version is a different (easier) task than the one given to peers.

---

### Example 5 — Relevance leakage (UNSAFE)

**Source** `gsm8k-train-1795` (GSM8K train split; reference answer 100)

> Mary and her two friends came up with the idea of collecting marbles each day for their play on weekends. From Monday to Friday, Mary collected twice as many red marbles as Jenny and half the number of blue marbles collected by Anie, who collected 20 more red marbles than Mary and twice the number of blue marbles Jenny collected. If Jenny collected 30 red marbles and 25 blue marbles, what's the total number of blue marbles collected by the friends together?

**Opus, naive teacher prompt** — `claude-opus-5-5`, prompt `naive_v1`, free-text reply

```text
This one has a lot of information packed together, so here it is broken apart:

**Collecting Marbles**

Three friends collect marbles from Monday to Friday:
**Mary**, **Jenny**, and **Anie**.

They collect **red** marbles and **blue** marbles.

**Jenny:**
- Red marbles: **30**
- Blue marbles: **25**

**Mary:**
- Red marbles: **2 times** as many as Jenny
- Blue marbles: **half** as many as Anie

**Anie:**
- Red marbles: **20 more** than Mary
- Blue marbles: **2 times** as many as Jenny

**Question:** How many **blue** marbles did the three friends collect altogether?

---

**Helpful tip:** The question only asks about **blue** marbles. The red marble facts are extra information you don't need.

**Steps to try:**
1. Find Anie's blue marbles (use Jenny's number).
2. Find Mary's blue marbles (use Anie's number).
3. Add Jenny's, Anie's, and Mary's blue marbles.

A table with one row per friend and columns for Red and Blue can also help students organize this one.
```

**What went wrong.** Besides the step plan, the reply says "The red marble facts are extra information you don't need." Deciding which information is relevant is part of the original task (and distractor sensitivity is a documented difficulty factor, cf. GSM-IC). Note also the bolding, which is harmless when it marks every quantity but becomes a relevance cue if it marks only some.

---

### Example 6 — Intermediate-result leakage, in two different forms (UNSAFE)

**Source** `gsm8k-train-5378` (GSM8K train split; reference answer 270)

> James builds a 20 story building.  The first 10 stories are each 12 feet tall each.  The remaining floors are each 3 feet taller.  How tall is the building?

**Haiku, naive teacher prompt** — `claude-haiku-5-5`, prompt `naive_v1`, free-text reply

```text
James builds a building that has 20 stories (floors).

Stories 1 to 10:
- Each story is 12 feet tall.

Stories 11 to 20:
- Each story is 3 feet taller than each of the first 10 stories.

Question: How tall is the whole building?
```

**Opus, naive teacher prompt** — `claude-opus-5-5`, prompt `naive_v1`, free-text reply

```text
Here's a simpler version:

**James's Building**

James builds a building with **20 floors**.

**Bottom part:**
- The first **10** floors
- Each one is **12 feet** tall

**Top part:**
- The other **10** floors
- Each one is **3 feet taller** than a bottom floor

**Question:** How tall is the whole building?

---

**Steps to try:**
1. Find the height of the bottom 10 floors.
2. Find how tall one top floor is.
3. Find the height of the top 10 floors.
4. Add the two parts together.

A quick sketch of a tall building split into a bottom half and a top half can really help here.
```

**What went wrong.** The original says "the remaining floors"; the learner must work out that there are 20 − 10 = 10 of them. Haiku's headings "Stories 11 to 20" and Opus's "The other **10** floors" both hand over that intermediate fact. Haiku's version is subtle: no new number is stated as a result, and no operation is named. The deterministic checker caught both (new number 11 or 10 that is derivable from source numbers).

---

### Example 7 — Layout that mirrors the solution (UNSAFE, mild: structural leakage)

**Source** `gsm8k-train-5508` (GSM8K train split; reference answer 180)

> Carly is making a beaded corset. She's going to add 50 rows of purple beads with 20 beads per row, 40 rows of blue beads with 18 beads per row, and 80 gold beads. If beads cost $1 per 10 beads, how much do all the beads she bought cost?

**Haiku, naive teacher prompt** — `claude-haiku-5-5`, prompt `naive_v1`, free-text reply

```text
Carly is making a beaded corset.

Step 1: Purple beads
- She adds 50 rows of purple beads.
- Each row has 20 beads.

Step 2: Blue beads
- She adds 40 rows of blue beads.
- Each row has 18 beads.

Step 3: Gold beads
- She adds 80 gold beads.

The beads cost $1 for every 10 beads.

Question: How much do all the beads Carly bought cost?
```

**Haiku, constrained chunked prompt (for comparison)** — `claude-haiku-5-5`, prompt `chunked_v1`, status `REWRITTEN`

```text
- Carly is making a beaded corset.
- She's going to add 50 rows of purple beads with 20 beads per row.
- She's going to add 40 rows of blue beads with 18 beads per row.
- She's going to add 80 gold beads.
- Beads cost $1 per 10 beads.
Question: How much do all the beads she bought cost?
```

**Why it is a borderline-but-real case.** "Step 1: Purple beads / Step 2: Blue beads / Step 3: Gold beads" contains no numbers that were not in the original and names no operation, but the labels turn the problem statement into a solution sequence (count each colour, then combine). The constrained prompt, which forbids "Step" labels, produced plain one-fact-per-line chunks instead. This distinction—*chunking the problem* versus *chunking the solution*—is the core of our leakage rubric (level 1, "structural cue").

---

### Example 8 — Silent vs disclosed disambiguation (RESOLVED ambiguity + leakage)

**Source** `gsm8k-train-2998` (GSM8K train split; reference answer 750)

> As a freelancer, Katherine takes 20 hours to develop a website for her clients. Her junior, Naomi, takes 1/4 times more time to complete creating a similar website. If many clients required her to build their websites in a particular year, and she gave her junior 30 websites to develop, calculate the total number of hours Katherine's junior took to create the 30 websites.

**Opus, naive teacher prompt** — `claude-opus-5-5`, prompt `naive_v1`, free-text reply

```text
Here's a simpler version in small chunks:

**Building Websites**

Katherine builds websites.

It takes Katherine **20 hours** to build **1** website.

Naomi works for Katherine.

Naomi is slower. She takes **1/4 more time** than Katherine to build 1 website.
(That means 20 hours, plus an extra 1/4 of 20 hours.)

One year, Katherine gives Naomi **30** websites to build.

**Question:** How many hours in total does Naomi take to build all 30 websites?

---

**Steps to try:**
1. Find 1/4 of 20 hours.
2. Add that to 20 hours. This is Naomi's time for 1 website.
3. Multiply Naomi's time for 1 website by 30.

Note: I clarified the phrase "1/4 times more time" from the original, since it can be confusing. If you want students to practice interpreting that wording, you could leave the parenthetical line out.
```

**Haiku, naive teacher prompt** — `claude-haiku-5-5`, prompt `naive_v1`, free-text reply

```text
Katherine is a freelancer. She makes websites for her clients.

Facts about Katherine:
- Katherine takes 20 hours to make one website.

Facts about her junior, Naomi:
- Naomi takes 1/4 times more time than Katherine to make a similar website.
- In one year, many clients asked Katherine to build their websites.
- Katherine gave Naomi 30 websites to make.

Question: What is the total number of hours that Naomi took to make the 30 websites?
```

**What happened.** "Takes 1/4 times more time" is ambiguous. Opus interprets it ("20 hours, plus an extra 1/4 of 20 hours"), matching GSM8K's reference solution, and *discloses* the change in a note to the teacher—good practice, but the interpretation is still part of the task the original posed. Haiku keeps the ambiguous wording but files "many clients asked Katherine…" under "Facts about her junior, Naomi" (entity-grouping error; mathematics unaffected). We annotate ambiguity as `NONE / NEW / RESOLVED` so these are counted rather than ignored.

---

### Example 9 — A checker false alarm (why a lexical verifier is not enough)

**Source** `gsm8k-train-5508` (GSM8K train split; reference answer 180)

> Carly is making a beaded corset. She's going to add 50 rows of purple beads with 20 beads per row, 40 rows of blue beads with 18 beads per row, and 80 gold beads. If beads cost $1 per 10 beads, how much do all the beads she bought cost?

**Sonnet, plain** — `claude-sonnet-5-5`, prompt `plain_v1`, status `REWRITTEN`

```text
Carly is making a beaded corset. She is going to add 50 rows of purple beads with 20 beads per row. She is going to add 40 rows of blue beads with 18 beads per row. She is going to add 80 gold beads. Beads cost $1 per 10 beads. How much do all the beads she bought cost?
```

**What happened.** The adaptation is faithful. The deterministic layer still flags it for REVIEW because "add" appears three times instead of once—here "add" means *attach beads*, not arithmetic. After refinement, repeated use of a cue word that already appears in the source is downgraded from REJECT to REVIEW. Across the pilot, the deterministic layer flagged 16 of 57 safe outputs (1 REJECT, 15 REVIEW) while catching all 13 unsafe ones: high recall, poor precision. That is the job of the critic and program layers.

---

## Constructed examples (NOT model outputs)

The cases below were **written by us** to define the rubric and to unit-test the verifier (`tests/stress_cases.jsonl`). **None of them was observed in the pilot.** Never present them as model behavior. The last column shows the decision the deterministic layer *alone* gives today; the critic and program layers exist for the cases it can only send to REVIEW.

| Case | Original → adaptation (abridged) | Failure | Deterministic layer |
|---|---|---|---|
| Condition dropped | "…Six Tuesday sales were returned…" → return sentence missing | `COND_OMIT` (answer 66 → 72) | REJECT (number 6 missing) |
| Same numbers, different math | "three **times as many** as Lena" → "three **more** than Lena" | `REL_CHANGE` (24 → 11) | REVIEW only — needs critic/program layer |
| Operation leak | "…18 rows with 24 seats…" → "First multiply 18 by 24. Then subtract…" | `LEAK_OPERATION` | REJECT |
| Intermediate leak | "15 tickets in each of 8 rows" → "sold 120 tickets" | `LEAK_INTERMEDIATE` | REJECT (120 = 15×8) |
| Unit swap | "12 feet … four feet" → "12 meters … four meters" | `UNIT_CHANGE` (answer still 8) | REVIEW |
| Quantifier | "**Each** of the 5 students" → "**Some** of the 5 students" | `QUANTIFIER_CHANGE`, unsolvable | REVIEW |
| Solution-shaped chunks | "Step 1: Find the total… Step 2: Subtract…" | `LEAK_STEPS` | REJECT |
| Answer leak | "…Now Sam has 9 apples…" | `LEAK_ANSWER` | REJECT |
| Relevance leak | "You don't need the red pens." | `LEAK_RELEVANCE` | REVIEW |

## What we want to achieve (the target behavior, in one picture)

```text
ORIGINAL   Out of the 200 cookies that Javier baked …, his wife took 30%, and his daughter took 40
           from the remaining cookies. If he ate half of the remaining cookies, how many cookies did
           they not eat?

TARGET     - Javier baked 200 cookies from the recipe he learned online.          <- one fact per line
(Opus,     - Out of the 200 cookies, Javier's wife took 30%.                       <- same numbers, same relations
 chunked)  - Javier's daughter took 40 from the remaining cookies.                 <- no operation words
           - Javier ate half of the remaining cookies.                             <- no steps, no hints
           Question: How many cookies did they not eat?                            <- same unknown

NOT THIS   …same problem… + "Steps to try: 1. Find 30% of 200. Subtract it from 200. …"
(Opus,     <- answer unchanged, task changed: the learner no longer decides what to do
 naive)
```
