## Outcome rates (95% CI, source-clustered bootstrap)

### SAFE

| model             | transformation   |   n |   k |   rate |   ci_lo |   ci_hi |
|:------------------|:-----------------|----:|----:|-------:|--------:|--------:|
| claude-haiku-5-5  | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-haiku-5-5  | naive            |  10 |   7 |  0.700 |   0.400 |   1.000 |
| claude-haiku-5-5  | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | naive            |  10 |   0 |  0.000 |   0.000 |   0.000 |
| claude-opus-5-5   | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-sonnet-5-5 | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 | 

### SAFE_AND_USEFUL

| model             | transformation   |   n |   k |   rate |   ci_lo |   ci_hi |
|:------------------|:-----------------|----:|----:|-------:|--------:|--------:|
| claude-haiku-5-5  | chunked          |  10 |   6 |  0.600 |   0.300 |   0.900 |
| claude-haiku-5-5  | naive            |  10 |   7 |  0.700 |   0.400 |   1.000 |
| claude-haiku-5-5  | plain            |  10 |   5 |  0.500 |   0.200 |   0.800 |
| claude-opus-5-5   | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | naive            |  10 |   0 |  0.000 |   0.000 |   0.000 |
| claude-opus-5-5   | plain            |  10 |   9 |  0.900 |   0.700 |   1.000 |
| claude-sonnet-5-5 | plain            |  10 |   7 |  0.700 |   0.400 |   1.000 | 

### MATH_OK

| model             | transformation   |   n |   k |   rate |   ci_lo |   ci_hi |
|:------------------|:-----------------|----:|----:|-------:|--------:|--------:|
| claude-haiku-5-5  | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-haiku-5-5  | naive            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-haiku-5-5  | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | naive            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-sonnet-5-5 | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 | 

### NO_LEAK

| model             | transformation   |   n |   k |   rate |   ci_lo |   ci_hi |
|:------------------|:-----------------|----:|----:|-------:|--------:|--------:|
| claude-haiku-5-5  | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-haiku-5-5  | naive            |  10 |   7 |  0.700 |   0.400 |   1.000 |
| claude-haiku-5-5  | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | chunked          |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-opus-5-5   | naive            |  10 |   0 |  0.000 |   0.000 |   0.000 |
| claude-opus-5-5   | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 |
| claude-sonnet-5-5 | plain            |  10 |  10 |  1.000 |   1.000 |   1.000 | 

## Paired comparisons on SAFE (exact McNemar, Holm-adjusted)

| A                        | B                       |   n_pairs |   diff_A_minus_B |   ci_lo |   ci_hi |   A_only |   B_only |   mcnemar_p |   holm_p |
|:-------------------------|:------------------------|----------:|-----------------:|--------:|--------:|---------:|---------:|------------:|---------:|
| claude-haiku-5-5|chunked | claude-haiku-5-5|naive  |        10 |            0.300 |   0.000 |   0.600 |        3 |        0 |       0.250 |    1.000 |
| claude-haiku-5-5|chunked | claude-haiku-5-5|plain  |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-haiku-5-5|chunked | claude-opus-5-5|chunked |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-haiku-5-5|chunked | claude-opus-5-5|naive   |        10 |            1.000 |   1.000 |   1.000 |       10 |        0 |       0.002 |    0.041 |
| claude-haiku-5-5|chunked | claude-opus-5-5|plain   |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-haiku-5-5|chunked | claude-sonnet-5-5|plain |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-haiku-5-5|naive   | claude-haiku-5-5|plain  |        10 |           -0.300 |  -0.600 |   0.000 |        0 |        3 |       0.250 |    1.000 |
| claude-haiku-5-5|naive   | claude-opus-5-5|chunked |        10 |           -0.300 |  -0.600 |   0.000 |        0 |        3 |       0.250 |    1.000 |
| claude-haiku-5-5|naive   | claude-opus-5-5|naive   |        10 |            0.700 |   0.400 |   1.000 |        7 |        0 |       0.016 |    0.250 |
| claude-haiku-5-5|naive   | claude-opus-5-5|plain   |        10 |           -0.300 |  -0.600 |   0.000 |        0 |        3 |       0.250 |    1.000 |
| claude-haiku-5-5|naive   | claude-sonnet-5-5|plain |        10 |           -0.300 |  -0.600 |   0.000 |        0 |        3 |       0.250 |    1.000 |
| claude-haiku-5-5|plain   | claude-opus-5-5|chunked |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-haiku-5-5|plain   | claude-opus-5-5|naive   |        10 |            1.000 |   1.000 |   1.000 |       10 |        0 |       0.002 |    0.041 |
| claude-haiku-5-5|plain   | claude-opus-5-5|plain   |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-haiku-5-5|plain   | claude-sonnet-5-5|plain |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-opus-5-5|chunked  | claude-opus-5-5|naive   |        10 |            1.000 |   1.000 |   1.000 |       10 |        0 |       0.002 |    0.041 |
| claude-opus-5-5|chunked  | claude-opus-5-5|plain   |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-opus-5-5|chunked  | claude-sonnet-5-5|plain |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 |
| claude-opus-5-5|naive    | claude-opus-5-5|plain   |        10 |           -1.000 |  -1.000 |  -1.000 |        0 |       10 |       0.002 |    0.041 |
| claude-opus-5-5|naive    | claude-sonnet-5-5|plain |        10 |           -1.000 |  -1.000 |  -1.000 |        0 |       10 |       0.002 |    0.041 |
| claude-opus-5-5|plain    | claude-sonnet-5-5|plain |        10 |            0.000 |   0.000 |   0.000 |        0 |        0 |       1.000 |    1.000 | 

## Deterministic checker vs labels (FLAG_ANY)

{
 "tp": 13,
 "fn": 0,
 "fp": 16,
 "tn": 41,
 "recall_unsafe": 1.0,
 "precision": 0.4482758620689655,
 "specificity": 0.7192982456140351,
 "npv": 1.0,
 "f1": 0.6190476190476191,
 "flag_rate": 0.4142857142857143,
 "recall_ci": [
  1.0,
  1.0
 ]
} 

## Deterministic checker vs labels (FLAG_REJECT)

{
 "tp": 13,
 "fn": 0,
 "fp": 1,
 "tn": 56,
 "recall_unsafe": 1.0,
 "precision": 0.9285714285714286,
 "specificity": 0.9824561403508771,
 "npv": 1.0,
 "f1": 0.9629629629629629,
 "flag_rate": 0.2,
 "recall_ci": [
  1.0,
  1.0
 ]
} 

