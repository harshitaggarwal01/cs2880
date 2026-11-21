# Labelling quick guide (rubric v1.2)

**What you are judging:** is the ADAPTATION the *same task* as the ORIGINAL, made easier to *read* but not easier to *solve*?

## How to do one row (about 1.5 minutes)

1. Read the **ORIGINAL**, then the **ADAPTATION**. Label *everything* in the adaptation, including preambles and tips.
2. **Nothing wrong?** Set **QUICK = ALL CLEAR**. That fills math PASS, target PASS, solvability NO, ambiguity NONE and leakage 0 / NONE. Then set **presentation** and **adaptation_needed**. Done.
3. **Something wrong?** Leave QUICK blank and fill the columns left to right:
   - **Math:** check every number, unit, owner, relation, "each / all / remaining", condition ("If…"), the time order, and the question.
   - **Leakage:** does it give away anything the student had to work out? Pick the **most severe** level and its type.
   - **Presentation 0–3:** leave it blank if "model said" is NO_REWRITE_NEEDED, and fill **abstention_appropriate** instead.
   - **Rows where "model said" is NO_REWRITE_NEEDED** (the original came back unchanged): the math and leakage columns count as clean automatically. Fill only **abstention_appropriate** and **adaptation_needed** (E4, E5).
   - **failure_codes:** comma-separated (see the table below).
   - **evidence:** paste the exact offending words. It is required for any FAIL, solvability YES, ambiguity NEW, or leakage > 0.
   - **confidence:** use LOW together with UNSURE, and say why in **notes**.
4. The **done** column turns green when the row is complete. Save often. You can stop and resume any time.

**SAFE is computed for you:** math PASS + target PASS + solvability NO + ambiguity not NEW + leakage 0.

### The five rulings people get wrong (v1.2)
- **"If…" is a condition.** Keep it on the question. Stating it as an event, or leaving a dangling "If…" bullet, is not SAFE (E14, E19).
- **Every percent keeps its base.** "10% goes to savings" with no "of his pay" is ambiguity NEW (E20).
- **Level 3 is any value, range or set-up expression the student had to work out** (E27).
- **Relevance cues are level 2** ("Here is what you need to know") (E26). Step labels are level 1 (E23). **Any leak caps presentation at 2.**
- **Short is not the same as clear.** "3 feet taller" (than what?) makes adaptation_needed YES.

## Every value, with an example

| Field | Value | Use it when | Example |
|---|---|---|---|
| math_fidelity | **PASS** | every number, unit, owner, relation, condition, 'each/all/remaining', and time order kept | E1, E2 |
|  | **FAIL** | anything changed, missing, added or reordered (including an 'If' stated as an event) | E6–E16 |
|  | **UNSURE** | the text now allows two readings and you can't tell if the math survived | E19, E20 |
| target_preserved | **PASS** | same unknown, same unit, same person (rewording is fine) | E18 |
|  | **FAIL** | asks for something else | E17 |
|  | **UNSURE** | the question became unclear |  |
| solvability_changed | **NO** | still solvable with the same answer | E1, E13 |
|  | **YES** | unsolvable or a different answer | E6, E14 |
|  | **UNSURE** | goes with an UNSURE math call | E19 |
| ambiguity | **NONE** | one reading, as in the original | E1 |
|  | **NEW** | a second reading appeared | E12, E19, E20 |
|  | **RESOLVED** | the original was ambiguous and the rewrite picked one reading (say which in notes) | E21, E22 |
| leakage_level | **0** | nothing the student had to work out is given | E1 |
|  | **1** | STRUCTURE: step labels / solution-order layout | E23 |
|  | **2** | STEPS, OPERATION or RELEVANCE | E24–E26 |
|  | **3** | INTERMEDIATE or ANSWER | E27, E28 |
| leakage_type | **NONE** | level 0 | E1 |
|  | **STRUCTURE** | Step 1 / Step 2 labels | E23 |
|  | **STEPS** | a plan, tips, 'steps to try' | E25 |
|  | **OPERATION** | 'multiply', 'subtract', an equation | E24 |
|  | **RELEVANCE** | 'what you need to know', 'this fact is extra' | E26 |
|  | **INTERMEDIATE** | a derived value, range or set-up expression | E27 |
|  | **ANSWER** | the answer itself | E28 |
| presentation (REWRITTEN only) | **0** | harder to read | E29 |
|  | **1** | near-copy, fragments, or the original buried under added text | E3, E30 |
|  | **2** | clearer prose, OR any layout with added steps/hints/notes, OR any leak (cap 2) | E2, E23–E28 |
|  | **3** | one fact per line or grouped, question set apart, nothing added | E1 |
| abstention_appropriate | **YES** | model said NO_REWRITE_NEEDED and the original was already short and clear | E4 |
|  | **NO** | model said NO_REWRITE_NEEDED but the original needed help | E5 |
|  | **NA** | every REWRITTEN row | E1 |
| adaptation_needed (judge the ORIGINAL) | **YES** | a sentence over 20 words, or 3+ quantities/relations in one sentence, or an unclear relation ('3 feet taller' than what?) | E1, E5 |
|  | **NO** | short, clear sentences | E4, E9 |
|  | **UNCLEAR** | only with a note |  |
| confidence | **HIGH** | clear case |  |
|  | **MEDIUM** | a judgement call |  |
|  | **LOW** | you used UNSURE; explain in notes |  |

## Every failure code, with an example

| Code | Meaning | Example |
|---|---|---|
| `QTY_CHANGE` | a number changed | E6 |
| `QTY_OMIT` | a number missing | E7 |
| `QTY_ADD` | a new number added | E8 |
| `UNIT_CHANGE` | a unit changed | E9 |
| `ENTITY_CHANGE` | a quantity now belongs to someone/something else | E11 |
| `REL_CHANGE` | a relation changed (e.g. 3 times -> 3 more; direction flipped) | E10 |
| `COND_OMIT` | a condition dropped | E14 |
| `COND_ADD` | a condition added | E15 |
| `QUANTIFIER_CHANGE` | each/all/some/remaining/at least changed | E12 |
| `ORDER_CHANGE` | time order changed | E13 |
| `TARGET_CHANGE` | asks for something else | E17 |
| `SOLVABILITY_CHANGE` | unsolvable or a different answer now | E6 |
| `CONTRADICTION` | the text contradicts itself | E16 |
| `AMBIGUITY_NEW` | a new second reading | E12 |
| `FALSE_DISAMBIGUATION` | picked a reading that does not match the intended one | E22 |
| `DISAMBIGUATION` | picked one reading of an ambiguous original (note which) | E21 |
| `LEAK_ANSWER` | states the answer | E28 |
| `LEAK_INTERMEDIATE` | states an intermediate value (also as a range/heading) | E27 |
| `LEAK_OPERATION` | names an operation not in the original | E24 |
| `LEAK_STEPS` | a plan or steps to follow | E25 |
| `LEAK_RELEVANCE` | says which facts matter or don't | E26 |
| `LEAK_STRUCTURE` | layout/labels mirror the solution order | E23 |
| `NO_ADAPT` | near-copy, nothing really changed | E3 |
| `OVER_EDIT` | changed far more than needed | E29 |
| `HARMFUL_FRAGMENT` | sentence fragments that hurt reading | E19 |
| `ENTITY_GROUPING` | facts regrouped confusingly | E31 |
| `FORMAT_FAIL` | the requested format not followed | E32 |
| `EXTRA_TEXT` | preamble or teacher note around the problem | E33 |

## Worked examples (invented problems)

### Clean

**E1. Perfect chunked rewrite (use QUICK = ALL CLEAR)** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: - Maya has 12 apples. / - She gives 3 apples to each of her 2 friends. / - Then she buys 5 more apples. / Question: How many apples does Maya have now?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **3** · abstention_appropriate **NA** · adaptation_needed **YES**
- Why: Every number, owner, 'each', 'then' and the question survive. One fact per line, question set apart, nothing added. SAFE.

**E2. Good plain-language rewrite** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee, so how much money does she keep?
>
> ADAPTATION: Lena earns $15 an hour. She works 6 hours a day for 5 days. From her total pay, 10% goes to taxes. A club fee of $20 also comes out of her total pay. How much money does she keep?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES**
- Why: Same facts, shorter sentences, clearer prose, but not one-fact-per-line with the question set apart: presentation 2. SAFE.

**E3. Faithful but barely changed (near-copy)** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee, so how much money does she keep?
>
> ADAPTATION: Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee. How much money does she keep?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **NO_ADAPT**
- Why: Still SAFE (nothing wrong with the math), but the densest sentence is unchanged: presentation 1, code NO_ADAPT.

### Model said no rewrite needed

**E4. Abstention is right (short and clear)** (requested: plain; model said: NO_REWRITE_NEEDED)

> ORIGINAL: Sam has 5 pencils. He buys 4 more. How many pencils does Sam have?
>
> ADAPTATION: Sam has 5 pencils. He buys 4 more. How many pencils does Sam have?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · abstention_appropriate **YES** · adaptation_needed **NO**
- Why: Leave presentation BLANK. abstention_appropriate YES: two short sentences, one relation.

**E5. Abstention is wrong (dense original)** (requested: plain; model said: NO_REWRITE_NEEDED)

> ORIGINAL: Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee, so how much money does she keep?
>
> ADAPTATION: Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee, so how much money does she keep?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · abstention_appropriate **NO** · adaptation_needed **YES** · failure_codes **NO_ADAPT**
- Why: Presentation BLANK. abstention_appropriate NO: one 40-word sentence with five quantities needed a rewrite.

### Math fidelity

**E6. A number changed** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: - Maya has 12 apples. / - She gives 4 apples to each of her 2 friends. / - Then she buys 5 more apples. / Question: How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **3** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **QTY_CHANGE, SOLVABILITY_CHANGE** · evidence: "She gives 4 apples to each"
- Why: 3 became 4, so the answer changes (11 -> 9). Presentation is still judged on layout: 3.

**E7. A number dropped** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **QTY_OMIT, SOLVABILITY_CHANGE** · evidence: "(missing: Then she buys 5 more apples.)"
- Why: The +5 fact is gone. For an omission, write what is missing in evidence.

**E8. A number added** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. She eats 1 apple. Then she buys 5 more apples. How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **QTY_ADD, SOLVABILITY_CHANGE** · evidence: "She eats 1 apple."
- Why: A new quantity changes the answer.

**E9. Unit changed** (requested: plain; model said: REWRITTEN)

> ORIGINAL: A rope is 6 meters long. Jo cuts it into 3 equal pieces. How long is each piece?
>
> ADAPTATION: A rope is 6 feet long. Jo cuts it into 3 equal pieces. How long is each piece?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **NO** · failure_codes **UNIT_CHANGE, SOLVABILITY_CHANGE** · evidence: "6 feet"
- Why: Meters became feet: the answer is now 2 feet, not 2 meters.

**E10. Relation changed** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Tom has 3 times as many marbles as Ana. Ana has 8 marbles. How many marbles do they have together?
>
> ADAPTATION: Tom has 3 more marbles than Ana. Ana has 8 marbles. How many marbles do they have together?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **REL_CHANGE, SOLVABILITY_CHANGE** · evidence: "3 more marbles than Ana"
- Why: '3 times as many' is not '3 more'. Answer 32 -> 19.

**E11. Quantity moved to someone else** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Tom has 3 times as many marbles as Ana. Ana has 8 marbles. How many marbles do they have together?
>
> ADAPTATION: Ana has 3 times as many marbles as Tom. Ana has 8 marbles. How many marbles do they have together?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **ENTITY_CHANGE, SOLVABILITY_CHANGE** · evidence: "Ana has 3 times as many marbles as Tom"
- Why: Who has 3 times as many flipped.

**E12. 'each' lost (quantifier)** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: - Maya has 12 apples. / - She gives 3 apples to her 2 friends. / - Then she buys 5 more apples. / Question: How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NEW** · leakage_level **0** · leakage_type **NONE** · presentation **3** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **QUANTIFIER_CHANGE, AMBIGUITY_NEW, SOLVABILITY_CHANGE** · evidence: "She gives 3 apples to her 2 friends."
- Why: Without 'each' it reads as 3 apples in total. A changed quantifier: FAIL.

**E13. Time order changed** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. First she buys 5 more apples. Then she gives 3 apples to each of her 2 friends. How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **ORDER_CHANGE** · evidence: "First she buys 5 more apples. Then she gives"
- Why: The answer happens to stay 11, but the story order is part of the task: math FAIL, solvability NO.

**E14. "If" condition stated as an event (v1.2)** (requested: plain; model said: REWRITTEN)

> ORIGINAL: A baker made 40 muffins. If he sold 3/4 of them in the morning, how many muffins does he have left?
>
> ADAPTATION: A baker made 40 muffins. He sold 3/4 of them in the morning. How many muffins does he have left?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **NO** · failure_codes **COND_OMIT, SOLVABILITY_CHANGE** · evidence: "He sold 3/4 of them in the morning."
- Why: The question is asked UNDER the 'If'. Turning it into a fact drops the condition. Keep it: 'Question: If he sold 3/4 of them in the morning, how many are left?'

**E15. Condition added** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends, but only if they help her. Then she buys 5 more apples. How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **COND_ADD, SOLVABILITY_CHANGE** · evidence: "but only if they help her"
- Why: A new condition makes the answer depend on something unknown.

**E16. Contradiction** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Maya started with 10 apples. Then she buys 5 more. How many apples does Maya have now?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **CONTRADICTION, QTY_ADD, SOLVABILITY_CHANGE** · evidence: "Maya started with 10 apples."
- Why: The text now disagrees with itself.

### Target (the question)

**E17. Asks for something else** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples did Maya give away?

- Labels: math_fidelity **PASS** · target_preserved **FAIL** · solvability_changed **YES** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **TARGET_CHANGE, SOLVABILITY_CHANGE** · evidence: "How many apples did Maya give away?"
- Why: Different unknown: target FAIL. Math can stay PASS when every given survives.

**E18. Reworded, same target (fine)** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have at the end?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES**
- Why: Same unknown, same unit, same person: PASS.

### Ambiguity

**E19. Dangling "If" fragment (v1.2)** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: A baker made 40 muffins. If he sold 3/4 of them in the morning, how many muffins does he have left?
>
> ADAPTATION: - A baker made 40 muffins. / - If he sold 3/4 of them in the morning. / Question: How many muffins does he have left?

- Labels: math_fidelity **UNSURE** · target_preserved **PASS** · solvability_changed **UNSURE** · ambiguity **NEW** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **NO** · failure_codes **AMBIGUITY_NEW, HARMFUL_FRAGMENT, COND_OMIT** · evidence: "- If he sold 3/4 of them in the morning."
- Why: A bullet that is neither a fact nor the question; a student can drop it or read it as a guess. Not SAFE. Presentation ≤ 1.

**E20. A line loses its base (v1.2)** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Ravi earns $200 a week. From his weekly pay, 10% goes to savings and $15 goes to bus fare. How much money does he have left each week?
>
> ADAPTATION: - Ravi earns $200 a week. / - 10% goes to savings. / - $15 goes to bus fare. / Question: How much money does he have left each week?

- Labels: math_fidelity **UNSURE** · target_preserved **PASS** · solvability_changed **UNSURE** · ambiguity **NEW** · leakage_level **0** · leakage_type **NONE** · presentation **3** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **AMBIGUITY_NEW** · evidence: "- 10% goes to savings."
- Why: '10% of what?' The base ('of his weekly pay') was lost. A flat $15 needs no base. Correct line: '- 10% of his weekly pay goes to savings.'

**E21. Resolves an ambiguous original correctly** (requested: plain; model said: REWRITTEN)

> ORIGINAL: A tower has 10 floors. The first 4 floors are each 10 feet tall. The other floors are each 2 feet taller. How tall is the tower?
>
> ADAPTATION: A tower has 10 floors. The first 4 floors are each 10 feet tall. Each of the other floors is 2 feet taller than each of the first 4 floors. How tall is the tower?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **RESOLVED** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **DISAMBIGUATION** · evidence: "2 feet taller than each of the first 4 floors"
- Why: The original never said 'taller than what'. Picking the intended reading = RESOLVED (still SAFE). Say which reading in notes.

**E22. Resolves it the wrong way** (requested: plain; model said: REWRITTEN)

> ORIGINAL: A tower has 10 floors. The first 4 floors are each 10 feet tall. The other floors are each 2 feet taller. How tall is the tower?
>
> ADAPTATION: A tower has 10 floors. The first 4 floors are each 10 feet tall. Each other floor is 2 feet taller than the floor below it. How tall is the tower?

- Labels: math_fidelity **FAIL** · target_preserved **PASS** · solvability_changed **YES** · ambiguity **RESOLVED** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **FALSE_DISAMBIGUATION, SOLVABILITY_CHANGE** · evidence: "2 feet taller than the floor below it"
- Why: Picked a reading that is not the intended one: the answer changes.

### Leakage level 1

**E23. STRUCTURE: step labels in solution order** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Step 1: Maya has 12 apples. / Step 2: She gives 3 apples to each of her 2 friends. / Step 3: She buys 5 more apples. / Question: How many apples does Maya have now?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **1** · leakage_type **STRUCTURE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **LEAK_STRUCTURE** · evidence: "Step 1: ... Step 2: ... Step 3:"
- Why: Labels hint at a solution order. Level 1. Any leak caps presentation at 2.

### Leakage level 2

**E24. OPERATION: names the operation** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends, so multiply 3 by 2. Then she buys 5 more apples. How many apples does Maya have now?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **2** · leakage_type **OPERATION** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **LEAK_OPERATION** · evidence: "so multiply 3 by 2"
- Why: Tells the student which operation to use.

**E25. STEPS: a plan or tips** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now? / Tip: First find how many apples she gave away. Then subtract. Then add the ones she bought.

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **2** · leakage_type **STEPS** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **LEAK_STEPS** · evidence: "First find how many apples she gave away. Then subtract."
- Why: A plan to follow: level 2 STEPS.

**E26. RELEVANCE: says which facts matter** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Here is what you need to know: / - Maya has 12 apples. / - She gives 3 apples to EACH of her 2 friends. / - Then she buys 5 more apples. / Question: How many apples does Maya have now?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **2** · leakage_type **RELEVANCE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **LEAK_RELEVANCE** · evidence: "Here is what you need to know:"
- Why: Relevance cues ('what you need to know', 'this fact is extra', bolding only some numbers) = level 2 RELEVANCE. A heading that only groups facts is level 0.

### Leakage level 3

**E27. INTERMEDIATE: a value the student had to work out** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 6 apples away to her 2 friends, 3 each. Then she buys 5 more apples. How many apples does Maya have now?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **3** · leakage_type **INTERMEDIATE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **LEAK_INTERMEDIATE** · evidence: "She gives 6 apples away"
- Why: 6 = 3 x 2 was the student's job. Ranges ('floors 5 to 10') and set-up expressions ('3 apples times 2 friends') also count as level 3.

**E28. ANSWER: states the answer** (requested: naive; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now? / (Maya ends up with 11 apples.)

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **3** · leakage_type **ANSWER** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **LEAK_ANSWER** · evidence: "Maya ends up with 11 apples."
- Why: The most severe leak. Pick the MOST severe level when there are several.

### Presentation

**E29. Harder to read (0)** (requested: plain; model said: REWRITTEN)

> ORIGINAL: Sam has 5 pencils. He buys 4 more. How many pencils does Sam have?
>
> ADAPTATION: Pertaining to writing implements, Sam possesses five, and subsequently procures an additional four; ascertain his aggregate holdings.

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **0** · abstention_appropriate **NA** · adaptation_needed **NO** · failure_codes **OVER_EDIT**
- Why: Faithful math, but harder words: presentation 0, OVER_EDIT.

**E30. Broken fragments (1)** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?
>
> ADAPTATION: - 12 apples. / - 3 apples. / - each friend, 2 friends. / - 5 more. / Question: How many apples does Maya have now?

- Labels: math_fidelity **UNSURE** · target_preserved **PASS** · solvability_changed **UNSURE** · ambiguity **NEW** · leakage_level **0** · leakage_type **NONE** · presentation **1** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **HARMFUL_FRAGMENT, AMBIGUITY_NEW** · evidence: "- 3 apples. - each friend, 2 friends."
- Why: Fragments lose who did what. Presentation 1.

**E31. Confusing regrouping** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Tom has 3 times as many marbles as Ana. Ana has 8 marbles. How many marbles do they have together?
>
> ADAPTATION: Marbles: / - Tom: 3 times as many / - Ana: 8 / Question: How many marbles do they have together?

- Labels: math_fidelity **UNSURE** · target_preserved **PASS** · solvability_changed **UNSURE** · ambiguity **NEW** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **ENTITY_GROUPING, AMBIGUITY_NEW** · evidence: "Tom: 3 times as many"
- Why: '3 times as many' as whom? Regrouping hid the relation.

**E32. Asked for chunked, got a paragraph** (requested: chunked; model said: REWRITTEN)

> ORIGINAL: Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee, so how much money does she keep?
>
> ADAPTATION: Lena earns $15 an hour. She works 6 hours a day for 5 days. From her total pay, 10% goes to taxes and $20 goes to a club fee. How much does she keep?

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **YES** · failure_codes **FORMAT_FAIL**
- Why: Math fine (SAFE), but the requested chunked format was not followed.

**E33. Teacher preamble / extra text** (requested: naive; model said: REWRITTEN)

> ORIGINAL: Sam has 5 pencils. He buys 4 more. How many pencils does Sam have?
>
> ADAPTATION: Here's a simpler version for your student! / Sam has 5 pencils. He buys 4 more. How many pencils does Sam have? / Teacher tip: read it aloud.

- Labels: math_fidelity **PASS** · target_preserved **PASS** · solvability_changed **NO** · ambiguity **NONE** · leakage_level **0** · leakage_type **NONE** · presentation **2** · abstention_appropriate **NA** · adaptation_needed **NO** · failure_codes **EXTRA_TEXT**
- Why: Label everything the model returned. Teacher-only text = EXTRA_TEXT. It gives nothing away here, so still SAFE.

## When you're done

Save the .xlsx and send it back. Don't open `KEY_DO_NOT_OPEN.csv`, and don't compare notes with the other annotator before the joint adjudication.
