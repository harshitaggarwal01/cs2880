# Distilled free layer (Phase 3D)

**Purpose.** The critic is the expensive part of the verifier. This stretch analysis asks how much of its recall of
UNSAFE adaptations a free layer can recover: a small classifier that learns from the deterministic layer's own
evidence which of its flags, and which combinations, actually predict a human UNSAFE label. It is distillation in the
loose sense of Hinton, Vinyals and Dean (2015, arXiv:1503.02531), with human labels as the target rather than the
critic's soft outputs, and it follows the rule-then-judge pattern of Zhao, Knezevic and Kaser (2026, ACL): cheap rules
first, an expensive judge only where needed.

**Features** (`src/distill.py: features`). One-hot of the 14 deterministic flag codes (fixed vocabulary), number of
flags, number of REJECT flags, candidate minus source Flesch-Kincaid grade, candidate/source word ratio, longest
sentence, and source length. Critic fields (overall verdict, failure-code one-hots, math/leakage flags) are added only
with `use_critic=True`, which is no longer a free layer and serves as the upper reference.

**Evaluation at a matched review rate.** Two reference points come from the stored rows: det-only REJECT and det-only
ANY (REJECT or REVIEW). The classifier, logistic regression or shallow gradient boosting, produces out-of-fold
probabilities; the top-scoring items are flagged so that the flag rate equals each reference rate exactly. We report
recall of UNSAFE, precision and AUPRC, and the recall difference to the det-only point. Matching the rate means the
classifier cannot win by sending more items to review.

**Leave-source-out.** Folds are `GroupKFold(5)` on `source_id`, so no source contributes to both training and
scoring, matching the source-clustered resampling used elsewhere.

**Limitations.**
- Small n: a few hundred labelled items with few UNSAFE cases; recall differences of a few points are within noise
  and no confidence interval is reported yet.
- The features are the deterministic layer's own output. The classifier can re-weight and combine that evidence but
  cannot see anything the checks do not already measure; semantic errors the critic catches stay out of reach.
- Labels come from the same annotation protocol as the rest of the study, and the models are tuned on nothing but
  defaults; any hyperparameter search would need nested leave-source-out.
- Synthetic data (`--synthetic`) has planted structure and only tests the plumbing, not the real gain.

Usage: `python src/distill.py --run data/outputs/main-v1` or `python src/distill.py --synthetic`.
