# Module: Stackelberg audit game (`src/audit_game.py`)

**This is a policy simulation.** Vendors and tools do not currently respond strategically to audits, and the unsafe rates come from one study. The game shows how a fixed audit budget should be spread if some provider were careless about where it cuts corners, and what that is worth compared with simple rules.

## Why

Manual audits are expensive. A district or platform that can audit B items per period must decide which tool x condition cells to audit most. Allocating by hunch (uniform, or proportional to the observed rate) is predictable: a vendor that knows the rule can put unsafe content where coverage is thinnest. Security games (Tambe, 2011) model exactly this commitment problem.

## Method

Targets t are tool (or generator) x condition cells with an unsafe rate p_t and CI [lo_t, hi_t] (point and interval from `ppi.csv` or `evaluate` output; `build_game` accepts group/rate/lo/hi/n or the `ppipp*` columns) and a volume v_t. The defender chooses coverage c_t in [0, 1] with Σ c_t v_t ≤ B (or Σ c_t ≤ B in "targets" mode). An audit catches an unsafe item with probability `detect` (default 1). Unsafe items reaching students at t: L_t = v_t p_t (1 − detect·c_t). The attacker picks a target and gains g_t·L_t; the defender loses h_t·L_t (harm weights, default 1, so the game is zero-sum).

- **Strong Stackelberg Equilibrium**: the defender commits to c, the attacker best-responds, ties go to the defender. Solved by the multiple-LPs method (Conitzer & Sandholm, 2006): for each attacker target k, an LP maximises the defender's utility subject to k being a best response; the best feasible LP wins (`scipy.optimize.linprog`, HiGHS). The compact coverage-vector form follows Kiekintveld et al. (2009).
- **Robust variant**: max-min over the box of rates [lo, hi] (interval uncertainty as in Kiekintveld, Islam & Kreinovich, 2013): minimise z subject to h_t v_t hi_t (1 − detect·c_t) ≤ z for all t, which is the worst case over both the attacker's target and the rate in the box.
- **Baselines at the same budget**: uniform coverage; coverage proportional to the rate (capped at 1, scale found by bisection).

Closed form used in the tests (zero-sum, detect = 1, a_t = v_t p_t): the equilibrium equalises a_t(1 − c_t) = L across covered targets with L = (T − B)/Σ(1/a_t); when a target's a_t is below L it is left uncovered.

## What we report

`analysis/audit_game.csv`: for budgets 0, 5, 10, 20, 40 and 100% of full coverage and each method (SSE, robust, uniform, proportional): the attacked target, expected unsafe items reaching students per 1,000 (1000·L at the attacked target / total volume) at the attacker's best response under the point rates, and the worst case over every target at the CI upper bounds. The CLI also prints the coverage table at the chosen budget.

## Caveats

- Policy simulation only; no evidence that vendors behave this way. The attacker model (one target, full knowledge of c) is a worst-case idealisation.
- Rates inherit the study's labels and the sampling error in the CI; the robust variant uses the CI upper bound for every target at once, which is conservative (a Bertsimas-Sim style budget of uncertainty would be less so).
- No audit costs beyond the budget, no punishment of vendors (see Blocki et al., 2013, for audit games with penalties), no learning over repeated periods, and a perfect auditor unless `detect` < 1.
- Volumes are the study's item counts unless the user supplies real deployment volumes.

## References

- Tambe, M. (2011). Security and Game Theory: Algorithms, Deployed Systems, Lessons Learned. Cambridge University Press.
- Kiekintveld, C., Jain, M., Tsai, J., Pita, J., Ordóñez, F. & Tambe, M. (2009). Computing optimal randomized resource allocations for massive security games. AAMAS.
- Conitzer, V. & Sandholm, T. (2006). Computing the optimal strategy to commit to. ACM EC.
- Blocki, J., Christin, N., Datta, A., Procaccia, A. & Sinha, A. (2013). Audit games. IJCAI.
- Kiekintveld, C., Islam, T. & Kreinovich, V. (2013). Security games with interval uncertainty. AAMAS.
