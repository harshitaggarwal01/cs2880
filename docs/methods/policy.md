# Module 2D: offline contextual-bandit policy (`src/policy.py`)

## The decision problem

For each source problem we must choose one adaptation arm: the deterministic chunking baseline, or an LLM generator with `plain` or `chunked` output, optionally followed by one repair. The reward for source *s* and arm *a* is

r(s, a) = SAFE_AND_USEFUL(s, a) − λ · USD(s, a),

where USD is the item's summed ledger cost (a repair arm pays for the original and the repair; missing costs count as 0). A repair arm takes the repaired item's outcome when a repair exists and the original's otherwise. The context is cheap to compute before any LLM call: the seven surface tags, a step bucket ("unknown" when `n_steps` is missing), a length tercile in words, and a bucket for the number of quantities.

## Why offline evaluation is exact here

Logged-bandit evaluation usually needs importance weighting or a reward model, because only the chosen arm is seen (Li, Chu, Langford & Schapire, 2010; Dudík, Langford & Li, 2011). Our logs are full-information: every arm was labelled on every source. The value of any policy is therefore the mean of the reward table at the arms it picks, with no propensities and no model. The direct method is exact, up to sampling error over sources.

## Policy class and comparators

The policy is a depth-2 decision tree (at least 8 sources per leaf) on one-hot context features. It is fit to each source's best arm, with ties going to the deterministic arm and then the cheaper one. Each leaf plays the arm with the highest mean reward among its training sources, and `Policy.describe()` prints the rules as "IF … : use …". With n = 124 sources, depth 2 is the most the data can support.

Comparators: *never-AI* (deterministic), *always-AI* (the best single LLM arm, picked on the training fold) and the best single arm overall. Selection of the tree and of both "best single" arms happens on training folds only. Evaluation is 10-fold by source, since the source is the exchangeable unit; leave-one-source-out is available with `folds=None`.

## Thompson-sampling replay

`thompson_replay` bridges to live use. Sources arrive in random order (500 orders); a Beta-Bernoulli Thompson sampler per context bucket sees only the chosen arm's reward and we track realised regret against the best fixed arm in hindsight (Agrawal & Goyal, 2013; Chapelle & Li, 2011; tutorial: Russo, Van Roy, Kazerouni, Osband & Wen, 2018). Falling regret per step means a deployment could learn the policy online. It uses SAFE_AND_USEFUL with λ = 0.

## What we report

`analysis/policy.csv`: cross-validated value of each method, paired differences (learned minus each comparator, always-AI minus never-AI), the in-sample value and the per-source oracle as references, all with 95% source-bootstrap CIs. `policy_tree.txt`: the rules fit on all sources. `policy_regret.csv`: mean and 2.5/97.5 percentile regret at t = 25, 50, 100 and all.

## Caveats

- The reward inherits the rubric: a different definition of "useful" can change the best arm.
- Costs come from one week's prices; a λ > 0 conclusion may not survive repricing.
- With 124 sources the CIs on differences will be wide, and a learned tree that matches the best single arm is the expected outcome unless the structure is strong.
- Deployment adds drift and feedback delay that the replay does not model (framing: Perrault, Fang, Sinha & Tambe, 2020).

## References

- Li, L., Chu, W., Langford, J. & Schapire, R. (2010). A contextual-bandit approach to personalized news article recommendation. WWW.
- Dudík, M., Langford, J. & Li, L. (2011). Doubly robust policy evaluation and learning. ICML.
- Agrawal, S. & Goyal, N. (2013). Further optimal regret bounds for Thompson sampling. AISTATS.
- Chapelle, O. & Li, L. (2011). An empirical evaluation of Thompson sampling. NeurIPS.
- Russo, D., Van Roy, B., Kazerouni, A., Osband, I. & Wen, Z. (2018). A tutorial on Thompson sampling. Foundations and Trends in Machine Learning.
- Perrault, A., Fang, F., Sinha, A. & Tambe, M. (2020). Artificial intelligence for social impact: learning and planning in the data-to-deployment pipeline. AI Magazine.
