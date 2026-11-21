"""Build the Nov 23 video deck (15 slides) in the Nov 16 v3 visual style; narration -> speaker notes.

  python scripts/build_video_deck.py <v3_template.pptx> <out.pptx>
Needs python-pptx. Slide text is short on purpose; the narration lives in docs/video/VIDEO_DECK_nov23.md.
"""
import copy
import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
VID = ROOT / "docs" / "video"
CREAM, NAVY, RUST, BLUE = RGBColor(0xF6, 0xF3, 0xEC), RGBColor(0x1B, 0x2A, 0x3A), RGBColor(0xB0, 0x4E, 0x12), RGBColor(0x2F, 0x66, 0x90)
LIGHT, MUTE, PALE = RGBColor(0xF6, 0xF3, 0xEC), RGBColor(0xC9, 0xD6, 0xE2), RGBColor(0xEC, 0xE6, 0xDA)
PEACH = RGBColor(0xF0, 0xA4, 0x6E)
SERIF, SANS = "EB Garamond", "Nunito Sans"
L, W = Inches(0.89), Inches(11.55)


def narration() -> dict[int, str]:
    text = (VID / "VIDEO_DECK_nov23.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^## (\d+) · .*?(?=^---$|\Z)", text, re.M | re.S):
        paras = [ln[2:].replace("**Narration.** ", "") for ln in m.group(0).splitlines() if ln.startswith("> ")]
        out[int(m.group(1))] = "\n\n".join(paras)
    return out


def box(slide, x, y, w, h, fill=None, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, size=18, color=NAVY, font=SANS, bold=False, anchor=MSO_ANCHOR.TOP, space=6):
    """runs: str | list of paragraphs; a paragraph is str or list of (text, {bold, color, size, font})."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space)
        for t, st in ([(para, {})] if isinstance(para, str) else para):
            r = p.add_run()
            r.text = t
            f = r.font
            f.name, f.size, f.bold = st.get("font", font), Pt(st.get("size", size)), st.get("bold", bold)
            f.color.rgb = st.get("color", color)
    return tb


def header(slide, kicker, title, dark=False):
    text(slide, L, Inches(0.6), W, Inches(0.3), kicker.upper(), 13, PEACH if dark else RUST, bold=True)
    text(slide, L, Inches(0.95), W, Inches(0.9), title, 32, LIGHT if dark else NAVY, SERIF, bold=True)


def bullets(slide, items, y=1.95, h=4.9, size=19, x=None, w=None):
    paras = []
    for it in items:
        if isinstance(it, tuple):           # (bold lead, rest)
            paras.append([("•  ", {"color": RUST, "bold": True}), (it[0], {"bold": True}), (it[1], {})])
        else:
            paras.append([("•  ", {"color": RUST, "bold": True}), (it, {})])
    return text(slide, x or L, Inches(y), w or W, Inches(h), paras, size, space=10)


def new_slide(prs, bg=CREAM):
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s


def footer(slide, n, dark=False):
    text(slide, Inches(11.6), Inches(7.0), Inches(1.2), Inches(0.3), f"{n} / 15", 11, MUTE if dark else BLUE)


def stat(slide, x, y, w, big, small, color):
    text(slide, x, y, w, Inches(0.9), big, 54, color, SERIF, bold=True)
    text(slide, x, y + Inches(0.95), w, Inches(1.4), small, 15)


def build(template: Path, out: Path) -> None:
    prs = Presentation(str(template))
    sldIdLst = prs.slides._sldIdLst                       # drop the Nov 16 slides, keep the theme
    for sid in list(sldIdLst):
        prs.part.drop_rel(sid.rId)
        sldIdLst.remove(sid)
    notes = narration()
    S = []

    # 1 title
    s = new_slide(prs, NAVY)
    text(s, L, Inches(0.89), W, Inches(0.3), "CS 2880 · AI FOR SOCIAL IMPACT · BROWN UNIVERSITY · NOV 2026", 12, PEACH, bold=True)
    text(s, L, Inches(2.5), W, Inches(1.0), "SafeAdapt-Math", 60, LIGHT, SERIF, bold=True)
    text(s, L, Inches(3.6), W, Inches(0.6), "When “easier to read” becomes “easier to solve”", 30, LIGHT, SERIF)
    text(s, L, Inches(4.35), W, Inches(0.4), "Auditing AI accessibility rewrites of math word problems", 18, MUTE)
    text(s, L, Inches(6.3), W, Inches(0.4), "Harshit Aggarwal · Cathy Liu", 17, LIGHT, bold=True)
    S.append(s)

    # 2 motivation
    s = new_slide(prs)
    header(s, "Motivation", "Teachers use AI to adapt tests; nobody checks it")
    bullets(s, [("Accommodation ", "(legally owed under IEPs and 504 plans): the same task, made accessible."),
                ("Modification ", "(a different legal category): an easier task. It changes what the grade means."),
                "Teachers are encouraged to use AI for accommodations, with no tool that flags when a rewrite crosses the line.",
                ("The failure is invisible: ", "a rewrite that hands over the steps looks more helpful, not less."),
                "The harm lands on the students the accommodation was meant to protect."])
    S.append(s)

    # 3 problem statement
    s = new_slide(prs)
    header(s, "Problem statement", "Did the AI rewrite keep the same task?")
    q = box(s, L, Inches(1.95), W, Inches(1.35), PALE)
    text(s, L + Inches(0.3), Inches(2.05), W - Inches(0.6), Inches(1.2),
         "Given a math word problem and an AI rewrite of it, decide automatically, at low cost and with a stated "
         "error guarantee, whether the rewrite is the same task: an accommodation, not a modification.",
         21, NAVY, SERIF, anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, [("Same task (fidelity): ", "every quantity, relation, condition and the question survive, so the answer is unchanged."),
                ("Nothing given away (no leakage): ", "no added steps, operations, relevance hints or derived values."),
                ("We measure: ", "how often it goes wrong · how well checkers catch it · whether a $0 school gets the same protection.")],
            y=3.6, h=3.2)
    S.append(s)

    # 4 main finding
    s = new_slide(prs)
    header(s, "Main finding", "The prompt teachers type breaks the task")
    cw = Inches(3.65)
    stat(s, L, Inches(2.0), cw, "99%", "of rewrites rejected under the prompt teachers type (297 of 300), against 13% with careful prompts (82 of 620)", RUST)
    stat(s, L + Inches(3.95), Inches(2.0), cw, "18 / 54", "rewrites with a provably changed answer that the best AI judge caught (best free large judge: 7)", BLUE)
    stat(s, L + Inches(7.9), Inches(2.0), cw, "5 / 5", "disputed cases where AI sided with the lenient human reading (overruled on review)", NAVY)
    text(s, L, Inches(5.35), W, Inches(1.2),
         [[("So: ", {"bold": True, "color": RUST}),
           ("a safeguard can't rely on prompt discipline or on another AI. It has to check the output with rules and "
            "answer recomputation, and keep humans as the ground truth.", {})]], 19)
    S.append(s)

    # 5 example
    s = new_slide(prs)
    header(s, "One example", "Easier to read, and two steps already done")
    text(s, L, Inches(2.0), Inches(5.5), Inches(0.3), "ORIGINAL (practice problem)", 13, RUST, bold=True)
    text(s, L, Inches(2.35), Inches(5.5), Inches(2.2), [[("James builds a 20 story building. The first 10 stories are each 12 feet tall each. ", {}),
         ("The remaining floors are each 3 feet taller.", {"bold": True}), (" How tall is the building?", {})]], 20, NAVY, SERIF)
    text(s, L + Inches(6.05), Inches(2.0), Inches(5.5), Inches(0.3), "REWRITE (free 3B model, plain-language prompt)", 13, RUST, bold=True)
    text(s, L + Inches(6.05), Inches(2.35), Inches(5.5), Inches(2.2), [[("… ", {}), ("The remaining 10 stories are 15 feet tall each.", {"bold": True}),
         (" How tall is the building?", {})]], 20, NAVY, SERIF)
    bullets(s, [("Done for the student: ", "20 − 10 = 10 floors, and 12 + 3 = 15 feet."),
                ("Verdicts: ", "Qwen 32B and Gemma 12B judges SAFE · Claude Haiku and GPT-6 Luna UNSAFE · free rule layer REJECT (two derived values).")],
            y=4.75, h=2.0)
    S.append(s)

    # 6 approach
    s = new_slide(prs)
    header(s, "Solution approach · overview", "Measure, check, then decide")
    cols = [("1 · Measure", "Real problems → AI rewrites under careful and realistic prompts, plus a non-AI control → blind, double human labels."),
            ("2 · Check", "Free rules → AI critic → recompute the answer as a program → PASS / REVIEW / REJECT."),
            ("3 · Decide", "Guaranteed-safe PASS threshold · cheapest order of checks · label-efficient failure rates · where to audit.")]
    for i, (h, b) in enumerate(cols):
        x = L + Inches(3.9 * i)
        box(s, x, Inches(2.05), Inches(3.6), Inches(3.3), PALE)
        text(s, x + Inches(0.25), Inches(2.25), Inches(3.1), Inches(0.5), h, 24, BLUE, SERIF, bold=True)
        text(s, x + Inches(0.25), Inches(2.9), Inches(3.1), Inches(2.4), b, 18)
    text(s, L, Inches(5.75), W, Inches(0.8), "Prespecified and frozen before any study data was generated. Tuned on 10 separate practice problems only.", 17, BLUE)
    S.append(s)

    # 7 design
    s = new_slide(prs)
    header(s, "Solution approach · study and checker", "1,044 AI rewrites, checked on one GPU at $0")
    bullets(s, [("Problems: ", "124 from GSM8K, ASDiv and GSM1K (contamination check), stratified by steps × relational cues."),
                ("Conditions: ", "careful plain-language and chunked prompts · the realistic teacher prompt · a non-AI sentence splitter (control)."),
                ("Rewriters: ", "Qwen 14B, Gemma 12B, Llama 3B (free, open weights)."),
                ("Checker: ", "rules (numbers, relations, leaked operations and values) → AI critic with cited evidence → program recomputation."),
                ("Judges compared: ", "3 free local models and 4 paid frontier models (Claude Haiku and Sonnet 5.5, GPT-6 Luna, GPT-6.1 Sol): $11.42 in total."),
                ("Labels: ", "1,062 items, two blind annotators, 30% double-labelled (due Dec 1).")], size=18)
    S.append(s)

    # 8 result 1
    s = new_slide(prs)
    header(s, "Evaluation · result 1", "The prompt decides whether the task survives")
    s.shapes.add_picture(str(VID / "fig_prompt.png"), L, Inches(1.85), height=Inches(4.15))
    text(s, Inches(9.45), Inches(2.0), Inches(3.4), Inches(4.5),
         [[("Control: ", {"bold": True}), ("a non-AI splitter gets 0 REJECT of 124.", {})],
          [("Realistic prompt adds, ", {"bold": True}), ("of 300: an operation (266), precomputed values (260), equations (239), steps (201).", {})]],
         16, space=14)
    text(s, L, Inches(6.25), W, Inches(0.6), "Checker: automated decisions on the main run. Human: adjudicated labels on 70 practice-problem rewrites.", 13, BLUE)
    S.append(s)

    # 9 result 2
    s = new_slide(prs)
    header(s, "Evaluation · result 2", "AI judges miss most real errors")
    s.shapes.add_picture(str(VID / "fig_judges.png"), L, Inches(1.85), height=Inches(4.3))
    text(s, Inches(9.75), Inches(2.0), Inches(3.1), Inches(4.6),
         ["Paid judges catch 2–3× more than large free ones; the best still misses 36 of 54.",
          "Price buys little: Haiku ($0.47) ≈ Sonnet ($7.08).",
          "Qwen 32B and Gemma 12B agree on only 4 of the rewrites they flag."], 16, space=14)
    S.append(s)

    # 10 result 3
    s = new_slide(prs)
    header(s, "Evaluation · result 3", "The line is a value judgement; AI leans lenient")
    stat(s, L, Inches(2.0), Inches(3.6), "κ 0.79", "two blind annotators on SAFE (n = 70). All 5 disagreements: one strict, one lenient.", BLUE)
    stat(s, L + Inches(3.95), Inches(2.0), Inches(3.6), "5 / 5", "an AI adjudicator sided with the lenient label. The owner reviewed all 30 and overrode all 5 to UNSAFE.", RUST)
    stat(s, L + Inches(7.9), Inches(2.0), Inches(3.6), "κ 0.79", "an AI labeller (Mistral 24B) vs the final labels: the same as the lenient annotator.", NAVY)
    text(s, L, Inches(4.95), W, Inches(1.6),
         [[("Disputed cases: ", {"bold": True}), ("“If he ate half…, how many…?” restated as a fact · a dangling “If…” fragment · “Here is what you need to know”.", {})],
          [("Response: ", {"bold": True}), ("rubric v1.2 states the strict reading, with examples, before main-study labelling. Final labels are human.", {})]],
         18, space=12)
    S.append(s)

    # 11 result 4
    s = new_slide(prs)
    header(s, "Evaluation · result 4", "What “free” buys a school")
    bullets(s, [("$0 on one GPU: ", "the whole study runs in about 1.5 days. Student materials never leave campus."),
                ("A size floor: ", "Llama 3B produced a usable chunked rewrite for 1 of 124 problems (Qwen 14B and Gemma 12B: 124 of 124). As a judge it flags 85%."),
                ("Small isn't cheap: ", "the Qwen 4B critic was about 25× slower than the 32B. It reasons until cut off."),
                ("Teacher time is the binding cost: ", "one REVIEW takes about 1.5 min, and a third of careful-prompt rewrites go to REVIEW."),
                ("Stable outputs: ", "93% of regenerations are text-identical; SAFE flipped on 2 of the 10 that changed.")])
    S.append(s)

    # 12 decision layer
    s = new_slide(prs)
    header(s, "Solution approach · from checker to decision", "A checker is not a policy")
    bullets(s, [("Guaranteed PASS ", "(conformal risk control, Learn-then-Test): of what we pass, at most α is unsafe, with probability ≥ 1 − δ."),
                ("Label-efficient rates ", "(prediction-powered inference, stratum-weighted): unbiased failure rates from a labelled subset plus checker verdicts."),
                ("Cost-aware cascade: ", "the cheapest order of rules → AI critic → human for a target safety level (Pareto frontier)."),
                ("Where to audit ", "(Stackelberg audit game): spend a district's limited audit budget where a lenient tool would do most harm."),
                ("Robustness: ", "a red-team attacker cuts held-out recall from 0.73 to 0.67 over 3 rounds (n = 15 per round); weighted conformal holds under shift (synthetic).")],
            size=18, h=3.9)
    text(s, L, Inches(6.0), W, Inches(0.6), "Built, unit-tested (230 tests) and run end to end. Final numbers on human labels: Dec 3.", 16, BLUE, bold=True)
    S.append(s)

    # 13 ethics
    s = new_slide(prs)
    header(s, "Ethical implications and broader impact", "Who could be helped, who could be harmed")
    box(s, L, Inches(1.95), Inches(3.5), Inches(4.75), PALE)
    text(s, L + Inches(0.25), Inches(2.1), Inches(3.0), Inches(4.5),
         [[("Intended benefit", {"bold": True, "color": BLUE, "font": SERIF, "size": 22})],
          "Students with disabilities get the access they are owed without the bar silently dropping.",
          "Districts can audit vendor tools.",
          [("Scope", {"bold": True, "color": BLUE, "font": SERIF, "size": 22})],
          "English, GSM-style arithmetic, one rubric, no student outcomes yet."], 16, space=8)
    bullets(s, [("False reassurance: ", "a PASS is evidence, not proof. Mitigations: a stated error guarantee, REVIEW goes to a person, humans have final authority."),
                ("Whose line? ", "The rubric reflects two annotators, not special-education teachers, students or families. Validate with them before deployment."),
                ("Over-blocking: ", "a false REJECT also hurts the student, so we report false alarms, not just catches."),
                ("Equity and privacy: ", "cheaper models fail more often. The free on-campus tier keeps student data local."),
                ("Dual use: ", "the red-team attacker shows how to evade a checker; it is released as an evaluation tool only.")],
            y=1.95, h=4.9, size=16, x=L + Inches(3.8), w=Inches(7.75))
    S.append(s)

    # 14 limitations / next
    s = new_slide(prs)
    header(s, "Limitations and next steps", "What's done, what's left")
    bullets(s, [("Done: ", "the frozen design, the 1,044-rewrite main run, 7 judges, calibration, rubric v1.2, and every decision method built and tested."),
                ("Dec 1–3: ", "main-study human labels (1,062 items, two blind annotators), then joint adjudication, final rates, the guaranteed-PASS threshold, cascade and audit game."),
                ("Limitations: ", "human labels so far cover 70 practice items · 8% of rewrites can't be recomputed · 3 rewriters · English only."),
                ("Next: ", "validate the rubric with special-education teachers · a student study (do safe rewrites help?) · beyond arithmetic word problems.")])
    S.append(s)

    # 15 take-home
    s = new_slide(prs, NAVY)
    header(s, "Take-home", "Easier to read, verified before a student sees it", dark=True)
    paras = [[("The failure is real: ", {"bold": True, "color": PEACH}), ("with the prompt teachers type, 297 of 300 rewrites gave away operations, values or steps.", {"color": LIGHT})],
             [("AI can't grade AI here: ", {"bold": True, "color": PEACH}), ("the best judge caught 18 of 54 rewrites whose answer provably changed, and AI sided with the lenient reading.", {"color": LIGHT})],
             [("What works: ", {"bold": True, "color": PEACH}), ("rules plus answer recomputation, AI as one signal, humans as ground truth, guarantees on what passes. It runs at $0.", {"color": LIGHT})]]
    text(s, L, Inches(2.4), W, Inches(3.5), paras, 21, space=18)
    text(s, L, Inches(6.4), W, Inches(0.4), "Code, data card and technical appendix: github.com/harshitaggarwal01/cs2880", 14, MUTE)
    S.append(s)

    for i, s in enumerate(S, 1):
        footer(s, i, dark=i in (1, 15))
        s.notes_slide.notes_text_frame.text = notes.get(i, "")
    prs.save(str(out))
    print(f"wrote {out}: {len(S)} slides")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
