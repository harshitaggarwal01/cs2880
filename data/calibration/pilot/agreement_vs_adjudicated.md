# Calibration agreement against the owner-adjudicated labels (2026-11-20)

Final labels: `adjudicated.csv` after the owner review (`owner_review_2026-11-20.csv`: 16 ACCEPT, 14 OVERRIDE of the 2026-11-19 AI adjudications). A vs B (before adjudication) is unchanged: `agreement_A_vs_B.md`.

## adjudicated vs sheet_A

| label                  |   n |   raw_agreement |   kappa | kappa_weighting   |   gwet_ac1 |
|:-----------------------|----:|----------------:|--------:|:------------------|-----------:|
| math_fidelity          |  70 |           1.000 |   1.000 | none              |      1.000 |
| target_preserved       |  70 |           1.000 |   1.000 | none              |      1.000 |
| ambiguity              |  70 |           1.000 |   1.000 | none              |      1.000 |
| leakage_level          |  70 |           1.000 |   1.000 | quadratic         |      1.000 |
| presentation           |  65 |           0.923 |   0.877 | quadratic         |      0.897 |
| SAFE                   |  70 |           1.000 |   1.000 | none              |      1.000 |
| adaptation_needed      |  70 |           0.943 |   0.574 | none              |      0.934 |
| solvability_changed    |  70 |           1.000 |   1.000 | none              |      1.000 |
| leakage_type           |  70 |           1.000 |   1.000 | none              |      1.000 |
| abstention_appropriate |   5 |           1.000 |   1.000 | none              |      1.000 |
| failure_codes          |  23 |           0.739 |   0.721 | none              |      0.727 |

## adjudicated vs sheet_B

| label                  |   n |   raw_agreement |   kappa | kappa_weighting   |   gwet_ac1 |
|:-----------------------|----:|----------------:|--------:|:------------------|-----------:|
| math_fidelity          |  70 |           0.900 |   0.000 | none              |      0.895 |
| target_preserved       |  70 |           0.986 |   0.000 | none              |      0.986 |
| ambiguity              |  70 |           0.943 |   0.616 | none              |      0.938 |
| leakage_level          |  70 |           0.971 |   0.950 | quadratic         |      0.968 |
| presentation           |  65 |           0.738 |   0.636 | quadratic         |      0.633 |
| SAFE                   |  70 |           0.929 |   0.794 | none              |      0.891 |
| adaptation_needed      |  70 |           0.700 |   0.286 | none              |      0.520 |
| solvability_changed    |  70 |           0.900 |   0.000 | none              |      0.895 |
| leakage_type           |  70 |           0.971 |   0.915 | none              |      0.969 |
| abstention_appropriate |   5 |           0.800 |   0.545 | none              |      0.655 |
| failure_codes          |  23 |           0.609 |   0.556 | none              |      0.588 |

## adjudicated vs standin/adjudicated

| label                  |   n |   raw_agreement |   kappa | kappa_weighting   |   gwet_ac1 |
|:-----------------------|----:|----------------:|--------:|:------------------|-----------:|
| math_fidelity          |  70 |           0.900 |   0.194 | none              |      0.893 |
| target_preserved       |  70 |           0.986 |   0.000 | none              |      0.986 |
| ambiguity              |  70 |           0.914 |   0.236 | none              |      0.909 |
| leakage_level          |  70 |           0.957 |   0.941 | quadratic         |      0.952 |
| presentation           |  65 |           0.677 |   0.528 | quadratic         |      0.568 |
| SAFE                   |  70 |           0.929 |   0.794 | none              |      0.891 |
| adaptation_needed      |  70 |           0.900 |   0.533 | none              |      0.873 |
| solvability_changed    |  70 |           0.900 |   0.000 | none              |      0.895 |
| leakage_type           |  70 |           0.957 |   0.873 | none              |      0.954 |
| abstention_appropriate |   5 |           0.600 |   0.000 | none              |      0.412 |
| failure_codes          |  14 |           0.143 |   0.134 | none              |      0.093 |
