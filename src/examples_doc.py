"""Write docs/run_examples.md: verbatim outputs and verifier evidence from the anthropic-v1 pilot and the earlier pilot.

  python src/examples_doc.py      # rewrites docs/run_examples.md from the run files (no retyping)

The example picks and "Our read" commentary are hand-written for the Nov 2 pilot; update them if verdicts change.
"""
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/outputs/anthropic-v1"
load = lambda p: [json.loads(l) for l in open(p)]
gens = {r["output_id"]: r for r in load(RUN / "pilot_generations.jsonl")}
ver = {r["output_id"]: r for r in load(RUN / "pilot_generations.verify-critic-det-program.jsonl")}
src = {r["source_id"]: r for r in load(ROOT / "data/frozen/dev.jsonl")}
old = {r["output_id"]: r for r in load(ROOT / "pilot/pilot_outputs.jsonl")}
ledger = list(csv.DictReader(open(RUN / "ledger.csv")))

MODEL = {"haiku55": "Claude Haiku 5.5", "sonnet55": "Claude Sonnet 5.5"}
STYLE = {"plain": "plain language", "chunked": "chunked"}
out = []
w = out.append


def oid(gen, tf, sid):
    return f"anthropic-v1|{gen}|{tf}|{sid}"


def answer(sid):
    return src[sid]["answer"].split("####")[-1].strip()


def source_block(sid):
    w(f"**Original** (`{sid}`, GSM8K train; answer {answer(sid)})\n")
    w("> " + " ".join(src[sid]["text"].split()) + "\n")


def checker_lines(r):
    det = r["deterministic"]["flags"]
    c, p = r["critic"] or {}, r["program"] or {}
    lines = [f"- **Decision: {r['decision']}**" + (f" (reasons: {', '.join('`'+x+'`' for x in r['reasons'])})" if r["reasons"] else "")]
    lines.append("- Rules (layer 1): " + ("; ".join(f"`{f['code']}` ({f['severity']}): {f['detail']}" for f in det) if det else "no flags"))
    crit = f"- AI reviewer (layer 2, Claude Opus 5.5): **{c.get('overall')}**"
    if c.get("failure_codes"):
        crit += f", codes {', '.join(c['failure_codes'])}"
    lines.append(crit)
    lines.append(f"- Answer recompute (layer 3): {p.get('status')}, original {p.get('source_value'):g} vs rewrite "
                 f"{p.get('candidate_value'):g}" + ("" if p.get("relation_types_equal", True) else "; extracted relation types differ"))
    return lines


def output_block(gen, tf, sid, evidence=False):
    k = oid(gen, tf, sid)
    g, r = gens[k], ver[k]
    w(f"**{MODEL[gen]} · {STYLE[tf]}** (status `{g['status']}`)\n")
    w("```text\n" + g["adapted_problem"].strip() + "\n```\n")
    w("\n".join(checker_lines(r)) + "\n")
    if evidence:
        for e in (r["critic"] or {}).get("evidence", []):
            w(f"  - Reviewer's evidence, quoted: *\"{e['issue']}\"*")
        w("")


# ------------------------------------------------------------------ header
dec = collections.Counter(r["decision"] for r in ver.values())
tot = sum(float(x["usd"]) for x in ledger)
by_stage = collections.defaultdict(float)
for x in ledger:
    by_stage[x["stage"]] += float(x["usd"])
w("# Real Examples from Our Runs\n")
w("**SafeAdapt-Math · CS 2880 · for discussion with the professor**\n")
w("Every rewrite and every checker verdict below is copied programmatically from the run files, not retyped. "
  "Sources are real GSM8K problems from our 10 practice (dev) problems; the 124 study problems have not been used.\n")
w("## What was run (Nov 2, run `anthropic-v1`)\n")
w("| | |\n|---|---|")
w("| Problems | 10 practice problems (GSM8K train, frozen with seed 2880) |")
w("| Rewriters | Claude Haiku 5.5 and Claude Sonnet 5.5, real API calls |")
w("| Styles | `plain_v1` (plain language) and `chunked_v1` (one fact per line), our careful prompts |")
w(f"| Outputs | {len(gens)} rewrites |")
w("| Checker | rules → AI reviewer (Claude Opus 5.5) → extract both versions as a program and recompute the answer |")
w(f"| Cost | ${tot:.2f} total: rewriting ${by_stage['gen']:.2f}, AI reviewer ${by_stage['critic']:.2f}, "
  f"answer recompute ${by_stage['extract']:.2f} ({len(ledger)} API calls) |")
w(f"| Checker decisions | {dec['PASS']} PASS · {dec['REVIEW']} REVIEW · {dec['REJECT']} REJECT |")
w("")
w("**Read these as examples, not rates.** There are no human labels yet (calibration labelling is next), "
  "the realistic teacher prompt was not part of this run, and the reviewer is from the same company as the rewriters.\n")

w("### Decisions by model and style\n")
w("| Model · style | PASS | REVIEW | REJECT | Same answer when recomputed |\n|---|---:|---:|---:|---:|")
for gen in ("haiku55", "sonnet55"):
    for tf in ("plain", "chunked"):
        rows = [v for k, v in ver.items() if f"|{gen}|{tf}|" in k]
        c = collections.Counter(r["decision"] for r in rows)
        same = sum(r["program"]["status"] == "MATCH" for r in rows)
        w(f"| {MODEL[gen]} · {STYLE[tf]} | {c['PASS']} | {c['REVIEW']} | {c['REJECT']} | {same}/{len(rows)} |")
w("")

# ------------------------------------------------------------------ examples
w("---\n\n## Example 1: one problem, four rewrites (false alarm, real catch, clean pass)\n")
source_block("gsm8k-train-2016")
w("")
output_block("sonnet55", "plain", "gsm8k-train-2016")
w("**Our read: false alarm.** The rewrite is faithful and the answer is unchanged. The rule for leaked derived values "
  "fired because the new word \"three\" (counting the deductions) happens to equal a number that can be computed from "
  "the problem. Counting words should not count as leaks; this rule gets tuned on practice problems.\n")
output_block("haiku55", "chunked", "gsm8k-train-2016", evidence=True)
w("**Our read: real catch.** Splitting the sentence into bullets detached \"from her weekly earnings\" from the 5% "
  "line. A student could take 5% of what is left after tax and get a different answer. No word-matching rule sees "
  "this; the AI reviewer did, and the item goes to a human.\n")
output_block("sonnet55", "chunked", "gsm8k-train-2016")
w("**Our read: the right way to chunk it.** Sonnet repeated \"From her weekly earnings\" on every deduction line, "
  "which keeps the meaning that Haiku's version lost. Same layout, and this time the math is unchanged.\n")
output_block("haiku55", "plain", "gsm8k-train-2016")
w("**Our read: correct abstention.** Haiku judged the problem already clear and returned it unchanged.\n")
w("**Takeaway.** Same problem, four outputs: a false alarm, a real catch, the fix done right, and a safe no-change. "
  "The checker needs every layer, and the review step needs to stay.\n")

w("---\n\n## Example 2: a faithful rewrite flagged by an over-strict rule\n")
source_block("gsm8k-train-1795")
w("")
output_block("sonnet55", "chunked", "gsm8k-train-1795")
w("**Our read: false alarm.** One fact per line, every relation kept, same answer. The recompute layer compares the "
  "*types* of relations it extracts, and splitting compound sentences changes how they are extracted. That "
  "comparison fired on 18 of 40 rewrites, all with matching answers; it is the main cause of the review load.\n")

w("---\n\n## Example 3: one word changed, one rule fires\n")
source_block("gsm8k-train-5510")
w("")
output_block("haiku55", "plain", "gsm8k-train-5510")
output_block("sonnet55", "plain", "gsm8k-train-5510")
w("**Our read.** Both plain rewrites are faithful. Haiku changed \"altogether\" to \"in total\" and \"placed\" to "
  "\"put … into the book\", so the rules saw a quantifier lost, one added, and the question reworded: REVIEW. "
  "Sonnet kept \"altogether\": PASS. The rules are deliberately sensitive to math words; the question for tuning is "
  "how much synonym change to allow.\n")

w("---\n\n## Example 4: a rewrite that quietly resolves an ambiguity\n")
source_block("gsm8k-train-5378")
w("")
output_block("sonnet55", "plain", "gsm8k-train-5378")
w("**Our read: worth discussing.** The original says the remaining floors are \"3 feet taller\" without saying "
  "taller than what. Sonnet made it explicit: \"3 feet taller than each of the first 10 stories.\" That is the "
  "intended reading (answer 270 either way), but it removes an interpretation step the original left to the "
  "student. Our rubric records this as *resolved ambiguity*: is that a fair accommodation or a small modification?\n")

w("---\n\n## Example 5: repeating the original's own words triggers a soft flag\n")
source_block("gsm8k-train-5508")
w("")
output_block("sonnet55", "chunked", "gsm8k-train-5508", evidence=True)
w("**Our read: safe, correctly sent to REVIEW rather than rejected.** \"Add\" is an operation word, but it already "
  "appears in the original (\"add 50 rows of beads\"), so the rule downgrades it to REVIEW. The reviewer explains "
  "why it is fine.\n")

w("---\n\n## Example 6: the model correctly declines to rewrite\n")
source_block("gsm8k-train-3578")
w("")
output_block("haiku55", "plain", "gsm8k-train-3578")
w("**Our read: correct abstention.** The problem is already short and clear, and the prompt allows "
  "`NO_REWRITE_NEEDED`. Changing nothing is the safe choice here.\n")

w("---\n\n## Example 7: clean chunking\n")
source_block("gsm8k-train-1097")
w("")
output_block("sonnet55", "chunked", "gsm8k-train-1097")
w("**Our read: what we want.** One fact per line, original wording, nothing added, question last. Compare it with "
  "what the realistic teacher prompt produced on the same problem (next section).\n")

# ------------------------------------------------------------------ earlier pilot
w("---\n\n## From the earlier pilot (Oct 16): the realistic teacher prompt\n")
w("These outputs are from our first, smaller pilot. They were generated through Claude Code subagents, not the API "
  "pipeline, and their labels are preliminary (AI-proposed, being re-labelled by both teammates). The prompt is what "
  "a teacher might actually type: *\"Rewrite this math word problem so it is easier to understand for a student with "
  "ADHD or dyslexia. Use simple language and break it into small chunks.\"* With preliminary labels, 13 of 20 "
  "realistic-prompt rewrites were unsafe, against 0 of 50 under our careful prompts.\n")
for key, label, read in (
    ("pilot-opus-naive-gsm8k-train-1097", "Claude Opus 5.5 · realistic teacher prompt", "**Strategy leakage.** The "
     "rewritten problem is faithful, but the appended \"Steps to try\" tell the student which operations to do and "
     "in what order. The answer is unchanged; the task is not. Opus did this in 10 of 10 realistic-prompt outputs."),
    ("pilot-haiku-naive-gsm8k-train-5378", "Claude Haiku 5.5 · realistic teacher prompt", "**Intermediate-result "
     "leakage.** Splitting the building into stories 1–10 and 11–20 gives the student the count of the remaining "
     "floors (10), a value they were meant to work out."),
):
    r = old[key]
    w(f"**{label}** on `{r['source_id']}` (answer {answer(r['source_id'])})\n")
    w("> " + " ".join(src[r["source_id"]]["text"].split()) + "\n")
    text = r["adapted_problem"] or r["raw_output"]
    w("```text\n" + text.strip() + "\n```\n")
    w(read + "\n")

# ------------------------------------------------------------------ appendix
w("---\n\n## Appendix: all 40 checker decisions from this week's run\n")
w("| Problem | Model · style | Decision | Reasons |\n|---|---|---|---|")
for k in sorted(ver, key=lambda k: (k.split("|")[3], k.split("|")[1], k.split("|")[2])):
    _, gen, tf, sid = k.split("|")
    r = ver[k]
    w(f"| `{sid}` | {MODEL[gen].replace('Claude ', '')} · {tf} | {r['decision']} | "
      f"{', '.join(r['reasons']) if r['reasons'] else '—'} |")
w("\nFiles: `data/outputs/anthropic-v1/pilot_generations.jsonl` (rewrites), "
  "`pilot_generations.verify-critic-det-program.jsonl` (checker), `ledger.csv` (cost); earlier pilot in `pilot/`.")
(ROOT / "docs/run_examples.md").write_text("\n".join(out) + "\n")
print("written", len(out), "lines")
