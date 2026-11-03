# Deterministic comparison

- Computer: Windows 11, Intel64 Family 6 Model 140 Stepping 1, GenuineIntel, Python 3.12.16
- Researched method defaults: seed 522, 4 chains x 2000 ruin-and-recreate iterations, safety time cap 300 s (never reached)
- The rule to beat has no settings and no time limit.
- Every measure was recomputed by the independent checker from the written decision.json.
- Self-crossings count pairs of legs of one route that cross on the map (the team's added constraint; the researched method enforces zero, the rule is implemented exactly as the brief states).

| Instance | Customers | Method | Checker | Total travel (min) | Vehicles used | Waiting (min) | Self-crossings | Computation time (s) |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| hand_checkable | 6 | rule | feasible | 352.417 | 2 | 232.861 | 0 | 0.000 |
| hand_checkable | 6 | researched | feasible | 329.670 | 2 | 328.798 | 0 | 3.284 |
| development_small | 15 | rule | feasible | 620.581 | 5 | 845.804 | 1 | 0.000 |
| development_small | 15 | researched | feasible | 483.044 | 4 | 701.206 | 0 | 10.228 |
| development_medium | 45 | rule | feasible | 1683.397 | 11 | 2199.093 | 0 | 0.000 |
| development_medium | 45 | researched | feasible | 1071.159 | 8 | 2174.676 | 0 | 28.692 |
| development_large | 120 | rule | feasible | 3523.223 | 25 | 5831.634 | 8 | 0.002 |
| development_large | 120 | researched | feasible | 2155.902 | 20 | 5309.162 | 0 | 83.652 |
| edge_case | 10 | rule | no feasible decision found | - | - | - | - | 0.000 |
| edge_case | 10 | researched | no feasible decision found | - | - | - | - | 0.007 |

## Researched method against the rule to beat

| Instance | Rule travel | Researched travel | Saving (min) | Saving (%) | Vehicles rule -> researched |
| --- | ---: | ---: | ---: | ---: | --- |
| hand_checkable | 352.417 | 329.670 | 22.747 | 6.5% | 2 -> 2 |
| development_small | 620.581 | 483.044 | 137.537 | 22.2% | 5 -> 4 |
| development_medium | 1683.397 | 1071.159 | 612.238 | 36.4% | 11 -> 8 |
| development_large | 3523.223 | 2155.902 | 1367.321 | 38.8% | 25 -> 20 |
