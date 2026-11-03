# Stress test of the fixed plans

- Instance: development_medium; 30 scenarios drawn from seed 20261103 and saved to results/stress/scenarios/ before either plan is executed.
- Uncertain input: travel time.  Scenario s multiplies every leg by C_s x E_ij, where the day-wide congestion factor C_s and each leg's own factor E_ij are independent lognormal draws with mean 1 and coefficients of variation 0.15 and 0.1.
- Execution rule (brief): each planned route is followed in its planned order; a vehicle that arrives early waits; every service that starts after its window end and every return after the shift end counts as a constraint violation.  No decision is changed.

| Measure | Rule to beat | Researched |
| --- | ---: | ---: |
| Planned total travel (min) | 1683.397 | 1071.159 |
| Mean total travel (min) | 1639.357 | 1046.362 |
| 90th percentile total travel (min) | 1918.588 | 1241.643 |
| Mean vehicles used | 11.0 | 8.0 |
| 90th percentile vehicles used | 11.0 | 8.0 |
| Scenarios with at least one violation (of 30) | 6 | 7 |
| Violations, total over 30 scenarios | 12 | 12 |
| Violations per scenario, mean | 0.40 | 0.40 |
| Violations per scenario, 90th percentile | 2.0 | 1.1 |
| Late service starts, total | 6 | 12 |
| Late returns, total | 6 | 0 |
| Minutes late per scenario, mean | 2.14 | 1.68 |

The 90th percentile uses Python's statistics.quantiles(n=10, method='inclusive').
