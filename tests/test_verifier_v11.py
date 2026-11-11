"""Verifier v1.1 tuning (dev problems only). Texts below are dev-set (gsm8k-train-2016, -5378, -5510, -1097)
rewrites from the anthropic-v1 pilot or constructed variants; they are software tests, not measured failures."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import read_jsonl  # noqa: E402
from deterministic_checks import check, readable, relation_changes  # noqa: E402
from verify import VERIFIER_VERSION, decide, decide_subset, redecide_file  # noqa: E402

VIKKI = ("Vikki worked 42 hours in one week. Her hourly pay rate is $10. From her weekly earnings, 20% is deducted as "
         "tax, 5% is deducted as insurance cover, and $5 is deducted for union dues. How much money, in dollars, does "
         "Vikki take home after deductions?")
VIKKI_3WAYS = ("Vikki worked 42 hours in one week. She is paid $10 per hour. Money is taken out of her weekly earnings in "
               "three ways: 20% is taken out for tax, 5% is taken out for insurance, and $5 is taken out for union dues. "
               "How much money, in dollars, does Vikki take home after these deductions?")
JAMES = ("James builds a 20 story building.  The first 10 stories are each 12 feet tall each.  The remaining floors are "
         "each 3 feet taller.  How tall is the building?")
SAFE_CRITIC = {"overall": "SAFE", "failure_codes": [], "math_fidelity": "PASS", "instructional_leakage": "NONE"}
codes = lambda r: {f["code"]: f["severity"] for f in r["flags"]}


class NumberWords(unittest.TestCase):
    def test_three_ways_not_rejected(self):
        r = check(VIKKI, VIKKI_3WAYS, "plain")
        self.assertNotEqual(r["decision"], "REJECT")
        self.assertEqual(codes(r).get("NUMBER_WORD_ADDED"), "REVIEW")
        self.assertNotIn("LEAK_DERIVED_VALUE", codes(r))

    def test_digit_three_still_rejected(self):
        r = check(VIKKI, VIKKI_3WAYS.replace("three ways", "3 ways"), "plain")
        self.assertEqual(codes(r).get("LEAK_DERIVED_VALUE"), "REJECT")

    def test_word_above_ten_still_rejected(self):
        src = "A theater sells 15 tickets in each of 8 rows. 20 tickets are canceled. How many tickets remain sold?"
        cand = "A theater sells 15 tickets in each of 8 rows, so one hundred twenty in all. 20 are canceled. How many remain sold?"
        self.assertEqual(check(src, cand)["decision"], "REJECT")

    def test_stories_11_to_20_still_flags(self):
        old = {r["output_id"]: r for r in read_jsonl(ROOT / "pilot" / "pilot_outputs.jsonl")}
        cand = old["pilot-haiku-naive-gsm8k-train-5378"]["adapted_problem"]
        r = check(JAMES, cand, "naive")
        self.assertEqual(r["decision"], "REJECT")
        self.assertEqual(codes(r).get("LEAK_DERIVED_VALUE"), "REJECT")

    def test_leak_stress_cases_still_caught(self):
        for case in read_jsonl(ROOT / "tests" / "stress_cases.jsonl"):
            if case["label"].startswith("LEAK") and case["expect"] == "REJECT":
                with self.subTest(case=case["case"]):
                    self.assertEqual(check(case["source"], case["candidate"])["decision"], "REJECT")


class Synonyms(unittest.TestCase):
    def test_total_class(self):
        for a, b in (("altogether", "in total"), ("altogether", "total"), ("combined", "altogether"), ("total", "combined")):
            with self.subTest(a=a, b=b):
                lost, added = relation_changes(f"Karl has 25. Ben has 5. How many do they have {a}?",
                                               f"Karl has 25. Ben has 5. How many do they have {b}?")
                self.assertEqual((lost, added), ({}, {}))

    def test_remaining_class(self):
        src = "His daughter took 40 from the remaining cookies. He ate half of the remaining cookies."
        for b in ("left", "other", "rest"):
            with self.subTest(b=b):
                cand = src.replace("the remaining", f"the {b}") if b != "left" else src.replace("the remaining cookies", "the cookies that were left")
                if b == "rest":
                    cand = src.replace("the remaining cookies", "the rest of the cookies")
                lost, added = relation_changes(src, cand)
                self.assertEqual(lost, {}, cand)

    def test_untracked_member_alone_never_flags(self):
        lost, added = relation_changes("Sam has 3 apples left.", "Sam has 3 apples.")
        self.assertEqual((lost, added), ({}, {}))

    def test_cross_class_swap_still_flags(self):
        lost, added = relation_changes("How many are remaining?", "How many in total?")
        self.assertTrue(lost and added)

    def test_genuine_loss_still_flags(self):
        lost, _ = relation_changes("How many are remaining?", "How many are there?")
        self.assertIn(r"\bremaining\b", lost)

    def test_each_duplicate(self):
        cand = "James builds a 20 story building. The first 10 stories are each 12 feet tall. The remaining floors are each 3 feet taller. How tall is the building?"
        self.assertEqual(relation_changes(JAMES, cand), ({}, {}))
        no_each = cand.replace("are each", "are")
        self.assertIn(r"\beach\b", relation_changes(JAMES, no_each)[0])

    def test_pilot_haiku_5510_synonym_gone_target_kept(self):
        src = ("Karl, Ryan, and Ben are fond of collecting stickers. Karl has 25 stickers. Ryan has 20 more stickers "
               "than Karl. Ben has 10 fewer stickers than Ryan. They placed all their stickers in one sticker book. "
               "How many stickers did they place altogether?")
        cand = ("Karl, Ryan, and Ben like to collect stickers. Karl has 25 stickers. Ryan has 20 more stickers than Karl. "
                "Ben has 10 fewer stickers than Ryan. They put all of their stickers into one sticker book. How many "
                "stickers did they put in the book in total?")
        c = codes(check(src, cand, "plain"))
        self.assertNotIn("RELATION_OR_QUANTIFIER_LOST", c)
        self.assertNotIn("RELATION_OR_QUANTIFIER_ADDED", c)
        self.assertIn("TARGET_WORDING_CHANGED", c)  # threshold unchanged


class Readable(unittest.TestCase):
    def test_cue_names(self):
        self.assertEqual(readable(r"\badd(?:ing|ed)?\b"), "add")
        self.assertEqual(readable(r"\bmultipl(?:y|ying|ied)\b"), "multiply")
        self.assertEqual(readable(r"\btake away\b"), "take away")
        self.assertEqual(readable(r"times as (?:many|much|long|tall|old|fast)"), "times as many")

    def test_flag_detail_uses_names(self):
        src = "Carly is going to add 50 rows of beads. Beads cost $1 per 10 beads. How much do the beads cost?"
        cand = "Carly is going to add 50 rows of beads. She will add them all. Beads cost $1 per 10 beads. How much do the beads cost?"
        det = [f for f in check(src, cand)["flags"] if f["code"] == "LEAK_OPERATION"][0]
        self.assertIn("add", det["detail"])
        self.assertNotIn("addinged", det["detail"])


class ChunkFormat(unittest.TestCase):
    SRC = "Karl has 25 stickers. Ryan has 20 more stickers than Karl. How many stickers does Ryan have?"

    def test_good_chunked_no_flag(self):
        cand = "- Karl has 25 stickers.\n- Ryan has 20 more stickers than Karl.\nQuestion: How many stickers does Ryan have?"
        self.assertNotIn("CHUNK_FORMAT", codes(check(self.SRC, cand, "chunked")))

    def test_missing_dash_is_review(self):
        cand = "Karl has 25 stickers.\n- Ryan has 20 more stickers than Karl.\nQuestion: How many stickers does Ryan have?"
        r = check(self.SRC, cand, "chunked")
        self.assertEqual(codes(r).get("CHUNK_FORMAT"), "REVIEW")
        self.assertEqual(r["decision"], "REVIEW")

    def test_missing_question_line(self):
        cand = "- Karl has 25 stickers.\n- Ryan has 20 more stickers than Karl.\n- How many stickers does Ryan have?"
        self.assertIn("Question", [f for f in check(self.SRC, cand, "chunked")["flags"] if f["code"] == "CHUNK_FORMAT"][0]["detail"])

    def test_plain_not_checked(self):
        self.assertNotIn("CHUNK_FORMAT", codes(check(self.SRC, self.SRC, "plain")))


class RelationsDiffer(unittest.TestCase):
    DET = {"decision": "PASS", "flags": []}

    def test_match_with_different_relations_passes(self):
        prog = {"status": "MATCH", "relation_types_equal": False}
        self.assertEqual(decide(self.DET, SAFE_CRITIC, prog), ("PASS", []))

    def test_decide_subset_agrees(self):
        row = {"deterministic": self.DET, "critic": SAFE_CRITIC, "program": {"status": "MATCH", "relation_types_equal": False}}
        for layers in ({"det", "critic", "program"}, {"det", "program"}):
            self.assertEqual(decide_subset(row, layers)[0], "PASS")

    def test_mismatch_still_rejects(self):
        self.assertEqual(decide(self.DET, SAFE_CRITIC, {"status": "MISMATCH", "relation_types_equal": False})[0], "REJECT")

    def test_unsure_critic_still_reviews(self):
        self.assertEqual(decide(self.DET, {**SAFE_CRITIC, "overall": "UNSURE"}, {"status": "MATCH", "relation_types_equal": False}),
                         ("REVIEW", ["critic:UNSURE"]))


class Redecide(unittest.TestCase):
    def test_redecide_offline(self):
        src = {"s1": VIKKI}
        gen = {"output_id": "o1", "source_id": "s1", "transformation": "plain", "adapted_problem": VIKKI_3WAYS}
        old = {"output_id": "o1", "layers": ["critic", "det", "program"], "decision": "REJECT",
               "reasons": ["det:LEAK_DERIVED_VALUE"], "deterministic": {}, "critic": SAFE_CRITIC,
               "program": {"status": "MATCH", "relation_types_equal": False}}
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "g.jsonl").write_text(json.dumps(gen) + "\n")
            (d / "v.jsonl").write_text(json.dumps(old) + "\n")
            rows = redecide_file(d / "v.jsonl", d / "g.jsonl", d / "v11.jsonl", src)
            self.assertEqual(rows[0]["decision"], "REVIEW")
            self.assertIn("det:NUMBER_WORD_ADDED", rows[0]["reasons"])
            self.assertEqual(rows[0]["verifier_version"], VERIFIER_VERSION)
            self.assertEqual(rows[0]["redecided_from"]["decision"], "REJECT")
            self.assertEqual(json.loads((d / "v.jsonl").read_text())["decision"], "REJECT")  # input untouched
            with self.assertRaises(ValueError):
                redecide_file(d / "v.jsonl", d / "g.jsonl", d / "v.jsonl", src)


if __name__ == "__main__":
    unittest.main()
