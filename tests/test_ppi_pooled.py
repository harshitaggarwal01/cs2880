import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ppi_pooled import pooled_rates  # noqa: E402


def _data(seed=0, frac_a=1.0, frac_b=0.2, n=400):
    """Two strata with different unsafe rates (0.8 vs 0.1) and different labelled fractions."""
    rng = np.random.default_rng(seed)
    rows = []
    for g, p, frac in (("a", 0.8, frac_a), ("b", 0.1, frac_b)):
        for i in range(n):
            y = float(rng.random() < p)
            rows.append({"transformation": g, "generator": "x", "source_id": f"s{i % 100}", "UNSAFE": y,
                         "f": y if rng.random() < 0.8 else 1 - y, "lab": rng.random() < frac})
    df = pd.DataFrame(rows)
    return df, df.pop("lab").to_numpy()


class PooledTest(unittest.TestCase):
    def test_weighted_recovers_population_rate(self):
        df, mask = _data()
        res, dropped = pooled_rates(df, mask, n_boot=400)
        truth = df["UNSAFE"].mean()
        naive = df.loc[mask, "UNSAFE"].mean()          # the invalid unweighted pooled estimate
        cl = res.set_index("estimator").loc["classical"]
        self.assertFalse(dropped)
        self.assertLess(abs(cl.estimate - truth), abs(naive - truth))
        self.assertLessEqual(cl.lo, cl.estimate)
        self.assertGreaterEqual(cl.hi, cl.estimate)

    def test_equal_fractions_classical_equals_stratum_mean(self):
        df, mask = _data(frac_a=1.0, frac_b=1.0)
        res, _ = pooled_rates(df, mask, n_boot=50)
        expected = df.groupby("transformation")["UNSAFE"].mean().mean()   # equal N_h -> simple average
        self.assertAlmostEqual(res.set_index("estimator").loc["classical", "estimate"], expected)

    def test_small_strata_dropped(self):
        df, mask = _data()
        extra = pd.DataFrame([{"transformation": "c", "generator": "x", "source_id": "s1", "UNSAFE": 1.0, "f": 1.0}])
        res, dropped = pooled_rates(pd.concat([df, extra], ignore_index=True), np.r_[mask, True], n_boot=50)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(int(res.n_strata.iloc[0]), 2)


if __name__ == "__main__":
    unittest.main()
