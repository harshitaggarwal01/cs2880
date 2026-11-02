# 2C — Prediction-powered inference for failure rates

`src/ppi.py` · tests in `tests/test_ppi.py` · outputs `analysis/ppi.csv`, `analysis/ppi_budget.csv`

## Why

Human labels are the bottleneck of this study: every adjudicated UNSAFE/SAFE label costs two annotators and a tie-break, so the number of conditions, external tools and extra sources we can report rates for is bounded by annotation time, not by API budget. The verifier, on the other hand, runs on everything for cents. Treating verifier flags as if they were labels is not an option: a 15% systematic over-flag turns into a 15-point bias in the reported rate. Prediction-powered inference (PPI) uses the cheap predictor on *all* items and the human labels on a *subset* to get an estimate that is unbiased whatever the predictor's errors, with an interval that narrows as the predictor gets better.

## Estimators

Let `y` be the human label (UNSAFE = 1 − SAFE from `evaluate.derive`, or any binary outcome), known on `n_lab` labelled items, and `f` the predictor (verifier `decision != PASS`, or critic `overall != SAFE`; a missing or errored critic counts as unsafe), known on all `n_all` items.

- **Classical:** `mean(y_lab)`. Ignores the predictor.
- **PPI:** `mean(f_all) + mean(y_lab − f_lab)`. The first term is the predictor's rate on everything; the second, the *rectifier*, is the predictor's average error measured where we can check it. Over-flagging makes the rectifier negative and pulls the estimate back down. Because the rectifier is estimated on a random sample of the same population, the sum is unbiased for the true rate no matter how wrong `f` is; the interval is narrow when `y − f` varies little, i.e. when the predictor is accurate.
- **PPI++:** `mean(y_lab) + λ · (mean(f_all) − mean(f_lab))` with `λ = cov(y_lab, f_lab) / (var(f_lab) · (1 + n_lab/n_all))`, clipped to [0, 1]. `λ = 0` is the classical estimate, `λ = 1` is PPI. A useless predictor gets `λ ≈ 0`, so PPI++ is never worse than classical; a strong one gets `λ` near 1. With a mediocre predictor (accuracy ≈ 0.85) plain PPI can actually be *wider* than classical because `y − f` is as noisy as `y`; PPI++ is the estimator to quote.

## Clustering

All five adaptations of one source problem share its difficulty, so the resampling unit is `source_id`, as everywhere else in the analysis. Intervals are percentile bootstraps (default 2000 draws) over sources, resampling the labelled set and the full set independently. `classical_mean` without clusters falls back to the normal approximation. Bootstrap percentiles are not clipped to [0, 1].

## What we report

- `analysis/ppi.csv` (`estimate_rates`): per transformation × generator and overall, the three estimates with 95% CIs, widths, `λ`, `n_lab`, `n_all`, and the raw predictor rate `f_rate_all` for contrast.
- `analysis/ppi_budget.csv` (`label_budget_curve`): for labelled fractions 20–100% of sources, 200 random relabellings each: mean CI width, RMSE and coverage of the full-data mean for each estimator. This is the chart that says how many labels an external-tool audit needs (Phase 3A targets ≈ 30 per tool).

`python src/ppi.py --synthetic` runs the same pipeline on planted data with a predictor of chosen accuracy and bias (`synthetic`), which is what the tests use: PPI is unbiased under a 15-point predictor bias, narrower than classical at 95% accuracy, `λ` stays in [0, 1], and coverage is at or above nominal.

## Caveats

- The predictor must be computed *identically* on labelled and unlabelled items (same verifier version, layers and prompts); otherwise the rectifier corrects the wrong error.
- The labelled subset must be a random or stratified-random sample of the same population as the unlabelled items. Our 30% double-annotation subset is stratified random by condition, so it qualifies; the A-labelled set is complete, so on the main study PPI mostly serves as a check. It matters for external-tool audits and extra conditions, where only a small random subset gets labels.
- Here the labelled items are included in `f_all`; the bootstrap resamples the two sets independently, which ignores the small covariance this creates. With a ≤ 30% labelled fraction the effect on interval width is negligible.
- The budget curve measures coverage of the *finite* full-data mean, so it is conservative (coverage above nominal) at large fractions.

## References

- Angelopoulos, A. N., Bates, S., Fannjiang, C., Jordan, M. I. & Zrnic, T. (2023). Prediction-powered inference. *Science* 382(6671), 669–674.
- Angelopoulos, A. N., Duchi, J. C. & Zrnic, T. (2023). PPI++: Efficient prediction-powered inference. arXiv:2311.01453.
- Zrnic, T. & Candès, E. J. (2024). Cross-prediction-powered inference. *PNAS* 121(15), e2322083121.
