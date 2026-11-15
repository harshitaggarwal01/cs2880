"""Run: python -m unittest tests.test_train_checker -v   (offline; no model download, TF-IDF backend)"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import train_checker as tc  # noqa: E402


class TrainChecker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.labels, cls.rows, cls.src, cls.rew = tc.synthetic(n_sources=100, seed=5)
        cls.log = []
        cls.res = tc.fit_eval(cls.rows, cls.labels, cls.src, cls.rew, backend="tfidf", fold_log=cls.log)

    def test_recall_beats_det_only_at_matched_rate(self):
        r = self.res.set_index("method")
        for ref in ("det_only_reject", "det_only_any", "critic"):
            self.assertAlmostEqual(r.loc[f"checker@matched_{ref}", "flag_rate"], r.loc[ref, "flag_rate"], delta=0.01)
        # det-only REJECT is perfectly precise in this synthetic set, so at its rate the checker can at best tie
        self.assertGreaterEqual(r.loc["checker@matched_det_only_reject", "recall_unsafe"],
                                r.loc["det_only_reject", "recall_unsafe"] - 0.02)
        self.assertGreater(r.loc["checker@matched_critic", "recall_unsafe"], r.loc["critic", "recall_unsafe"] + 0.1)
        self.assertGreater(r.loc["checker@matched_det_only_any", "recall_unsafe"], r.loc["det_only_any", "recall_unsafe"])
        # text features add signal beyond the deterministic features alone
        self.assertGreater(r.loc["checker@matched_det_only_any", "recall_unsafe"],
                           r.loc["det_features_only@matched_det_only_any", "recall_unsafe"])

    def test_no_source_leakage_across_folds(self):
        self.assertGreaterEqual(len(self.log), 2)
        seen_test = set()
        for tr, te in self.log:
            self.assertFalse(tr & te)
            seen_test |= te
        self.assertEqual(seen_test, set(self.labels["source_id"]))
        groups = self.labels["source_id"].to_numpy()
        for tr, te in tc.source_folds(groups):
            self.assertFalse(set(groups[tr]) & set(groups[te]))

    def test_extra_baseline_critic_row(self):
        base = {o: int(s == 0) for o, s in zip(self.labels["output_id"], self.labels["SAFE"])}  # oracle
        r = tc.fit_eval(self.rows, self.labels, self.src, self.rew, baselines={"qwen_prompted": base}).set_index("method")
        self.assertAlmostEqual(r.loc["qwen_prompted", "recall_unsafe"], 1.0)
        self.assertIn("checker@matched_qwen_prompted", r.index)

    def test_level2_skips_cleanly_without_gpu(self):
        ok, reason = tc.gpu_stack_status()
        if ok:
            self.skipTest("GPU stack present; level 2 would really train")
        out = tc.lora_judge(["a"], ["b"], np.array([1]), np.array(["s"]))
        self.assertEqual(out["status"], "skipped")
        self.assertEqual(out["reason"], reason)
        self.assertNotIn("proba", out)


if __name__ == "__main__":
    unittest.main()
