"""Run: python -m unittest tests.test_push_hf -v   (offline; no network)"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import push_hf  # noqa: E402


class Filters(unittest.TestCase):
    def test_restricted_rows(self):
        self.assertTrue(push_hf.restricted_row({"source_id": "gsm1k-test-0028", "adapted_problem": "x"}))
        self.assertTrue(push_hf.restricted_row({"source_id": "gsmic-2step-1", "text": "y"}))
        self.assertFalse(push_hf.restricted_row({"source_id": "gsm1k-test-0028", "text": None}))   # ids only
        self.assertFalse(push_hf.restricted_row({"source_id": "gsm8k-train-1", "text": "z"}))

    def test_copy_jsonl_drops_restricted(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "a.jsonl", Path(d) / "out" / "a.jsonl"
            rows = [{"output_id": "r|g|plain|gsm8k-train-1", "adapted_problem": "ok"},
                    {"output_id": "r|g|plain|gsm1k-test-2", "adapted_problem": "secret text"}]
            src.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            self.assertEqual(push_hf.copy_jsonl(src, dst), (1, 1))
            self.assertNotIn("gsm1k", dst.read_text())

    def test_secret_pattern(self):
        self.assertTrue(push_hf.SECRET.search("key=sk-ant-" + "a" * 40))
        self.assertTrue(push_hf.SECRET.search("hf_" + "B" * 34))
        self.assertFalse(push_hf.SECRET.search("grep the diff for the sk- prefix"))

    def test_build_stages_whitelist_without_gsmic_or_raw(self):
        old = push_hf.STAGE
        with tempfile.TemporaryDirectory() as d:
            push_hf.STAGE = Path(d) / "stage"
            try:
                push_hf.build(runs=[])
                names = {str(p.relative_to(push_hf.STAGE)) for p in push_hf.STAGE.rglob("*") if p.is_file()}
                self.assertIn("frozen/main.jsonl", names)
                self.assertIn("README.md", names)
                self.assertIn("CHECKSUMS.sha256", names)
                self.assertFalse(any("gsmic" in n for n in names))
                self.assertFalse(any(n.startswith("raw/") for n in names))
            finally:
                push_hf.STAGE = old


if __name__ == "__main__":
    unittest.main()
