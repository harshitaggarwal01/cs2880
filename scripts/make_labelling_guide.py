"""Labelling quick guide (rubric v1.2): one source of examples -> docs/LABELLING_QUICK_GUIDE.md and guide tabs in xlsx.

  python scripts/make_labelling_guide.py                                   # writes the markdown guide
  python scripts/make_labelling_guide.py data/annotations/ollama-v1/sheet_A.xlsx data/annotations/ollama-v1/sheet_B.xlsx

Every example uses an INVENTED problem (not a calibration or study item), so it reveals no adjudication and no study
output. The Label tab is untouched; the guide tabs ("START HERE", "Examples", "Field guide", "Code examples") are
added or replaced; import (sheets_xlsx.import_xlsx) reads only the Label tab.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------------------------- invented problems
MAYA = "Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have now?"
SAM = "Sam has 5 pencils. He buys 4 more. How many pencils does Sam have?"
LENA = ("Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 "
        "goes to a club fee, so how much money does she keep?")
BAKER = "A baker made 40 muffins. If he sold 3/4 of them in the morning, how many muffins does he have left?"
TOWER = ("A tower has 10 floors. The first 4 floors are each 10 feet tall. The other floors are each 2 feet taller. "
         "How tall is the tower?")
TOM = "Tom has 3 times as many marbles as Ana. Ana has 8 marbles. How many marbles do they have together?"
RAVI = ("Ravi earns $200 a week. From his weekly pay, 10% goes to savings and $15 goes to bus fare. "
        "How much money does he have left each week?")
ROPE = "A rope is 6 meters long. Jo cuts it into 3 equal pieces. How long is each piece?"

COLS = ["math_fidelity", "target_preserved", "solvability_changed", "ambiguity", "leakage_level", "leakage_type",
        "presentation", "abstention_appropriate", "adaptation_needed", "failure_codes", "evidence"]


def lab(pres="3", math="PASS", target="PASS", solv="NO", amb="NONE", lvl="0", ltype="NONE", abst="NA",
        need="YES", codes="", ev="") -> dict:
    return dict(zip(COLS, [math, target, solv, amb, lvl, ltype, pres, abst, need, codes, ev]))


# (id, group, scenario, requested, model said, original, adaptation, labels, why)
EX = [
    # ---- clean
    ("E1", "Clean", "Perfect chunked rewrite (use QUICK = ALL CLEAR)", "chunked", "REWRITTEN", MAYA,
     "- Maya has 12 apples.\n- She gives 3 apples to each of her 2 friends.\n- Then she buys 5 more apples.\nQuestion: How many apples does Maya have now?",
     lab("3"), "Every number, owner, 'each', 'then' and the question survive. One fact per line, question set apart, nothing added. SAFE."),
    ("E2", "Clean", "Good plain-language rewrite", "plain", "REWRITTEN", LENA,
     "Lena earns $15 an hour. She works 6 hours a day for 5 days. From her total pay, 10% goes to taxes. A club fee of $20 also comes out of her total pay. How much money does she keep?",
     lab("2"), "Same facts, shorter sentences, clearer prose, but not one-fact-per-line with the question set apart: presentation 2. SAFE."),
    ("E3", "Clean", "Faithful but barely changed (near-copy)", "plain", "REWRITTEN", LENA,
     "Lena earns $15 an hour and works 6 hours a day for 5 days, and from her total pay 10% goes to taxes and $20 goes to a club fee. How much money does she keep?",
     lab("1", codes="NO_ADAPT"), "Still SAFE (nothing wrong with the math), but the densest sentence is unchanged: presentation 1, code NO_ADAPT."),
    # ---- abstention
    ("E4", "Model said no rewrite needed", "Abstention is right (short and clear)", "plain", "NO_REWRITE_NEEDED", SAM, SAM,
     lab("", abst="YES", need="NO"), "Leave presentation BLANK. abstention_appropriate YES: two short sentences, one relation."),
    ("E5", "Model said no rewrite needed", "Abstention is wrong (dense original)", "plain", "NO_REWRITE_NEEDED", LENA, LENA,
     lab("", abst="NO", need="YES", codes="NO_ADAPT"), "Presentation BLANK. abstention_appropriate NO: one 40-word sentence with five quantities needed a rewrite."),
    # ---- math fidelity
    ("E6", "Math fidelity", "A number changed", "chunked", "REWRITTEN", MAYA,
     "- Maya has 12 apples.\n- She gives 4 apples to each of her 2 friends.\n- Then she buys 5 more apples.\nQuestion: How many apples does Maya have now?",
     lab("3", math="FAIL", solv="YES", codes="QTY_CHANGE, SOLVABILITY_CHANGE", ev="She gives 4 apples to each"), "3 became 4, so the answer changes (11 -> 9). Presentation is still judged on layout: 3."),
    ("E7", "Math fidelity", "A number dropped", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends. How many apples does Maya have now?",
     lab("1", math="FAIL", solv="YES", codes="QTY_OMIT, SOLVABILITY_CHANGE", ev="(missing: Then she buys 5 more apples.)"), "The +5 fact is gone. For an omission, write what is missing in evidence."),
    ("E8", "Math fidelity", "A number added", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends. She eats 1 apple. Then she buys 5 more apples. How many apples does Maya have now?",
     lab("1", math="FAIL", solv="YES", codes="QTY_ADD, SOLVABILITY_CHANGE", ev="She eats 1 apple."), "A new quantity changes the answer."),
    ("E9", "Math fidelity", "Unit changed", "plain", "REWRITTEN", ROPE,
     "A rope is 6 feet long. Jo cuts it into 3 equal pieces. How long is each piece?",
     lab("1", math="FAIL", solv="YES", need="NO", codes="UNIT_CHANGE, SOLVABILITY_CHANGE", ev="6 feet"), "Meters became feet: the answer is now 2 feet, not 2 meters."),
    ("E10", "Math fidelity", "Relation changed", "plain", "REWRITTEN", TOM,
     "Tom has 3 more marbles than Ana. Ana has 8 marbles. How many marbles do they have together?",
     lab("2", math="FAIL", solv="YES", codes="REL_CHANGE, SOLVABILITY_CHANGE", ev="3 more marbles than Ana"), "'3 times as many' is not '3 more'. Answer 32 -> 19."),
    ("E11", "Math fidelity", "Quantity moved to someone else", "plain", "REWRITTEN", TOM,
     "Ana has 3 times as many marbles as Tom. Ana has 8 marbles. How many marbles do they have together?",
     lab("2", math="FAIL", solv="YES", codes="ENTITY_CHANGE, SOLVABILITY_CHANGE", ev="Ana has 3 times as many marbles as Tom"), "Who has 3 times as many flipped."),
    ("E12", "Math fidelity", "'each' lost (quantifier)", "chunked", "REWRITTEN", MAYA,
     "- Maya has 12 apples.\n- She gives 3 apples to her 2 friends.\n- Then she buys 5 more apples.\nQuestion: How many apples does Maya have now?",
     lab("3", math="FAIL", solv="YES", amb="NEW", codes="QUANTIFIER_CHANGE, AMBIGUITY_NEW, SOLVABILITY_CHANGE", ev="She gives 3 apples to her 2 friends."), "Without 'each' it reads as 3 apples in total. A changed quantifier: FAIL."),
    ("E13", "Math fidelity", "Time order changed", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. First she buys 5 more apples. Then she gives 3 apples to each of her 2 friends. How many apples does Maya have now?",
     lab("2", math="FAIL", solv="NO", codes="ORDER_CHANGE", ev="First she buys 5 more apples. Then she gives"), "The answer happens to stay 11, but the story order is part of the task: math FAIL, solvability NO."),
    ("E14", "Math fidelity", "\"If\" condition stated as an event (v1.2)", "plain", "REWRITTEN", BAKER,
     "A baker made 40 muffins. He sold 3/4 of them in the morning. How many muffins does he have left?",
     lab("2", math="FAIL", solv="YES", need="NO", codes="COND_OMIT, SOLVABILITY_CHANGE", ev="He sold 3/4 of them in the morning."), "The question is asked UNDER the 'If'. Turning it into a fact drops the condition. Keep it: 'Question: If he sold 3/4 of them in the morning, how many are left?'"),
    ("E15", "Math fidelity", "Condition added", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends, but only if they help her. Then she buys 5 more apples. How many apples does Maya have now?",
     lab("2", math="FAIL", solv="YES", codes="COND_ADD, SOLVABILITY_CHANGE", ev="but only if they help her"), "A new condition makes the answer depend on something unknown."),
    ("E16", "Math fidelity", "Contradiction", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends. Maya started with 10 apples. Then she buys 5 more. How many apples does Maya have now?",
     lab("1", math="FAIL", solv="YES", codes="CONTRADICTION, QTY_ADD, SOLVABILITY_CHANGE", ev="Maya started with 10 apples."), "The text now disagrees with itself."),
    # ---- target
    ("E17", "Target (the question)", "Asks for something else", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples did Maya give away?",
     lab("2", target="FAIL", solv="YES", codes="TARGET_CHANGE, SOLVABILITY_CHANGE", ev="How many apples did Maya give away?"), "Different unknown: target FAIL. Math can stay PASS when every given survives."),
    ("E18", "Target (the question)", "Reworded, same target (fine)", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends. Then she buys 5 more apples. How many apples does Maya have at the end?",
     lab("2"), "Same unknown, same unit, same person: PASS."),
    # ---- ambiguity
    ("E19", "Ambiguity", "Dangling \"If\" fragment (v1.2)", "chunked", "REWRITTEN", BAKER,
     "- A baker made 40 muffins.\n- If he sold 3/4 of them in the morning.\nQuestion: How many muffins does he have left?",
     lab("1", math="UNSURE", solv="UNSURE", amb="NEW", need="NO", codes="AMBIGUITY_NEW, HARMFUL_FRAGMENT, COND_OMIT", ev="- If he sold 3/4 of them in the morning."), "A bullet that is neither a fact nor the question; a student can drop it or read it as a guess. Not SAFE. Presentation ≤ 1."),
    ("E20", "Ambiguity", "A line loses its base (v1.2)", "chunked", "REWRITTEN", RAVI,
     "- Ravi earns $200 a week.\n- 10% goes to savings.\n- $15 goes to bus fare.\nQuestion: How much money does he have left each week?",
     lab("3", amb="NEW", math="UNSURE", solv="UNSURE", codes="AMBIGUITY_NEW", ev="- 10% goes to savings."), "'10% of what?' The base ('of his weekly pay') was lost. A flat $15 needs no base. Correct line: '- 10% of his weekly pay goes to savings.'"),
    ("E21", "Ambiguity", "Resolves an ambiguous original correctly", "plain", "REWRITTEN", TOWER,
     "A tower has 10 floors. The first 4 floors are each 10 feet tall. Each of the other floors is 2 feet taller than each of the first 4 floors. How tall is the tower?",
     lab("2", amb="RESOLVED", codes="DISAMBIGUATION", ev="2 feet taller than each of the first 4 floors"), "The original never said 'taller than what'. Picking the intended reading = RESOLVED (still SAFE). Say which reading in notes."),
    ("E22", "Ambiguity", "Resolves it the wrong way", "plain", "REWRITTEN", TOWER,
     "A tower has 10 floors. The first 4 floors are each 10 feet tall. Each other floor is 2 feet taller than the floor below it. How tall is the tower?",
     lab("2", math="FAIL", solv="YES", amb="RESOLVED", codes="FALSE_DISAMBIGUATION, SOLVABILITY_CHANGE", ev="2 feet taller than the floor below it"), "Picked a reading that is not the intended one: the answer changes."),
    # ---- leakage levels
    ("E23", "Leakage level 1", "STRUCTURE: step labels in solution order", "chunked", "REWRITTEN", MAYA,
     "Step 1: Maya has 12 apples.\nStep 2: She gives 3 apples to each of her 2 friends.\nStep 3: She buys 5 more apples.\nQuestion: How many apples does Maya have now?",
     lab("2", lvl="1", ltype="STRUCTURE", codes="LEAK_STRUCTURE", ev="Step 1: ... Step 2: ... Step 3:"), "Labels hint at a solution order. Level 1. Any leak caps presentation at 2."),
    ("E24", "Leakage level 2", "OPERATION: names the operation", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 3 apples to each of her 2 friends, so multiply 3 by 2. Then she buys 5 more apples. How many apples does Maya have now?",
     lab("2", lvl="2", ltype="OPERATION", codes="LEAK_OPERATION", ev="so multiply 3 by 2"), "Tells the student which operation to use."),
    ("E25", "Leakage level 2", "STEPS: a plan or tips", "plain", "REWRITTEN", MAYA,
     MAYA + "\nTip: First find how many apples she gave away. Then subtract. Then add the ones she bought.",
     lab("2", lvl="2", ltype="STEPS", codes="LEAK_STEPS", ev="First find how many apples she gave away. Then subtract."), "A plan to follow: level 2 STEPS."),
    ("E26", "Leakage level 2", "RELEVANCE: says which facts matter", "chunked", "REWRITTEN", MAYA,
     "Here is what you need to know:\n- Maya has 12 apples.\n- She gives 3 apples to EACH of her 2 friends.\n- Then she buys 5 more apples.\nQuestion: How many apples does Maya have now?",
     lab("2", lvl="2", ltype="RELEVANCE", codes="LEAK_RELEVANCE", ev="Here is what you need to know:"), "Relevance cues ('what you need to know', 'this fact is extra', bolding only some numbers) = level 2 RELEVANCE. A heading that only groups facts is level 0."),
    ("E27", "Leakage level 3", "INTERMEDIATE: a value the student had to work out", "plain", "REWRITTEN", MAYA,
     "Maya has 12 apples. She gives 6 apples away to her 2 friends, 3 each. Then she buys 5 more apples. How many apples does Maya have now?",
     lab("2", lvl="3", ltype="INTERMEDIATE", codes="LEAK_INTERMEDIATE", ev="She gives 6 apples away"), "6 = 3 x 2 was the student's job. Ranges ('floors 5 to 10') and set-up expressions ('3 apples times 2 friends') also count as level 3."),
    ("E28", "Leakage level 3", "ANSWER: states the answer", "naive", "REWRITTEN", MAYA,
     MAYA + "\n(Maya ends up with 11 apples.)",
     lab("2", lvl="3", ltype="ANSWER", codes="LEAK_ANSWER", ev="Maya ends up with 11 apples."), "The most severe leak. Pick the MOST severe level when there are several."),
    # ---- presentation and layout codes
    ("E29", "Presentation", "Harder to read (0)", "plain", "REWRITTEN", SAM,
     "Pertaining to writing implements, Sam possesses five, and subsequently procures an additional four; ascertain his aggregate holdings.",
     lab("0", need="NO", codes="OVER_EDIT", ev=""), "Faithful math, but harder words: presentation 0, OVER_EDIT."),
    ("E30", "Presentation", "Broken fragments (1)", "chunked", "REWRITTEN", MAYA,
     "- 12 apples.\n- 3 apples.\n- each friend, 2 friends.\n- 5 more.\nQuestion: How many apples does Maya have now?",
     lab("1", math="UNSURE", solv="UNSURE", amb="NEW", codes="HARMFUL_FRAGMENT, AMBIGUITY_NEW", ev="- 3 apples. - each friend, 2 friends."), "Fragments lose who did what. Presentation 1."),
    ("E31", "Presentation", "Confusing regrouping", "chunked", "REWRITTEN", TOM,
     "Marbles:\n- Tom: 3 times as many\n- Ana: 8\nQuestion: How many marbles do they have together?",
     lab("2", amb="NEW", math="UNSURE", solv="UNSURE", codes="ENTITY_GROUPING, AMBIGUITY_NEW", ev="Tom: 3 times as many"), "'3 times as many' as whom? Regrouping hid the relation."),
    ("E32", "Presentation", "Asked for chunked, got a paragraph", "chunked", "REWRITTEN", LENA,
     "Lena earns $15 an hour. She works 6 hours a day for 5 days. From her total pay, 10% goes to taxes and $20 goes to a club fee. How much does she keep?",
     lab("2", codes="FORMAT_FAIL"), "Math fine (SAFE), but the requested chunked format was not followed."),
    ("E33", "Presentation", "Teacher preamble / extra text", "naive", "REWRITTEN", SAM,
     "Here's a simpler version for your student!\nSam has 5 pencils. He buys 4 more. How many pencils does Sam have?\nTeacher tip: read it aloud.",
     lab("2", need="NO", codes="EXTRA_TEXT"), "Label everything the model returned. Teacher-only text = EXTRA_TEXT. It gives nothing away here, so still SAFE."),
]

FIELDS = [
    ("math_fidelity", [("PASS", "every number, unit, owner, relation, condition, 'each/all/remaining', and time order kept", "E1, E2"),
                       ("FAIL", "anything changed, missing, added or reordered (including an 'If' stated as an event)", "E6–E16"),
                       ("UNSURE", "the text now allows two readings and you can't tell if the math survived", "E19, E20")]),
    ("target_preserved", [("PASS", "same unknown, same unit, same person (rewording is fine)", "E18"),
                          ("FAIL", "asks for something else", "E17"), ("UNSURE", "the question became unclear", "")]),
    ("solvability_changed", [("NO", "still solvable with the same answer", "E1, E13"),
                             ("YES", "unsolvable or a different answer", "E6, E14"), ("UNSURE", "goes with an UNSURE math call", "E19")]),
    ("ambiguity", [("NONE", "one reading, as in the original", "E1"), ("NEW", "a second reading appeared", "E12, E19, E20"),
                   ("RESOLVED", "the original was ambiguous and the rewrite picked one reading (say which in notes)", "E21, E22")]),
    ("leakage_level", [("0", "nothing the student had to work out is given", "E1"), ("1", "STRUCTURE: step labels / solution-order layout", "E23"),
                       ("2", "STEPS, OPERATION or RELEVANCE", "E24–E26"), ("3", "INTERMEDIATE or ANSWER", "E27, E28")]),
    ("leakage_type", [("NONE", "level 0", "E1"), ("STRUCTURE", "Step 1 / Step 2 labels", "E23"), ("STEPS", "a plan, tips, 'steps to try'", "E25"),
                      ("OPERATION", "'multiply', 'subtract', an equation", "E24"), ("RELEVANCE", "'what you need to know', 'this fact is extra'", "E26"),
                      ("INTERMEDIATE", "a derived value, range or set-up expression", "E27"), ("ANSWER", "the answer itself", "E28")]),
    ("presentation (REWRITTEN only)", [("0", "harder to read", "E29"), ("1", "near-copy, fragments, or the original buried under added text", "E3, E30"),
                                        ("2", "clearer prose, OR any layout with added steps/hints/notes, OR any leak (cap 2)", "E2, E23–E28"),
                                        ("3", "one fact per line or grouped, question set apart, nothing added", "E1")]),
    ("abstention_appropriate", [("YES", "model said NO_REWRITE_NEEDED and the original was already short and clear", "E4"),
                                ("NO", "model said NO_REWRITE_NEEDED but the original needed help", "E5"), ("NA", "every REWRITTEN row", "E1")]),
    ("adaptation_needed (judge the ORIGINAL)", [("YES", "a sentence over 20 words, or 3+ quantities/relations in one sentence, or an unclear relation ('3 feet taller' than what?)", "E1, E5"),
                                                 ("NO", "short, clear sentences", "E4, E9"), ("UNCLEAR", "only with a note", "")]),
    ("confidence", [("HIGH", "clear case", ""), ("MEDIUM", "a judgement call", ""), ("LOW", "you used UNSURE; explain in notes", "")]),
]


def md() -> str:
    out = ["# Labelling quick guide (rubric v1.2)", "",
           "**What you are judging:** is the ADAPTATION the *same task* as the ORIGINAL, made easier to *read* but not easier to *solve*?", "",
           "## How to do one row (about 1.5 minutes)", "",
           "1. Read the **ORIGINAL**, then the **ADAPTATION**. Label *everything* in the adaptation, including preambles and tips.",
           "2. **Nothing wrong?** Set **QUICK = ALL CLEAR**. That fills math PASS, target PASS, solvability NO, ambiguity NONE and leakage 0 / NONE. Then set **presentation** and **adaptation_needed**. Done.",
           "3. **Something wrong?** Leave QUICK blank and fill the columns left to right:",
           "   - **Math:** check every number, unit, owner, relation, \"each / all / remaining\", condition (\"If…\"), the time order, and the question.",
           "   - **Leakage:** does it give away anything the student had to work out? Pick the **most severe** level and its type.",
           "   - **Presentation 0–3:** leave it blank if \"model said\" is NO_REWRITE_NEEDED, and fill **abstention_appropriate** instead.",
           "   - **Rows where \"model said\" is NO_REWRITE_NEEDED** (the original came back unchanged): the math and leakage columns count as clean automatically. Fill only **abstention_appropriate** and **adaptation_needed** (E4, E5).",
           "   - **failure_codes:** comma-separated (see the table below).",
           "   - **evidence:** paste the exact offending words. It is required for any FAIL, solvability YES, ambiguity NEW, or leakage > 0.",
           "   - **confidence:** use LOW together with UNSURE, and say why in **notes**.",
           "4. The **done** column turns green when the row is complete. Save often. You can stop and resume any time.",
           "",
           "**SAFE is computed for you:** math PASS + target PASS + solvability NO + ambiguity not NEW + leakage 0.",
           "",
           "### The five rulings people get wrong (v1.2)",
           "- **\"If…\" is a condition.** Keep it on the question. Stating it as an event, or leaving a dangling \"If…\" bullet, is not SAFE (E14, E19).",
           "- **Every percent keeps its base.** \"10% goes to savings\" with no \"of his pay\" is ambiguity NEW (E20).",
           "- **Level 3 is any value, range or set-up expression the student had to work out** (E27).",
           "- **Relevance cues are level 2** (\"Here is what you need to know\") (E26). Step labels are level 1 (E23). **Any leak caps presentation at 2.**",
           "- **Short is not the same as clear.** \"3 feet taller\" (than what?) makes adaptation_needed YES.",
           "", "## Every value, with an example", "", "| Field | Value | Use it when | Example |", "|---|---|---|---|"]
    for f, vals in FIELDS:
        for i, (v, when, ex) in enumerate(vals):
            out.append(f"| {f if i == 0 else ''} | **{v}** | {when} | {ex} |")
    out += ["", "## Every failure code, with an example", "", "| Code | Meaning | Example |", "|---|---|---|"]
    sys.path.insert(0, str(ROOT / "src"))
    from sheets_xlsx import FAILURE_CODES
    used = {}
    for e in EX:
        for c in [x.strip() for x in e[7]["failure_codes"].split(",") if x.strip()]:
            used.setdefault(c, e[0])
    for c, desc in FAILURE_CODES.items():
        out.append(f"| `{c}` | {desc} | {used.get(c, '—')} |")
    out += ["", "## Worked examples (invented problems)", ""]
    group = None
    for (eid, grp, scen, req, said, orig, adapt, L, why) in EX:
        if grp != group:
            out += [f"### {grp}", ""]
            group = grp
        lab_s = " · ".join(f"{k} **{v}**" for k, v in L.items() if v != "" and k != "evidence")
        out += [f"**{eid}. {scen}** (requested: {req}; model said: {said})", "",
                f"> ORIGINAL: {orig}", ">", "> ADAPTATION: " + adapt.replace("\n", " / "), "",
                f"- Labels: {lab_s}" + (f" · evidence: \"{L['evidence']}\"" if L["evidence"] else ""), f"- Why: {why}", ""]
    out += ["## When you're done", "", "Save the .xlsx and send it back. Don't open `KEY_DO_NOT_OPEN.csv`, and don't compare notes with the other annotator before the joint adjudication.", ""]
    return "\n".join(out)


def add_tabs(xlsx: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = load_workbook(xlsx)
    for name in ("START HERE", "Examples", "Field guide", "Code examples"):
        if name in wb.sheetnames:
            del wb[name]
    head, fill, wrap = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1B2A3A"), Alignment(wrap_text=True, vertical="top")
    text = md()
    start = text.split("## Every value, with an example")[0]
    ws = wb.create_sheet("START HERE", 0)
    ws.column_dimensions["A"].width = 150
    for line in start.splitlines():
        ws.append([line.replace("**", "").replace("`", "")])
        c = ws.cell(ws.max_row, 1)
        c.alignment = wrap
        if line.startswith("#"):
            c.font = Font(bold=True, size=14 if line.startswith("# ") else 12)
    ws.append(["Then open the 'Label' tab. Examples, every value, and every code are in the next tabs."])
    ws.cell(ws.max_row, 1).font = Font(bold=True, color="B04E12")

    def table(name, hdr, rows, widths):
        t = wb.create_sheet(name, wb.sheetnames.index("START HERE") + 1 + ["Examples", "Field guide", "Code examples"].index(name))
        t.append(hdr)
        for c in t[1]:
            c.font, c.fill, c.alignment = head, fill, wrap
        for r in rows:
            t.append(r)
        for i, w in enumerate(widths, 1):
            t.column_dimensions[t.cell(1, i).column_letter].width = w
        for row in t.iter_rows(min_row=2):
            for c in row:
                c.alignment = wrap
        t.freeze_panes = "B2"

    table("Examples", ["id", "scenario", "requested", "model said", "ORIGINAL", "ADAPTATION"] + COLS + ["why"],
          [[e[0], f"{e[1]}: {e[2]}", e[3], e[4], e[5], e[6]] + [e[7][c] for c in COLS] + [e[8]] for e in EX],
          [6, 28, 10, 12, 40, 44] + [11] * 9 + [22, 28, 50])
    table("Field guide", ["field", "value", "use it when", "example rows"],
          [[f if i == 0 else "", v, w, ex] for f, vals in FIELDS for i, (v, w, ex) in enumerate(vals)], [28, 14, 80, 16])
    sys.path.insert(0, str(ROOT / "src"))
    from sheets_xlsx import FAILURE_CODES
    used = {}
    for e in EX:
        for c in [x.strip() for x in e[7]["failure_codes"].split(",") if x.strip()]:
            used.setdefault(c, e[0])
    table("Code examples", ["code", "meaning", "example row"], [[c, d, used.get(c, "")] for c, d in FAILURE_CODES.items()], [24, 70, 14])
    wb.active = wb.sheetnames.index("START HERE")
    wb.save(xlsx)
    print(f"updated {xlsx}: tabs {wb.sheetnames}")


def check() -> list[str]:
    """Every example must satisfy the sheet validator (rubric rules) and every code must be a known code."""
    sys.path.insert(0, str(ROOT / "src"))
    from sheets_xlsx import FAILURE_CODES, validate
    probs = []
    for e in EX:
        row = {"annotation_id": e[0], "transformation_requested": e[3], "model_status": e[4], "original": e[5],
               "adaptation": e[6], **e[7], "confidence": "HIGH", "notes": ""}
        _, p, _ = validate(row)
        probs += [f"{e[0]}: {x}" for x in p]
        probs += [f"{e[0]}: unknown code {c}" for c in [x.strip() for x in e[7]["failure_codes"].split(",") if x.strip()] if c not in FAILURE_CODES]
    return probs


if __name__ == "__main__":
    bad = check()
    if bad:
        raise SystemExit("examples break the rubric validator:\n  " + "\n  ".join(bad))
    (ROOT / "docs" / "LABELLING_QUICK_GUIDE.md").write_text(md(), encoding="utf-8")
    print("wrote docs/LABELLING_QUICK_GUIDE.md")
    for p in sys.argv[1:]:
        add_tabs(Path(p))
