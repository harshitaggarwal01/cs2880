"""Run: python -m unittest tests.test_distill -v   (offline, a few seconds)"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from distill import FLAG_CODES, _folds, features, fit_eval, leave_source_out_proba, synthetic  # noqa: E402


class DistillCase(unittest.TestCase):
    def test_features_fixed_vocab(self):
        empty = {"deterministic": {"decision": "PASS", "flags": [], "readability": {}}}
        rich = {"deterministic": {"decision": "REJECT", "readability": {
            "source_fkgl": 4.0, "candidate_fkgl": 6.5, "source_words": 20, "candidate_words": 30,
            "candidate_max_sentence_words": 17},
            "flags": [{"code": "QTY_ADD", "severity": "REJECT", "detail": ""},
                      {"code": "LENGTH_EXPANDED", "severity": "REVIEW", "detail": ""}]}}
        a, b = features(empty), features(rich)
        self.assertEqual(list(a), list(b))
        self.assertEqual([k for k in a if k.startswith("flag_")], [f"flag_{c}" for c in FLAG_CODES])
        self.assertEqual((b["flag_QTY_ADD"], b["flag_LENGTH_EXPANDED"], b["flag_LEAK_STEPS"]), (1, 1, 0))
        self.assertEqual((b["n_flags"], b["n_reject_flags"]), (2, 1))
        self.assertAlmostEqual(b["fkgl_delta"], 2.5)
        self.assertAlmostEqual(b["word_ratio"], 1.5)
        self.assertEqual(b["max_sentence_words"], 17)
        self.assertFalse(any(k.startswith("critic") for k in b))          # free layer: no critic fields by default
        c = features({**rich, "critic": {"overall": "UNSAFE", "failure_codes": ["QTY_ADD"], "math_fidelity": "FAIL"}},
                     use_critic=True)
        self.assertEqual((c["critic_UNSAFE"], c["critic_SAFE"], c["critic_code_QTY_ADD"], c["critic_math_fail"]), (1, 0, 1, 1))
        self.assertEqual(list(features(empty, use_critic=True)), list(c))

    def test_fit_eval_beats_det_on_synthetic(self):
        labels, rows = synthetic(n_sources=150, per_source=5, seed=0)
        for model in ("logreg", "gbt"):
            res = fit_eval(rows, labels, model=model).set_index("method")
            self.assertEqual(list(res.index), ["det_only_reject", "det_only_any", "distilled@matched_reject_rate",
                                               "distilled@matched_any_rate"])
            for det, dist in (("det_only_reject", "distilled@matched_reject_rate"),
                              ("det_only_any", "distilled@matched_any_rate")):
                self.assertAlmostEqual(res.loc[dist, "flag_rate"], res.loc[det, "flag_rate"], places=2)
                self.assertGreaterEqual(res.loc[dist, "recall_unsafe"], res.loc[det, "recall_unsafe"] - 0.02)
            self.assertGreater(res.loc["distilled@matched_any_rate", "auprc"], res.loc["det_only_any", "auprc"])

    def test_extra_review_rate_row(self):
        labels, rows = synthetic(n_sources=60, per_source=5, seed=1)
        res = fit_eval(rows, labels, review_rate_match=0.25)
        self.assertEqual(res["method"].iloc[-1], "distilled@rate_0.25")
        self.assertAlmostEqual(res["flag_rate"].iloc[-1], 0.25, places=2)

    def test_groupkfold_no_source_leak(self):
        labels, _ = synthetic(n_sources=40, per_source=5, seed=2)
        groups = labels["source_id"].to_numpy()
        seen = np.zeros(len(groups), dtype=int)
        for tr, te in _folds(groups, 2880).split(np.zeros((len(groups), 1)), np.zeros(len(groups)), groups):
            self.assertFalse(set(groups[tr]) & set(groups[te]))
            seen[te] += 1
        self.assertTrue((seen == 1).all())                                 # every item scored exactly once, out of fold
        # a per-source fingerprint carries no signal for unseen sources: leave-source-out must not exploit it
        rng = np.random.default_rng(0)
        ids = {g: i for i, g in enumerate(sorted(set(groups)))}
        fp = np.eye(len(ids))[[ids[g] for g in groups]]
        y = np.array([rng.random() < 0.5 for _ in ids])[[ids[g] for g in groups]].astype(int)
        p = leave_source_out_proba(fp, y, groups, "logreg")
        from sklearn.metrics import roc_auc_score
        self.assertLess(roc_auc_score(y, p), 0.65)


if __name__ == "__main__":
    unittest.main()
