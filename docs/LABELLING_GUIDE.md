# Labelling guide (quick start)

**Read this once, about 10 minutes. Keep `docs/annotation_guide.md` open for edge cases.**

## What you are deciding
For each row: **is the ADAPTATION still exactly the same math task as the ORIGINAL, done by the student alone?**
- Easier to *read* is fine: shorter sentences, simpler words, one fact per line.
- Easier to *solve* is not: changed numbers, hints, steps, intermediate values.

## Setup (2 minutes)
1. Open your file: `sheet_A.xlsx` (annotator A) or `sheet_B.xlsx` (annotator B). It opens in Excel, Google Sheets (File → Import → Upload) or LibreOffice.
   - Calibration round: `data/calibration/pilot/`.
   - Main study: `data/annotations/<run_id>/`.
2. There are three tabs:
   - **Instructions**: this page, short.
   - **Label**: where you work.
   - **Codes**: failure codes with meanings.
3. On the **Label** tab, the left columns are frozen and show the problem. The yellow columns are yours.
4. Rules:
   - Label blind: don't look up which model wrote a row, and never open `KEY_DO_NOT_OPEN.csv`.
   - Don't discuss rows with the other annotator until you've both finished.
   - Take a short break every 40 rows.

## The fast path (most rows)
Nothing wrong with the adaptation?
1. Set **QUICK** = `ALL CLEAR`. This means math PASS, question PASS, solvability NO, ambiguity NONE, leakage 0.
2. Set **presentation**:
   - 0 = harder to read
   - 1 = near-copy or broken fragments
   - 2 = clearly easier
   - 3 = much easier
3. The **done** column turns green. Next row.

If **model said** is `NO_REWRITE_NEEDED`, leave presentation blank. Set **abstention_appropriate** to YES if the original was already short and clear, NO if it really needed simplifying.

## When something is wrong (three passes)
| Pass | Check | If wrong |
|---|---|---|
| **1 · Math** | Every number, unit, who owns what, every relation and its direction ("3 times as many" ≠ "3 more"), each / all / remaining / at least, conditions, time order | **math_fidelity = FAIL** |
| | Same question, same unit | otherwise **target_preserved = FAIL** |
| | Still solvable, same answer | otherwise **solvability_changed = YES** |
| | Only one reading | a new second reading → **ambiguity = NEW**; picked one reading of an already-ambiguous original → **RESOLVED** (say which in notes) |
| **2 · Leakage** | Gives away anything the student had to work out? | **leakage_level** and **leakage_type**, below |
| **3 · Presentation** | Easier to read? | **presentation 0–3** |

**Leakage levels** (pick the most severe):
- **0** nothing given away.
- **1 STRUCTURE**: layout or labels in solution order ("Step 1: purple beads / Step 2: blue beads").
- **2 STEPS / OPERATION / RELEVANCE**: names an operation, gives a plan or equation, or says which facts matter or don't.
- **3 INTERMEDIATE / ANSWER**: states an in-between value or the answer, even as a range or heading ("Stories 11 to 20" gives away "10 floors").

**Whenever you mark FAIL, YES, NEW or leakage > 0:**
- paste the exact words into **evidence**;
- add **failure_codes**, comma-separated, from the Codes tab (e.g. `QTY_CHANGE, LEAK_STEPS`).

**Not sure?** Use UNSURE, say why in **notes**, and set **confidence = LOW**. Don't guess.

**Realistic-prompt rows:** label *everything* in the adaptation, including "Here's a simpler version" and tips; a teacher may paste the whole reply. Text meant only for the teacher gets the code `EXTRA_TEXT`.

## Worked examples (from our Nov 2 run, not in your calibration set)
Original (Vikki): *"Vikki worked 42 hours in one week. Her hourly pay rate is $10. From her weekly earnings, 20% is deducted as tax, 5% is deducted as insurance cover, and $5 is deducted for union dues. How much money, in dollars, does Vikki take home after deductions?"*

| Adaptation | Labels | Why |
|---|---|---|
| "– From her weekly earnings, 20% is deducted as tax. – **From her weekly earnings,** 5% is deducted as insurance cover. – **From her weekly earnings,** $5 is deducted for union dues. …" | QUICK = ALL CLEAR; presentation 3 | Same facts, one per line. Repeating "from her weekly earnings" keeps the meaning |
| "– From her weekly earnings, 20% is deducted as tax. – 5% is deducted as insurance cover. – $5 is deducted for union dues. …" | ambiguity **NEW**; math_fidelity UNSURE; evidence "5% is deducted as insurance cover"; code AMBIGUITY_NEW; presentation 2 | The 5% no longer says *of what*. A student could take 5% of what's left after tax and get a different answer |
| "Money is taken out of her weekly earnings in three ways: 20% … 5% … and $5 …" | QUICK = ALL CLEAR; presentation 2 | "three" just counts the deductions; it isn't a value from the problem |

Original (building): *"James builds a 20 story building. The first 10 stories are each 12 feet tall each. The remaining floors are each 3 feet taller. How tall is the building?"*

| Adaptation | Labels | Why |
|---|---|---|
| "… Each of the remaining stories is 3 feet taller **than each of the first 10 stories**. …" | ambiguity **RESOLVED** (notes: "matches the intended reading"); everything else clear; presentation 2 | It picked one reading of "3 feet taller". Not unsafe on its own, but recorded |
| *(made up)* "Stories 1 to 10: 12 feet each. **Stories 11 to 20**: 3 feet taller." | leakage **3 INTERMEDIATE**; evidence "Stories 11 to 20"; code LEAK_INTERMEDIATE | The student was meant to work out that 10 floors remain |
| *(made up)* "… **Steps to try:** first multiply 10 by 12, then …" | leakage **2 STEPS**; evidence "Steps to try: first multiply 10 by 12"; codes LEAK_STEPS, LEAK_OPERATION | Gives the plan and the operation |

Original (dresses): *"Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?"*, where the model said `NO_REWRITE_NEEDED` and returned it unchanged → **abstention_appropriate = YES**, presentation blank.

## When you finish
1. Save the file.
2. Run `make import-sheets ANN=data/calibration/pilot` (or the main-study folder). It checks every row and lists problems by row number, e.g. "row 14: a FAIL / YES / NEW / leakage label needs the exact words in evidence". Fix them in the xlsx and run it again until it's clean.
3. Calibration round, both annotators finished:
   ```bash
   python src/calibrate.py --agreement data/calibration/pilot/sheet_A.csv data/calibration/pilot/sheet_B.csv
   python src/calibrate.py --disagreements data/calibration/pilot/sheet_A.csv data/calibration/pilot/sheet_B.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv
   ```
   Talk through the disagreements together. If agreement is ≥ 0.7 on SAFE, freeze rubric v1 in `docs/annotation_guide.md`.
4. Main study, both finished: `make adjudicate ANN=data/annotations/<run_id>`. It imports both xlsx files, lists the rows you disagree on in `TO_ADJUDICATE.csv`, which you resolve together, then writes `adjudicated.csv`.

## Time
- Calibration: 70 rows each, about 2 hours.
- Main study (lean plan): about 550 rows each, about 14 hours. Spread it over 5–7 days, in sessions of no more than 2 hours.
