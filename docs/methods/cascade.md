# Cascade: a cost-aware checking order (`src/cascade.py`)

## Decision problem

Every rewrite must be shipped, rejected, or sent to a human. Checks differ in price: the deterministic layer is free, the LLM critic plus structured-extraction program check costs about one cent per item, and a human review costs minutes (`minutes_per_review` in the config). The question is which outcome of which stage is allowed to settle an item, so that the unsafe rewrites that reach students are few at an acceptable cost. This is the cascade idea of Viola and Jones (2001), applied to LLM calls as in FrugalGPT (Chen, Zaharia and Zou, 2023), with a human as the last, most expensive, accurate stage, as in learning to reject or defer (Madras, Pitassi and Zemel, 2018; Mozannar and Sontag, 2020).

## Policy space

Stage S1 is the deterministic check, S2 is critic plus program, S3 is the human. A policy is five switches: S1 stops and rejects on a deterministic REJECT; S1 stops and ships on a clean PASS (no flags); S2 rejects on critic UNSAFE or program MISMATCH; S2 ships on critic SAFE with program not MISMATCH and no deterministic REJECT; items S2 does not settle go to the human (otherwise they are shipped). The 2^5 combinations are deduplicated by behaviour: policies that act identically on every (deterministic, critic, program) outcome are merged, keeping the one that reaches S2 less often. Five named baselines are added: ship everything, deterministic-only (reject on REJECT, ship or send to a human for the rest), a deterministic triage, the current full verifier (`verify.decide`: REJECT rejects, REVIEW goes to a human, PASS ships), and human review of everything. Stored verifier fields are replayed offline, so there are no API calls.

## Objective and Pareto frontier

Per 100 items: `unsafe shipped + lam * USD + mu * human minutes`. We report the whole table over (unsafe shipped, USD, minutes) and mark the non-dominated policies, because lam and mu are not facts: a school that values reviewer time differently from a vendor that values API spend picks a different point. `calibrate_and_test` shows what happens when one point is chosen from data: it selects the best policy on a random half of sources and scores it on the other half, over 100 splits, with 2.5 and 97.5 percentiles. Splits are by source problem because outputs of one source are not independent.

## Assumptions

- Human review is correct: a reviewed item is never an unsafe ship or a safe reject. The adjudicated label is the truth, so human error is not modelled and the human-reliant policies are optimistic by that amount.
- Costs come from `ledger.csv` (per item critic and extract spend). Items without ledger rows get defaults (critic 1.0 cent, extract 0.8 cent). Human time is a fixed number of minutes per item.
- Unsafe counts are per 100 labelled items, so they depend on the unsafe prevalence of the set, in particular the share of naive-prompt items.
- Frontier points are estimates from one labelled sample; differences between neighbouring policies can be inside noise, which the calibrated table makes visible.

## References

- Viola, P. and Jones, M. (2001). Rapid object detection using a boosted cascade of simple features. CVPR.
- Chen, L., Zaharia, M. and Zou, J. (2023). FrugalGPT: How to use large language models while reducing cost and improving performance. arXiv:2305.05176.
- Madras, D., Pitassi, T. and Zemel, R. (2018). Predict responsibly: Improving fairness and accuracy by learning to defer. NeurIPS.
- Mozannar, H. and Sontag, D. (2020). Consistent estimators for learning to defer to an expert. ICML.
