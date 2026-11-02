# Risk-controlled PASS (`src/conformal.py`)

## What we claim, in plain words

Pick a tolerance alpha (say 5%). From a set of human-labelled examples we choose a PASS threshold so that, on new problems from the same population, the rewrites we PASS are unsafe at most alpha of the time. Everything above the threshold goes to human review. The guarantee is finite-sample: it needs no model of how the verifier scores relate to harm. It comes in two forms.

- **Conformal Risk Control (CRC), marginal.** The expected share of *all* new rewrites that are both unsafe and passed is at most alpha.
- **Learn-then-Test (LTT), conditional.** With probability at least 1 - delta over the calibration sample, P(unsafe | PASS) <= alpha. This is the form that matches the sentence "of what we pass, at most alpha is unsafe".

CRC's quantity is the pass rate times the conditional rate, so it is the weaker of the two. It does not by itself bound the unsafe share among passed items (on the synthetic data it sits near 0.11 when alpha = 0.10). For the headline claim, quote LTT.

## The rule

Each verify row gets an ordinal risk score: 5 if any deterministic REJECT flag, else 4 if the critic says UNSAFE, else 3 if the program check mismatches, else 2 if the critic is missing, errored or UNSURE or the program is uncheckable, else 1 if any flag, else 0; plus 0.1 per deterministic flag (capped at 9). More evidence never lowers the score. PASS iff score <= lambda.

- **CRC.** Loss for an item is `unsafe * 1[score <= lambda]`, which is non-decreasing in lambda. Choose the largest lambda on the observed scores with `n/(n+1) * mean loss + B/(n+1) <= alpha` (B = 1). The unit is the source: a source's loss is the mean over its items and n counts sources.
- **LTT.** Walk the observed scores from strictest to most lenient. At each, test "risk > alpha" with the exact binomial p-value P(Binom(m, alpha) <= k) (m passed, k unsafe). Stop at the first p-value above delta (default 0.1) and return the previous lambda. Fixed-sequence testing controls the family-wise error rate at delta without a multiplicity correction. It needs only that the order is fixed before labels are seen; the conditional risk does not have to be monotone in lambda (it usually is not). The strict-to-lenient order is chosen for power. The cluster version treats each source's pass-set as one trial ("contains an unsafe item"), which is conservative.
- If no lambda qualifies the threshold is -inf and nothing is passed.

## Assumptions

1. **Exchangeability at the source level.** New sources behave like the calibration sources. Items from one source are correlated, so splits, losses and trials are all by `source_id`.
2. **Human labels.** Calibration labels are the adjudicated human labels, treated as ground truth. Label noise shifts the guarantee to the noisy target.
3. **No distribution shift.** A new problem type, grade band, generator or prompt breaks assumption 1. Recalibrate on labelled examples of the new setting before reusing a threshold.
4. The verifier and the score are frozen before calibration; changing either requires fresh labels.

## What we report

`analysis/conformal.csv`: for alpha in {0.02, 0.05, 0.10, 0.20} and each method, 200 random 50/50 source-level splits. Per alpha: mean lambda, review rate (share not passed) with its 2.5/97.5 percentiles over splits, realized unsafe-among-passed rate (`realized_risk_*`), the CRC quantity (`realized_unsafe_pass_*`), and the fraction of splits at or below alpha. `--by transformation` gives the same per condition, with thresholds calibrated on the pooled half; these rows are descriptive only (the guarantee is for the pooled population, not within each condition). The curve (alpha against review rate) is the cost of a stricter promise.

## Limitations

- The guarantee holds on average over calibration draws; a single calibration set can miss. LTT's delta says how often.
- With few labelled sources, tight alpha cannot be certified: CRC's `B/(n+1)` term and LTT's binomial test push towards "pass nothing" (on the synthetic data, alpha = 0.02 with 60 calibration sources passes almost nothing, and LTT passes little at alpha <= 0.10). Report the whole curve; quote the LTT row for the headline claim.
- Realized risk on test halves is noisy; report the interval, not the mean alone. Rates with no PASSed items count as 0 risk.
- Per-condition numbers are not separately guaranteed; the guarantee is for the pooled population.
- The score is coarse (many ties), so the achievable thresholds are few.

## References

- Angelopoulos, Bates, Fisch, Lei, Schuster (2024). Conformal Risk Control. ICLR.
- Angelopoulos, Bates, Candes, Jordan, Lei (2021). Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control. arXiv:2110.01052.
- Bates, Angelopoulos, Lei, Malik, Jordan (2021). Distribution-free, risk-controlling prediction sets. JACM 68(6).
- Vovk, Gammerman, Shafer (2005). Algorithmic Learning in a Random World. Springer.
