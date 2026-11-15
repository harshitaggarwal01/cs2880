# Label-free critic aggregation (`src/critic_ensemble.py`)

**Purpose.** The critic matrix (Task A2) gives every rewrite a verdict from several critics. Human labels are scarce, so
we want a combined verdict that (a) needs no labels, (b) weights critics by how reliable they appear to be, and (c) can be
plugged into the PPI and conformal machinery as a single score. Dawid and Skene (1979) EM does this.

**Model.** The human truth z in {SAFE, UNSAFE} is latent. Critic k's verdict v in {SAFE, UNSURE, UNSAFE} (or binary,
SAFE vs not SAFE) depends only on z through a confusion matrix P(v | z), independently across critics given z. EM
alternates the posterior P(z | verdicts) with updates of the class prior and the confusion matrices (with a 0.01
pseudo-count so no probability is exactly zero). Critics that did not score an output are skipped for that output.

**Details that matter.**
- *Initialisation and restarts.* Restart 0 starts from the majority-vote share; further restarts are noisy or random
  starts. The best log-likelihood is kept. EM has local optima and a label-switching symmetry.
- *Orientation.* Class 1 is the labelling in which critics flag items more often when z = 1 than z = 0, so it is UNSAFE.
- *Verdict coding.* Parse failures and missing replies count as UNSURE (binary: not SAFE), the same convention as
  `critic_matrix.says_safe`. Loading reuses `critic_matrix.critic_files` and `load_rows`.

**Outputs.** `analysis/critic_ensemble.csv`: per critic, estimated sensitivity, specificity and accuracy from the EM, and,
where human labels exist, the empirical values, the gap, and each critic's AUC. Summary rows give the AUC of the
posterior, of the majority-vote share, and of the best single critic. `critic_ensemble_posterior.csv` holds
`posterior_unsafe` per output.

**Use downstream.**
- *PPI predictor:* `ppi_predictor(post, threshold)` gives a binary f for `ppi.py`'s rectifier; any threshold is allowed
  because PPI stays unbiased whatever f is, and a better f only shrinks the interval.
- *Conformal risk score:* `attach_posterior_scores` and `conformal_curve` use the posterior as the ordinal score in CRC or
  LTT. The score is nearly continuous, so the grid of thresholds is rich; the guarantee is unchanged because it needs only
  exchangeability of calibration and test items, not a calibrated score.

**Limitations.**
- Conditional independence is the key assumption and it is likely false: critics from one family share blind spots (the
  self-preference result in `critic_matrix.md` is a direct violation). Correlated errors make the posterior over-confident
  and can make EM trust a bloc of agreeing critics. Compare the estimated accuracies with the labelled ones before trusting it.
- With few critics (two or three) the model is barely identified. Five or more helps; with two it only reproduces their
  agreement.
- A critic that is worse than chance flips under the orientation rule; check the accuracy table.
- Estimated accuracies are population-level; they say nothing about particular problem types.

**References.**
- Dawid, A. P., & Skene, A. M. (1979). Maximum likelihood estimation of observer error-rates using the EM algorithm. *Applied Statistics* 28(1), 20-28.
- Angelopoulos, Bates, Fannjiang, Jordan, Zrnic (2023). Prediction-powered inference. *Science* 382, 669-674.
- Angelopoulos, Bates, Fisch, Lei, Schuster (2024). Conformal Risk Control. *ICLR*.
