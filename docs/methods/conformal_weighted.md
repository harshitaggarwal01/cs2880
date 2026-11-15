# Weighted conformal under covariate shift (`src/conformal.py`, opt-in)

**Question.** The PASS threshold is calibrated on the study's outputs. Can the same guarantee transfer to an external
tool's outputs, whose problems and rewrites look different (longer, different transformation mix, harder sources)?
If the shift is only in the inputs (covariate shift: P(unsafe | x) is the same, the mix of x differs), reweighting the
calibration data by the density ratio restores validity (Tibshirani, Foygel Barber, Candes and Ramdas, 2019). **Nothing
changes by default**: no existing function or result is touched; the functions below are called only on request.

**Pieces.**
- `density_ratio_weights(X_study, X_new, clip=20)`: logistic classifier of new-tool (1) vs study (0) on features that are
  observable for unlabelled new-tool outputs. w(x) = P(new|x)/P(study|x) * n_study/n_new, clipped at `clip`.
  `effective_sample_size(w)` is the Kish ESS, the diagnostic to report.
- `weighted_crc_threshold(scores, losses, alpha, weights, w_test=None)`: the largest lambda with
  (sum_i w_i L_i(lambda) + B w_test) / (sum_i w_i + w_test) <= alpha. The test weight is unknown, so by default it is the
  largest calibration weight (conservative; clipping bounds it). With all weights 1 this is exactly `crc_threshold`
  (tested). With source groups, a group's loss is its weight-averaged loss and its weight the mean weight.
- `guarantee_curve_weighted(data, weights, ..., target=None)`: repeated source-level splits as in `guarantee_curve`;
  per alpha, the weighted threshold and, side by side, the plain CRC threshold from the same split, both evaluated on the
  new-tool `target` frame if you have labels there, else importance-weighted on the study test half.
- `synthetic_shift` and `python src/conformal.py --shift-demo`: planted shift, where the unweighted threshold over-passes
  on the shifted set and the weighted one keeps the unsafe-and-passed share near alpha.

**Limitations (read before quoting; get a stronger-model statistical review).**
- The guarantee needs the true density ratio and shared P(unsafe | x). Estimated, clipped weights make it approximate:
  in the planted-shift tests the realized risk is near, not exactly at or below, alpha. Label shift (the new tool is simply
  more often unsafe for the same x) is NOT covered.
- A large ratio shrinks the ESS; with an ESS of tens of items the weighted rule will usually pass nothing. That is the
  correct, conservative answer.
- The features must separate the tools only through x; including anything affected by the label breaks the assumption.
- Only CRC is weighted. Learn-then-Test would need a weighted binomial test and is not provided.
- Weights are estimated once and held fixed across splits; the splits do not account for that estimation error.
- The guarantee is marginal over the new tool's input distribution, not per problem type.

**References.**
- Tibshirani, Foygel Barber, Candes, Ramdas (2019). Conformal prediction under covariate shift. *NeurIPS*.
- Angelopoulos, Bates, Fisch, Lei, Schuster (2024). Conformal Risk Control. *ICLR*.
- Sugiyama, Suzuki, Kanamori (2012). *Density Ratio Estimation in Machine Learning.* Cambridge University Press.
