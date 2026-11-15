"""Layer 1 of the verifier: cheap, high-recall, reference-free checks.

Every check compares the CANDIDATE with the SOURCE; nothing here needs the
reference answer, so the same code can run in deployment. Checks are allowed
to over-flag: a false alarm costs a human review, a miss ships an unsafe
problem.

Severity
  REJECT  strong evidence of corruption or leakage (number lost/added, answer-like
          derived value, explicit step structure, explicit operation instruction)
  REVIEW  weaker evidence (relational/quantifier phrase lost, unit set changed,
          question missing, large length change, a new count written only as a word
          one..ten, chunked-format slips)

Usage:  python src/deterministic_checks.py outputs.jsonl --sources data/frozen/dev.jsonl
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction

WORD_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "dozen": 12, "half": Fraction(1, 2), "twice": 2, "double": 2,
    "triple": 3, "thrice": 3, "quarter": Fraction(1, 4), "third": Fraction(1, 3),
}
# words that are numbers grammatically but usually not task quantities when they appear alone
SOFT_WORDS = {"one", "half", "double", "third", "quarter"}

NUM_RE = re.compile(r"(?<![\w.])\$?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?:\s*/\s*(\d+))?(%?)")
WORD_RE = re.compile(r"\b(" + "|".join(sorted(WORD_NUM, key=len, reverse=True)) + r")\b", re.I)

OPERATION_CUES = [
    r"\badd(?:ing|ed)?\b", r"\bsubtract(?:ing|ed)?\b", r"\bmultipl(?:y|ying|ied)\b", r"\bdivid(?:e|ing|ed)\b",
    r"\bsum\b", r"\bproduct\b", r"\bquotient\b", r"\bdifference\b", r"\bminus\b", r"\bplus\b",
    r"\bcalculate\b", r"\bcompute\b", r"\bwork out\b", r"\bfigure out\b", r"\bfind\b", r"\bsolve\b",
    r"\bformula\b", r"\bequation\b", r"\btake away\b", r"\bsplit\b",
]
STEP_CUES = [
    r"^\s*(?:step\s*\d+|\d+[.)])", r"\bstep\s*\d+\b", r"\bsteps? to\b", r"\bfirst,?\s+(?:find|figure|work|calculate|add|multiply|subtract|divide)",
    r"\bthen\s+(?:find|figure|work|calculate|add|multiply|subtract|divide)", r"\bnext,?\s+(?:find|figure|work|calculate)",
    r"\bto (?:find|solve|get) (?:this|the answer)", r"\bhints?\b", r"\bstrategy\b", r"\btips?\b",
]
# weaker structuring/relevance cues: escalate to REVIEW only
SOFT_CUES = [
    r"\bwhat you need to (?:find|know)\b", r"\bwhat we know\b", r"\bthink about\b", r"\b(?:you )?don'?t need\b",
    r"\bextra information\b", r"\bimportant\b", r"\bremember\b", r"\bkey\b",
]
# list enumerators and step labels are layout, not quantities: strip before number checks
ENUMERATOR_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:step\s*)?\d+[.):]\s+|\bstep\s*\d+\b", re.I | re.M)
SYMBOL_CUES = [r"(?<!\w)[×÷=](?!\w)", r"\d\s*[+*x×−-]\s*\d", r"\?\s*=\s*"]

RELATIONAL_PHRASES = [
    r"times as (?:many|much|long|tall|old|fast)", r"\btwice\b", r"\bhalf (?:as|of)\b", r"\bmore than\b",
    r"\bless than\b", r"\bfewer than\b", r"\bas many as\b", r"\bas much as\b", r"\bper\b", r"\beach\b",
    r"\bevery\b", r"\bremaining\b", r"\bthe rest\b", r"\bat least\b", r"\bat most\b", r"\bonly\b",
    r"\btotal\b", r"\baltogether\b", r"\bcombined\b", r"\blonger\b", r"\btaller\b", r"%|\bpercent\b",
]
# v1.1 synonym classes: a swap within a class is neither "lost" nor "added". Members marked untracked
# (not in RELATIONAL_PHRASES) never raise a flag themselves; they only offset a tracked member's change.
# "\btotal\b" also matches "in total".
SYNONYM_CLASSES = [
    [r"\baltogether\b", r"\btotal\b", r"\bcombined\b"],
    # v1.1.1 (Nov 15): "left" / "other" only in their quantity senses, so an incidental "turn left" or
    # "other apples in the store" cannot offset a dropped "remaining"
    [r"\bremaining\b", r"\bthe rest\b", r"\b(?:is|are|was|were|be|been) left\b|\bleft over\b|\bleftover\b",
     r"\bthe other\b"],
]
# "each ... each" in the source: keeping one "each" is enough (presence, not count)
PRESENCE_ONLY = {r"\beach\b"}
CARDINAL_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
UNITS = [
    "dollars", "dollar", "\\$", "cents", "cent", "hours", "hour", "minutes", "minute", "seconds", "second",
    "days", "day", "weeks", "week", "months", "month", "years", "year", "miles", "mile", "feet", "foot", "inches",
    "inch", "yards", "yard", "meters", "meter", "kilometers", "km", "pounds", "pound", "ounces", "ounce", "grams",
    "gram", "kilograms", "kg", "liters", "liter", "gallons", "gallon", "cups", "cup", "ml", "mL", "pages", "page",
]


@dataclass
class Flag:
    code: str
    severity: str  # REJECT | REVIEW
    detail: str


# ------------------------------------------------------------------ extraction

def numbers(text: str) -> list[Fraction]:
    """All numeric literals and number words, normalised to exact fractions."""
    vals: list[Fraction] = []
    for whole, dec, den, pct in NUM_RE.findall(text):
        v = Fraction(whole.replace(",", ""))
        if dec:
            v += Fraction(int(dec), 10 ** len(dec))
        if den and int(den) != 0:
            v = v / Fraction(int(den))
        vals.append(v / 100 if pct else v)
        if pct:
            vals.append(v)  # keep the bare percentage value too, so "20%" matches "20 percent"
    for w in WORD_RE.findall(text):
        vals.append(Fraction(WORD_NUM[w.lower()]))
    return vals


def hard_numbers(text: str) -> Counter:
    """Digits and number words that are almost always task quantities."""
    c: Counter = Counter()
    for whole, dec, den, pct in NUM_RE.findall(text):
        v = Fraction(whole.replace(",", ""))
        if dec:
            v += Fraction(int(dec), 10 ** len(dec))
        if den and int(den) != 0:
            v = v / Fraction(int(den))
        c[v] += 1
    for w in WORD_RE.findall(text):
        if w.lower() not in SOFT_WORDS:
            c[Fraction(WORD_NUM[w.lower()])] += 1
    return c


def derived_values(src_vals: list[Fraction]) -> set[Fraction]:
    """Values one or two operations away from source numbers (intermediate-result proxy)."""
    base = set(v for v in src_vals if v != 0)
    one = set()
    for a, b in itertools.permutations(base, 2):
        one |= {a + b, a - b, a * b}
        if b != 0:
            one.add(a / b)
    for a in base:  # percent-of and fraction-of style values
        one |= {a * 2, a / 2}
    two = set()
    small = sorted(one | base, key=lambda x: abs(x))[:60]
    for a, b in itertools.permutations(small, 2):
        two |= {a + b, a - b, a * b}
    return {v for v in (one | two) if v > 0 and v.denominator <= 100} - base


def count_patterns(patterns: list[str], text: str, flags=re.I | re.M) -> Counter:
    return Counter({p: len(re.findall(p, text, flags)) for p in patterns})


def units(text: str) -> set[str]:
    found = set()
    for u in UNITS:
        if re.search(rf"(?<!\w){u}(?!\w)", text, re.I):
            found.add(u.lower().rstrip("s").replace("\\", ""))
    return found


def last_question(text: str) -> str:
    qs = re.findall(r"[^.?!\n]*\?", text)
    return qs[-1].strip() if qs else ""


def content_words(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were", "do", "does",
            "did", "how", "many", "much", "what", "will", "be", "she", "he", "they", "it", "her", "his", "their",
            "question", "have", "has", "had", "that", "this", "with", "at", "by"}
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in stop and len(w) > 2}


# ------------------------------------------------------------------ checks

def check(source: str, candidate: str, transformation: str = "plain") -> dict:
    flags: list[Flag] = []
    cand_numbers_text = ENUMERATOR_RE.sub(" ", candidate)
    src_h, cand_h = hard_numbers(source), hard_numbers(cand_numbers_text)

    missing = src_h - cand_h
    # a source value repeated in the candidate is not a new quantity
    added = Counter({v: n for v, n in (cand_h - src_h).items() if v not in src_h})
    if missing:
        flags.append(Flag("QTY_OMIT_OR_CHANGE", "REJECT", f"source numbers missing: {fmt(missing)}"))
    if added:
        # v1.1: a new value written only as a cardinal word one..ten (no digit form) is usually a count of
        # listed items ("taken out in three ways"); downgrade it to REVIEW. Digits keep the REJECT rules.
        words_only = [v for v in added if v <= 10 and v.denominator == 1
                      and v not in digit_values(cand_numbers_text) and v in cardinal_word_values(cand_numbers_text)]
        if words_only:
            flags.append(Flag("NUMBER_WORD_ADDED", "REVIEW",
                              f"new values written only as number words: {fmt(Counter({v: added[v] for v in words_only}))}"))
        added = Counter({v: n for v, n in added.items() if v not in words_only})
    if added:
        derived = derived_values(numbers(source))
        leak_like = [v for v in added if v in derived]
        other = [v for v in added if v not in derived]
        if leak_like:
            flags.append(Flag("LEAK_DERIVED_VALUE", "REJECT",
                              f"new numbers equal to values derivable from the source: {fmt(Counter(leak_like))}"))
        if other:
            flags.append(Flag("QTY_ADD", "REJECT", f"new numbers not in source: {fmt(Counter(other))}"))

    src_cues = count_patterns(OPERATION_CUES + STEP_CUES + SYMBOL_CUES + SOFT_CUES, source)
    for name, pats, sev in (("LEAK_OPERATION", OPERATION_CUES, "REJECT"), ("LEAK_STEPS", STEP_CUES, "REJECT"),
                            ("LEAK_SYMBOLS", SYMBOL_CUES, "REJECT"), ("STRUCTURE_OR_RELEVANCE_CUE", SOFT_CUES, "REVIEW")):
        inc = count_patterns(pats, candidate) - count_patterns(pats, source)
        if not inc:
            continue
        # a cue word already used in the source (e.g. "add 50 rows of beads") is weaker evidence
        new_kind = [p for p in inc if src_cues[p] == 0]
        sev_eff = sev if new_kind else "REVIEW"
        flags.append(Flag(name, sev_eff, ("new cues: " if new_kind else "more uses of source cue words: ")
                          + ", ".join(sorted(readable(p) for p in inc))))

    lost_rel, new_rel = relation_changes(source, candidate)
    if lost_rel:
        flags.append(Flag("RELATION_OR_QUANTIFIER_LOST", "REVIEW",
                          "phrases fewer than in source: " + ", ".join(sorted(readable(p) for p in lost_rel))))
    if new_rel:
        flags.append(Flag("RELATION_OR_QUANTIFIER_ADDED", "REVIEW",
                          "phrases not in source: " + ", ".join(sorted(readable(p) for p in new_rel))))

    su, cu = units(source), units(candidate)
    if su != cu:
        flags.append(Flag("UNIT_SET_CHANGED", "REVIEW", f"source units {sorted(su)} vs candidate {sorted(cu)}"))

    sq, cq = last_question(source), last_question(candidate)
    if not cq and sq:
        flags.append(Flag("QUESTION_MISSING", "REVIEW", "candidate has no question sentence"))
    elif sq and len(content_words(sq)) >= 2:
        overlap = len(content_words(sq) & content_words(cq)) / len(content_words(sq))
        if overlap < 0.5:
            flags.append(Flag("TARGET_WORDING_CHANGED", "REVIEW", f"question content-word overlap {overlap:.2f}"))

    if transformation == "chunked":
        bad = chunk_format_problems(candidate)
        if bad:
            flags.append(Flag("CHUNK_FORMAT", "REVIEW", "; ".join(bad)))

    ratio = len(candidate.split()) / max(1, len(source.split()))
    if ratio > 1.6:
        flags.append(Flag("LENGTH_EXPANDED", "REVIEW", f"candidate/source word ratio {ratio:.2f}"))
    if ratio < 0.6:
        flags.append(Flag("LENGTH_SHRUNK", "REVIEW", f"candidate/source word ratio {ratio:.2f}"))

    decision = "REJECT" if any(f.severity == "REJECT" for f in flags) else "REVIEW" if flags else "PASS"
    return {"decision": decision, "flags": [asdict(f) for f in flags],
            "readability": {"source_fkgl": fkgl(source), "candidate_fkgl": fkgl(candidate),
                            "source_words": len(source.split()), "candidate_words": len(candidate.split()),
                            "candidate_max_sentence_words": max_sentence_words(candidate)}}


CUE_NAMES = {
    r"\badd(?:ing|ed)?\b": "add", r"\bsubtract(?:ing|ed)?\b": "subtract", r"\bmultipl(?:y|ying|ied)\b": "multiply",
    r"\bdivid(?:e|ing|ed)\b": "divide", r"^\s*(?:step\s*\d+|\d+[.)])": "numbered line", r"\bstep\s*\d+\b": "step N",
    r"\bsteps? to\b": "step(s) to", r"\bhints?\b": "hint", r"\btips?\b": "tip", r"\b(?:you )?don'?t need\b": "don't need",
    r"(?<!\w)[×÷=](?!\w)": "× ÷ = symbol", r"\d\s*[+*x×−-]\s*\d": "inline arithmetic", r"\?\s*=\s*": "?= blank",
    r"\bto (?:find|solve|get) (?:this|the answer)": "to find/solve/get the answer", r"%|\bpercent\b": "percent",
    r"\bwhat you need to (?:find|know)\b": "what you need to find/know",
    r"\bfirst,?\s+(?:find|figure|work|calculate|add|multiply|subtract|divide)": "first <operation>",
    r"\bthen\s+(?:find|figure|work|calculate|add|multiply|subtract|divide)": "then <operation>",
    r"\bnext,?\s+(?:find|figure|work|calculate)": "next <operation>",
}


def readable(pattern: str) -> str:
    """Human name for a cue regex ("add" for the add/adding/added pattern), for flag details."""
    if pattern in CUE_NAMES:
        return CUE_NAMES[pattern]
    s = re.sub(r"\(\?:([^()]*)\)", lambda m: m.group(1).split("|")[0], pattern)  # first alternative of each group
    s = re.sub(r"\\[bsd]|\(\?<!\\w\)|\(\?!\\w\)|[\\^()?*+\[\]]", "", s)
    return " ".join(s.split()) or pattern


def digit_values(text: str) -> set[Fraction]:
    out = set()
    for whole, dec, den, _ in NUM_RE.findall(text):
        v = Fraction(whole.replace(",", ""))
        if dec:
            v += Fraction(int(dec), 10 ** len(dec))
        if den and int(den) != 0:
            v = v / Fraction(int(den))
        out.add(v)
    return out


def cardinal_word_values(text: str) -> set[Fraction]:
    return {Fraction(WORD_NUM[w.lower()]) for w in WORD_RE.findall(text) if w.lower() in CARDINAL_WORDS}


def relation_changes(source: str, candidate: str) -> tuple[Counter, Counter]:
    """Relational phrases lost / added, with v1.1 synonym classes and presence-only "each"."""
    s_cnt, c_cnt = count_patterns(RELATIONAL_PHRASES, source), count_patterns(RELATIONAL_PHRASES, candidate)
    for p in PRESENCE_ONLY:
        s_cnt[p], c_cnt[p] = min(s_cnt[p], 1), min(c_cnt[p], 1)
    lost, added = s_cnt - c_cnt, c_cnt - s_cnt
    for cls in SYNONYM_CLASSES:
        s_all, c_all = count_patterns(cls, source), count_patterns(cls, candidate)
        surplus = sum((c_all - s_all).values())   # extra uses of any member in the candidate
        deficit = sum((s_all - c_all).values())   # fewer uses of any member in the candidate
        for p in cls:
            if p in lost:
                k = min(lost[p], surplus)
                lost[p] -= k
                surplus -= k
            if p in added:
                k = min(added[p], deficit)
                added[p] -= k
                deficit -= k
    return +lost, +added


def chunk_format_problems(candidate: str) -> list[str]:
    """Presentation check for chunked outputs: fact lines start with "- ", and a "Question:" line exists."""
    lines = [l for l in candidate.strip().splitlines() if l.strip()]
    q = [i for i, l in enumerate(lines) if l.strip().lower().startswith("question")]
    out = []
    if not q:
        out.append("no 'Question:' line")
    facts = lines[:q[-1]] if q else lines
    n_bad = sum(1 for l in facts if not l.lstrip().startswith("- "))
    if n_bad:
        out.append(f"{n_bad} fact line(s) without a leading '- '")
    return out


def fmt(c: Counter) -> str:
    return ", ".join(f"{float(v):g}" + (f" x{n}" if n > 1 else "") for v, n in sorted(c.items()))


# ------------------------------------------------------------------ readability (diagnostic only)

def syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups) - (1 if word.endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+|\n+", text) if re.search(r"[A-Za-z]", s)]


def fkgl(text: str) -> float:
    sents = split_sentences(text)
    words = re.findall(r"[A-Za-z]+", text)
    if not sents or not words:
        return 0.0
    return round(0.39 * len(words) / len(sents) + 11.8 * sum(map(syllables, words)) / len(words) - 15.59, 2)


def max_sentence_words(text: str) -> int:
    return max((len(s.split()) for s in split_sentences(text)), default=0)


# ------------------------------------------------------------------ cli

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("outputs", help="JSONL with source_id, adapted_problem, transformation")
    ap.add_argument("--sources", nargs="+", required=True)
    args = ap.parse_args()
    src = {}
    for path in args.sources:
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            src[r["source_id"]] = r["text"]
    for line in open(args.outputs, encoding="utf-8"):
        r = json.loads(line)
        if not r.get("adapted_problem"):
            continue
        res = check(src[r["source_id"]], r["adapted_problem"], r.get("transformation", "plain"))
        print(json.dumps({**{k: r[k] for k in ("source_id", "model", "transformation") if k in r}, **res}))


if __name__ == "__main__":
    main()
