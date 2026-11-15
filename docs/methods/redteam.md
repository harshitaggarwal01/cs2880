# Method 2E: red-teaming our own verifier

## Purpose

The deterministic layer catches obvious leakage: new digits, operation words, step labels, equations. A rewrite that leaks *subtly* (facts reordered into solution order, "helpful" relabeling, near-synonyms for operations, emphasis on which facts matter) could pass it. This module measures how much the verifier misses.

## Why this is not an attack on real tools

The inputs are 50 public GSM8K problems and the system under test is our own code. No deployed product is queried and no student or teacher is involved. The attacker prompt states the research framing, and outputs are never shown to learners.

## Attacker constraints

Keep every number exactly; add none. Avoid step, first, then, next, find, calculate, compute, add, subtract, multiply, divide, total, sum, equation, and all symbols and lists. Output `{"adapted_problem", "tactic"}`. With `--rounds > 1`, deterministic flags are fed back and the last attempt is kept.

## What we measure

- **Deterministic recall under attack:** the share of attack outputs the deterministic layer flags (decision other than PASS).
- **Full-verifier recall:** the share the full verifier flags (any non-PASS decision), and the share it REJECTs.
- **Human-confirmed leakage:** 30 attack outputs are mixed with 30 ordinary plain outputs in a blinded sheet (`make_blind_sheet`) and labelled with the usual rubric. Recall among confirmed-unsafe attacks (`leakage_level > 0`) is the headline figure. An attack that evades the checker but does not leak is not a miss.
- A breakdown by the attacker's self-reported tactic.

## Quarantine rule

Everything is written under `<run_dir>/redteam/`. Output IDs start with `<run_id>|redteam`, and the generator is `redteam:<model>`. Attacks never enter `generations.jsonl`, the main annotation sheets, or any main-run statistic.

## How results feed the checker

Confirmed misses are grouped by tactic. Each recurring pattern becomes a candidate cue in `deterministic_checks.py`, kept only if it raises recall without a material rise in false flags on the main labels. The attack set is then a development set; retests use fresh sources.

## Limitations

One attacker model and prompt cover part of the space. The set is small (50 attacks, 30 labelled), so intervals are wide. Tactic labels are self-reported. Attacks adapt to the deterministic layer only, not the critic. Mock runs test plumbing only.

## Iterated mode

`python src/redteam.py --config CFG --iterated --rounds K [--heldout-frac 0.3]` (`--mock` for offline plumbing). The attacked sources are split once, deterministically, into a feedback set and a **held-out set**. In round 1 every source gets the plain attacker prompt. In round k >= 2 the attacker prompt adds only the checker's verdicts from round k-1: for feedback sources, that source's own previous attempt, its verdict and a digest of round k-1 over the feedback set; for held-out sources, the digest alone. Nothing older than round k-1 is ever shown, and no verdict on a held-out attack ever enters a prompt. The checker is static across rounds (any callable can be supplied), so a rise in held-out evasion measures the attacker's adaptation, not a retuned checker. Each round's checker recall and evasion rate on the held-out attacks are written to `redteam/redteam_iterated_summary.csv`; records (with the exact attacker prompt) go to `redteam/redteam_iterated.jsonl`. Everything stays under `redteam/` (same quarantine rule, enforced by an assertion). Without `--iterated`, `--rounds` keeps its old meaning (attempts per source with deterministic-flag feedback).

Limits: held-out recall here is the deterministic layer's flag rate, not human-confirmed leakage; labelling still follows the blinded-sheet procedure. One attacker model and a small set give wide intervals. If the checker is later updated between rounds, do it only by the documented rule set and never from held-out verdicts. Reference: Perez et al. (2022), cited below, for the automated red-teaming loop.

## References

- Perez, E., et al. (2022). Red Teaming Language Models with Language Models. *EMNLP*.
- Ganguli, D., et al. (2022). Red Teaming Language Models to Reduce Harms: Methods, Scaling Behaviors, and Lessons Learned. arXiv:2209.07858.
- Zhao, Knežević & Käser (2026). Evaluating Answer Leakage Robustness of LLM Tutors. *ACL*.
