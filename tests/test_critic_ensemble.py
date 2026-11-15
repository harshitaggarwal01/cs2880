"""Run: python -m unittest tests.test_critic_ensemble -v   (offline)"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import critic_ensemble as ce  # noqa: E402


class DawidSkene(unittest.TestCase):
    def test_recovers_planted_accuracies(self):
        ids, critics, V, labels, truth = ce.synthetic(n=4000, seed=1)
        res = ce.dawid_skene(V)
        est = ce.estimated_rates(res)
        np.testing.assert_allclose(est["est_accuracy"], truth["accuracy"], atol=0.04)
        np.testing.assert_allclose(est["est_sensitivity"], truth["sens"], atol=0.06)
        self.assertAlmostEqual(res["pi"][1], truth["prevalence"], delta=0.04)

    def test_posterior_beats_majority_vote_when_one_critic_is_much_better(self):
        ids, critics, V, labels, _ = ce.synthetic(n=3000, seed=2)
        res = ce.dawid_skene(V)
        y = 1 - labels["SAFE"].to_numpy()
        a_post, a_mv = ce.auc(res["posterior"], y), ce.auc(ce.majority_share(V), y)
        self.assertGreater(a_post, a_mv + 0.02)
        tab = ce.validate(ids, critics, V, res, labels)
        self.assertEqual(set(tab["kind"]), {"critic", "posterior", "majority_vote", "best_single_critic"})
        self.assertLess(tab[tab["kind"] == "critic"]["accuracy_gap"].abs().max(), 0.05)

    def test_three_way_and_missing_verdicts(self):
        ids, critics, V, labels, truth = ce.synthetic(n=3000, three_way=True, seed=3)
        self.assertEqual(set(np.unique(V)), {0, 1, 2})
        V2 = V.copy()
        V2[np.random.default_rng(0).random(V.shape) < 0.2] = -1  # critics skip 20% of outputs
        V2[:, 0] = np.where(np.random.default_rng(1).random(len(V)) < 0.05, V2[:, 0], V[:, 0])
        res = ce.dawid_skene(V2, n_cats=3)
        self.assertEqual(res["confusion"].shape, (5, 2, 3))
        np.testing.assert_allclose(res["confusion"].sum(axis=2), 1.0)
        np.testing.assert_allclose(ce.estimated_rates(res)["est_accuracy"], truth["accuracy"], atol=0.06)
        self.assertGreater(res["posterior"][labels["SAFE"].to_numpy() == 0].mean(), 0.7)  # oriented: class 1 = UNSAFE

    def test_downstream_columns(self):
        ids, critics, V, labels, _ = ce.synthetic(n=800, seed=4)
        res, table, post = ce.analyse(ids, critics, V, labels, restarts=3)
        self.assertEqual(list(post.columns), ["output_id", "posterior_unsafe", "majority_unsafe_share", "n_critics"])
        f = ce.ppi_predictor(post)
        self.assertEqual(set(f.unique()) <= {0, 1}, True)
        data = ce.attach_posterior_scores(labels, post)
        cur = ce.conformal_curve(data, alphas=(0.1,), n_splits=5)
        self.assertEqual(len(cur), 1)
        self.assertLessEqual(cur["realized_unsafe_pass"].iloc[0], 0.15)

    def test_cli_synthetic_writes_csv(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            out = subprocess.run([sys.executable, str(ROOT / "src" / "critic_ensemble.py"), "--synthetic",
                                  "--out-dir", tmp], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue((Path(tmp) / "critic_ensemble.csv").exists())
            self.assertIn("posterior", out.stdout)


if __name__ == "__main__":
    unittest.main()
