# 2C — Prediction-powered inference for failure rates

`src/ppi.py` · tests `tests/test_ppi.py` · outputs `analysis/ppi.csv`, `analysis/ppi_budget.csv`

## Why

Human labels are the bottleneck: each adjudicated SAFE/UNSAFE label costs two annotators and a tie-break, so the conditions, external tools and extra sources we can report rates for are bounded by annotation time, not API budget. The verifier runs on everything for cents, but its flags are not labels: a 15% systematic over-flag becomes a 15-point bias in the rate. Prediction-powered inference (PPI) uses the cheap predictor on *all* items and human labels on a *subset* to get an estimate that is unbiased whatever the predictor's errors, with an interval that narrows as the predictor improves.

## Estimators

`y` is the human label (UNSAFE = 1 − SAFE from `evaluate.derive`, or any binary outcome) on `n_lab` items; `f` is the predictor (verifier `decision != PASS`, or critic `overall != SAFE`, missing/errored critic counting as unsafe) on all `n_all` items, `N = n_all − n_lab` of them unlabelled.

- **Classical:** `mean(y_lab)`.
- **PPI:** `mean(f_unlab) + mean(y_lab − f_lab)`. The first term is the predictor's rate on the unlabelled items (disjoint from the labelled ones, the standard PPI split); the second, the *rectifier*, is the predictor's average error measured where it can be checked. An over-flagging predictor gets a negative rectifier that pulls the estimate back down. The rectifier comes from a random sample of the same population, so the sum is unbiased however wrong `f` is, and the interval is narrow when `y − f` varies little.
- **PPI++:** `mean(y_lab) + λ (mean(f_unlab) − mean(f_lab))`, `λ = cov(y_lab, f_lab) / (var(f_lab)(1 + n_lab/N))` clipped to [0, 1]. λ is estimated once and held fixed inside the bootstrap (asymptotically valid). `λ = 0` is classical, `λ = 1` is PPI; a useless predictor gets `λ ≈ 0`, so PPI++ is never worse than classical. With a mediocre predictor (accuracy ≈ 0.85) plain PPI can be *wider* than classical; PPI++ is the estimate to quote.

## Clustering

The five adaptations of one source share its difficulty, so the resampling unit is `source_id`, as elsewhere. Intervals are percentile bootstraps (2000 draws) over sources. When labels are assigned per source (no source has both labelled and unlabelled items), the labelled and unlabelled sources are resampled separately; otherwise the union of sources is resampled jointly, so a source's labelled and unlabelled items move together. `classical_mean` without clusters uses the normal approximation.

## What we report

- `ppi.csv` (`estimate_rates`): per transformation × generator and overall, the three estimates with 95% CIs, widths, `λ`, `n_lab`, `n_all`, and the raw predictor rate for contrast.
- `ppi_budget.csv` (`label_budget_curve`): for 20–100% of sources labelled, 200 random relabellings each: mean CI width, RMSE and coverage of the full-data mean per estimator. This is what fixes the label budget for external-tool audits (Phase 3A: ≈ 30 per tool).

`--synthetic` runs the same pipeline on planted data with a predictor of chosen accuracy and bias; the tests check unbiasedness under a 15-point bias, narrower intervals at 95% accuracy, `λ ∈ [0, 1]`, coverage near nominal against the planted super-population rate (0.88–0.995; PPI ≈ 0.95 at 30% labelled), and that with everything labelled all three estimators equal the classical one.

## Caveats

- The predictor must be computed identically on labelled and unlabelled items (same verifier version, layers, prompts); otherwise the rectifier corrects the wrong error.
- The labelled subset must be a random or stratified-random sample of the same population. Our 30% double-annotation subset is stratified random by condition and qualifies; the A-labelled set is complete, so on the main study PPI is a check. It matters for external tools and extra conditions, where only a small random subset gets labels.
- With everything labelled (`N = 0`) PPI and PPI++ return the classical estimate. On the main study annotator A labels every item, so PPI there is the classical rate; the method pays off on the budget curve, external tools and extra conditions.
- Coverage in the budget curve is against the finite full-data mean, with no finite-population correction, hence conservative at large fractions.
- *Revision 2026-11-02:* an earlier version averaged `f` over all items (labelled included) while bootstrapping the two sets independently. That ignored their covariance, over-covered (0.995–1.0 on synthetic data) and did not reduce to classical at 100% labelled. Fixed as above.

## References

- Angelopoulos, A. N., Bates, S., Fannjiang, C., Jordan, M. I. & Zrnic, T. (2023). Prediction-powered inference. *Science* 382(6671), 669–674.
- Angelopoulos, A. N., Duchi, J. C. & Zrnic, T. (2023). PPI++: Efficient prediction-powered inference. arXiv:2311.01453.
- Zrnic, T. & Candès, E. J. (2024). Cross-prediction-powered inference. *PNAS* 121(15), e2322083121.
