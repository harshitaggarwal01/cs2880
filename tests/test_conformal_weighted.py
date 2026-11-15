"""Run: python -m unittest tests.test_conformal_weighted -v   (offline). Opt-in weighted conformal under covariate shift."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import conformal as cf  # noqa: E402


class WeightedConformal(unittest.TestCase):
    def test_unit_weights_equal_unweighted(self):
        rng = np.random.default_rng(0)
        scores = np.round(rng.normal(size=300), 1)
        losses = (rng.random(300) < 0.3).astype(int)
        groups = np.repeat(np.arange(100), 3)
        for g in (None, groups):
            for a in (0.02, 0.1, 0.3):
                self.assertEqual(cf.weighted_crc_threshold(scores, losses, a, np.ones(300), groups=g),
                                 cf.crc_threshold(scores, losses, a, groups=g))
        data, _ = cf.synthetic_shift(800, 10, seed=1)
        w = np.ones(len(data))
        c = cf.guarantee_curve_weighted(data, w, (0.1,), 10, target=None).set_index("variant")
        for col in ("lambda_mean", "review_rate_mean", "realized_unsafe_pass_mean"):
            self.assertAlmostEqual(c.loc["weighted", col], c.loc["unweighted", col])

    def test_weighted_controls_risk_under_shift_unweighted_does_not(self):
        study, new = cf.synthetic_shift(4000, 4000, shift=1.0, seed=3)
        w = cf.density_ratio_weights(study[["x"]], new[["x"]], clip=20)
        self.assertGreater(w[study["x"] > 1].mean(), 3 * w[study["x"] < -1].mean())  # ratio rises with x
        self.assertLess(cf.effective_sample_size(w), len(w))
        alpha = 0.10
        lam_w = cf.weighted_crc_threshold(study["score"], study["unsafe"], alpha, w)
        lam_u = cf.crc_threshold(study["score"], study["unsafe"], alpha)
        risk = lambda lam: float(((new["score"] <= lam) & (new["unsafe"] == 1)).mean())  # noqa: E731
        self.assertLessEqual(risk(lam_w), alpha + 0.01)
        self.assertGreater(risk(lam_u), alpha + 0.02)
        self.assertLess(lam_w, lam_u)  # the weighted rule is stricter

    def test_curve_prefers_weighted_on_shifted_target(self):
        study, new = cf.synthetic_shift(3000, 3000, shift=1.0, seed=4)
        w = cf.density_ratio_weights(study[["x"]], new[["x"]])
        c = cf.guarantee_curve_weighted(study, w, (0.1,), 20, target=new).set_index("variant")
        # estimated weights (ESS ~ 1/3 of n) make this approximate: allow Monte-Carlo and weight-estimation slack
        self.assertLessEqual(c.loc["weighted", "realized_unsafe_pass_mean"], 0.1 + 0.03)
        self.assertGreater(c.loc["unweighted", "realized_unsafe_pass_mean"],
                           c.loc["weighted", "realized_unsafe_pass_mean"] + 0.04)
        self.assertEqual(c.loc["weighted", "evaluated_on"], "target")
        # without a target the study test half is importance-weighted and gives the same conclusion
        c2 = cf.guarantee_curve_weighted(study, w, (0.1,), 20).set_index("variant")
        self.assertLessEqual(c2.loc["weighted", "realized_unsafe_pass_mean"], 0.1 + 0.03)
        self.assertGreater(c2.loc["unweighted", "realized_unsafe_pass_mean"], 0.1 + 0.04)

    def test_defaults_untouched(self):
        import inspect
        self.assertEqual(list(inspect.signature(cf.crc_threshold).parameters), ["scores", "losses", "alpha", "B", "groups"])
        self.assertEqual(list(inspect.signature(cf.guarantee_curve).parameters),
                         ["df", "verify_rows", "alphas", "n_splits", "method", "seed", "by", "delta", "B", "cluster"])


if __name__ == "__main__":
    unittest.main()
