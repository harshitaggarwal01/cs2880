# Generator × critic matrix and self-preference

`src/critic_matrix.py` · `make critic-matrix CFG=config.matrix.yaml RUN=data/outputs/matrix-v1` · synthetic check: `python src/critic_matrix.py --synthetic`

**Status.** Additional analysis, clearly labelled. The prespecified Phase-1 analysis still uses the **primary critic** (`primary_critic:` in the config; Opus 5.5), which alone drives decisions, repair and the main tables.

## Why
1. **Rewriter side.** Does a free open-weight model that a school could self-host (Qwen3.8-27B, Apache-2.0) produce more unsafe rewrites than paid frontier models?
2. **Checker side.** Can a cheap critic replace or pre-filter the expensive one? This feeds the cost story and the cascade.
3. **Same-family bias, measured.** With critics from several families judging rewriters from several families, the self-preference bias (Panickssery, Bowman & Feng 2024) becomes an estimate, not only a disclosure.

## Design
- Human labels attach to rewrites, so **every critic is scored against the same adjudicated labels**. An extra critic costs only API dollars.
- Each extra *rewriter* adds about 348 outputs to label (124 × 2 styles + 100 realistic), or a stratified 50% + PPI (`src/ppi.py`).
- `verify.py --all-critics` runs each critic in `critics:` on the same generations. Rules and the answer-recompute layer are identical across critics: there is one extractor, and its results are cached by text hash. Each critic writes `<gens>.verify-critic@NAME-det-program.jsonl`; the primary critic keeps the original file name, so older runs and every downstream script are unchanged. `common.primary_verify_files` keeps the other critics' files out of the prespecified analyses.

## Analyses
A critic **says SAFE** only when `overall == SAFE`. UNSURE, UNSAFE, a parse failure or no reply count as not SAFE. The positive class is human UNSAFE.

| Output | Content |
|---|---|
| `critic_matrix.csv` (kind=critic) | Per critic: recall on UNSAFE, precision, review rate (share not SAFE), false-SAFE count, USD per item (ledger, by `critic_name`), and ROC-AUC of `conformal.risk_score` built on that critic's rows. Scored twice: the critic verdict alone, and the full verifier decision with that critic. 95% CIs from a source-clustered bootstrap (`evaluate.verifier_metrics`, `cluster_boot`). |
| `critic_matrix.csv` (kind=grid) | Generator × critic: the critic's SAFE rate, its error rate against humans, and its false-SAFE rate on human-UNSAFE items. |
| `self_preference.csv` | Among human-UNSAFE items, one row per (item, critic): logit of "critic says SAFE" on `same_family` plus generator and critic fixed effects (dummies collinear with `same_family` are dropped). SEs are clustered by source. On separation or non-convergence the fit falls back to Firth with a cluster bootstrap, using exactly the rule of `evaluate.logit_unsafe`, factored out unchanged into `evaluate.fit_logit_clustered`. A positive coefficient means critics are more lenient on their own family's unsafe rewrites. It is not identified unless both families appear on both sides; the row then says so. |
| `critic_ensembles.csv` | Majority vote (ties → not SAFE); any-not-SAFE; and a cost-ordered cascade `cascade:<cheap>><expensive>`, which calls the expensive critic only when the cheap one is not SAFE and is charged accordingly. |
| `critic_pareto.csv` | `cascade.py` policies re-run for every critic option (single critics and ensembles) with that option's own critic cost, plus one global Pareto frontier over (unsafe shipped, USD, minutes), so cheap-critic options can appear on it. |

The report (`report.py`) adds a "Critic matrix (additional analysis)" section and `fig_critics.png` when `analysis/critic_matrix.csv` exists.

**Validation.** `tests/test_critic_matrix.py`. With planted self-preference (logit +2.0) the estimate is recovered (CI excludes 0). With none planted, the CI covers 0. The cascade's cost and verdict follow their definitions; majority voting is checked against the vote counts.

## Caveats
- The critics are scored on rewrites from the generators in the run only. A critic's accuracy may not transfer to other tools (see weighted conformal, Task H).
- Generator × critic cells are small. Read the grid descriptively; the inferential claim is the single `same_family` coefficient.
- The cheap-first cascade can ship items that the cheap critic wrongly calls SAFE. Its recall is the number to watch.

## References
- Panickssery, A., Bowman, S. R., & Feng, S. (2024). LLM evaluators recognize and favor their own generations. *NeurIPS 2024*.
- Zheng, L., et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. *NeurIPS 2023 Datasets and Benchmarks*.
- Verga, P., et al. (2024). Replacing judges with juries: Evaluating LLM generations with a panel of diverse models. arXiv:2404.18796.
- Firth, D. (1993). Bias reduction of maximum likelihood estimates. *Biometrika* 80(1).
