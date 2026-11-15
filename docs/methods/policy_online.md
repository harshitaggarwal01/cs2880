# Module 2D-b: online contextual bandit, off-policy evaluation and feedback logging (`src/policy_online.py`)

## Why

`policy.py` learns a rewrite-arm policy offline from a full-information label table. A real tool would instead choose an arm per problem, see only that arm's outcome, and learn as teachers give feedback. This module simulates that deployment on our table (a **policy simulation**, not a deployment), estimates the value of new policies from logs where only the chosen arm is seen, and provides a logger for the demo's thumbs feedback.

## Method

**Arms, context, reward** are imported from `policy.py`: the deterministic split, generator x {plain, chunked}, repair variants; the seven surface tags plus step, length and quantity buckets; reward = SAFE_AND_USEFUL − λ·USD. A *cell* is a combination of context columns (default `step_bucket`) or a leaf of a depth-≤2 tree fit on earlier data (`tree_cells`).

**Learners** (bandit feedback only):
- *Thompson sampling*: Beta-Bernoulli per cell and arm (Agrawal & Goyal, 2013; Chapelle & Li, 2011; Russo et al., 2018). Rewards are rescaled to [0, 1] so λ > 0 is allowed.
- *LinUCB*, disjoint: one ridge regression per arm on the one-hot context, optimism bonus α·sqrt(xᵀA⁻¹x) (Li et al., 2010).
- *ε-greedy* per cell (ε = 0.1) and a *uniform* random arm as baselines.

**Replay simulator.** Every problem has an outcome for every arm, so sources are replayed in random arrival orders (default 100) and each learner sees only its chosen arm. We report cumulative regret against the best fixed arm in hindsight and against the per-source oracle, as the mean and 2.5/97.5 percentiles over orders at t = 25, 50, 100, 200 and the horizon.

**Off-policy evaluation** for logs with stored propensities π₀(a|x) > 0, target policy π:
- IPS: mean of w·r with w = π(a|x)/π₀(a|x);
- SNIPS: Σw·r / Σw (Swaminathan & Joachims, 2015), lower variance, small bias;
- doubly robust: mean of q̂(x,π) + w·(r − q̂(x,a)) with q̂ the per-cell per-arm mean of logged rewards (Dudík, Langford & Li, 2011).
`check_ope` simulates an ε-greedy logging policy on the full table, hides non-chosen arms, and compares each estimator with the exact value for a greedy-per-cell and a uniform target. `ope_with_ci` adds source-clustered bootstrap CIs (`evaluate.cluster_boot`).

**Feedback logger.** `log_feedback(path, record)` appends JSONL with timestamp, source_id, arm, propensity, reward and/or thumbs; `load_feedback` reads it back and maps thumbs to a 0/1 reward. The demo (`demo/app.py`) has an optional thumbs widget writing to `data/feedback/feedback.jsonl` (gitignored). Because the user, not a randomised policy, picks the arm shown, the demo stores `propensity = null`; those rows can feed the online learner as rewards but not IPS-type estimates. A live deployment must randomise the arm and store its propensity.

## What we report

`analysis/policy_online.csv`: regret table per algorithm and checkpoint. `analysis/policy_online_ope.csv`: estimator, estimate, truth, error for each target. Run `python src/policy_online.py --run data/outputs/main-v1` or `--synthetic`.

## Caveats

- Replay uses one fixed label per (source, arm), so there is no outcome noise across repeats and no drift, delay or teacher-preference effects.
- With ~124 sources a learner has little time to learn: regret against the oracle stays large, and regret against the best fixed arm can be negative or positive within noise. Regret against the oracle includes the part of the outcome noise no context can predict.
- IPS has high variance when the target plays arms the logging policy rarely plays; SNIPS/DR are less affected but not free of bias. The per-cell mean DR model is crude.
- Thumbs from one demo user are not the study's rubric label; do not mix them with adjudicated outcomes.
- Restless bandits and mechanism design were considered and not pursued (decisions about problems, not people over time; no strategic behaviour).

## References

- Li, L., Chu, W., Langford, J. & Schapire, R. (2010). A contextual-bandit approach to personalized news article recommendation. WWW.
- Agrawal, S. & Goyal, N. (2013). Further optimal regret bounds for Thompson sampling. AISTATS.
- Chapelle, O. & Li, L. (2011). An empirical evaluation of Thompson sampling. NeurIPS.
- Dudík, M., Langford, J. & Li, L. (2011). Doubly robust policy evaluation and learning. ICML.
- Swaminathan, A. & Joachims, T. (2015). The self-normalized estimator for counterfactual learning. NeurIPS.
- Russo, D., Van Roy, B., Kazerouni, A., Osband, I. & Wen, Z. (2018). A tutorial on Thompson sampling. Foundations and Trends in Machine Learning.
