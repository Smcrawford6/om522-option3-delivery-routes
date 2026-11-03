# OM 522 Option 3: Planning delivery routes

**Team:** Sadie Crawford, Zacc Gleason, Annabelle Kemp (OM 522, Fall 2026)

Every morning a dispatcher at a single-depot delivery operation has to decide which vehicle serves each
of the day's customers and the order of stops on each vehicle's route, before any driver leaves the
yard. This tool makes that decision from the day's data files. It gives every used vehicle a timed
route that serves each customer once, inside the customer's time window, within the vehicle's capacity
and shift, and it reports the travel, waiting, and service consequences. We added one assumption
beyond the brief: **a route may not cross itself** when drawn on the depot and customer coordinates. A
driver should never cut back across their own earlier path. Two different routes may still cross. On
every supplied instance the travel time equals the straight-line distance between the coordinates, so
a self-crossing is a real detour and not just a messy map. The researched method enforces the rule as a
hard constraint. The rule to beat is implemented exactly as the brief states it (the guide requires
that), and its crossings are reported.

## Quick start

Everything runs through [Pixi](https://pixi.sh):

```bash
pixi install                                        # build the environment from pixi.toml / pixi.lock
pixi run solve <input_dir> <output_dir>             # THE GRADED COMMAND: researched method, default settings
pixi run rule  <input_dir> <output_dir>             # the rule to beat, same input/output contract
pixi run check <input_dir> <output_dir>/decision.json   # independent checker
pixi run test                                       # the automated tests
pixi run reproduce                                  # regenerates every submitted table and figure
```

`solve` reads any instance directory in the published format and writes `decision.json` (the structure of
`worked-example/solution.json`) plus `summary.md` / `summary.json` (measures, checker result, run status,
seed, stopping rule, and computation time) to the output directory. It never changes the input files.

| Input | What the tool does | Exit status |
| --- | --- | --- |
| Fails one of the four input checks | prints `input error: <file>, column '<column>': ...`, writes no `decision.json` | 2 |
| Valid, but the method finds nothing feasible | prints `no feasible decision found`, writes no `decision.json` | 0 |
| Any other valid input | writes `decision.json` and the summary | 0 |

Options for `solve`: `--method rule|researched` (default `researched`), `--seed` (522), `--chains` (4),
`--iterations` per chain (2000), `--time-limit` safety cap in seconds (480), `--verbose`.

## Repository layout

| Path | Contents |
| --- | --- |
| `vrptw/loader.py` | Reads an instance directory and applies the four input checks (files and columns present, declared types and no empty values, every referenced identifier exists, positive service times), plus sign and interval checks. Nothing is silently replaced. |
| `vrptw/core.py` | Integer-indexed copy of the instance used by both methods, route timing, and the self-crossing test. |
| `vrptw/rule.py` | Method 1, the rule to beat. |
| `vrptw/researched.py` | Method 2, the researched method. |
| `vrptw/checker.py` | Independent checker. Shares no code with either method. |
| `vrptw/cli.py`, `vrptw/experiments.py` | Commands, deterministic comparison, stress test, and figures. |
| `tests/test_tool.py` | The three required tests plus checker, loader, crossing, reproducibility, and relabeling tests. |
| `results/` | Submitted decisions, comparison tables, figures, saved stress scenarios, and stress results. |
| `presentation/` | Final-video slide deck and speaker script (HTML). |
| `hand_checkable/`, `development_*/`, `edge_case/`, `worked-example/`, `DATA_DICTIONARY.md`, `DATA_README.md` | The instructor's data package, unchanged. |

## Method 1: the rule to beat (nearest feasible neighbor)

Implemented exactly as `option-3-brief.pdf` states. Vehicles are taken in identifier order, and each one
leaves the depot at its shift start. It repeatedly drives to the nearest unserved customer by travel time
from its current location, with ties going to the smaller customer identifier. That customer must fit
the remaining capacity, allow service to start by its window end, and still allow a return to the depot
by the shift end. When no customer qualifies, the vehicle returns and the next one starts. If any customer
is still unserved after every vehicle has returned, the rule reports "no feasible decision found".

- **Representation:** a list of customers per vehicle, in visiting order.
- **Stopping rule:** every vehicle has returned (or every customer is served).
- **Randomization:** none.
- **Limitations:** the rule is greedy and myopic. It never revisits a choice, so it often drives far to
  catch a closing window and leaves stragglers for extra vehicles. It also ignores the team's
  no-self-crossing rule (8 crossings on `development_large`).
- **Test:** it reproduces `worked-example/` exactly: every visit, arrival, service start, and return
  time, plus total travel 352.417 min, 2 vehicles, and 232.861 min of waiting.

## Method 2: the researched method (Solomon I1 + local search + ruin and recreate)

**Source.** Solomon, M. M. (1987). Algorithms for the vehicle routing and scheduling problems with time
window constraints. *Operations Research*, 35(2), 254–265. This is the reading named in the brief and
the source of the I1 insertion heuristic. The improvement moves are the ones the brief lists. Stage 3
follows Shaw (1998, *CP-98*, LNCS 1520) and Ropke & Pisinger (2006, *Transportation Science* 40(4)).
Granular neighbor lists follow Toth & Vigo (2003, *INFORMS Journal on Computing* 15(4)).

**Why it fits.** Time windows are what make this decision hard. I1 builds routes by choosing, at every
step, the customer and position that add the least travel and push later stops back the least. It
checks every window as it inserts. The local search and ruin-and-recreate stages then fix the poor early
choices a greedy construction cannot revisit. Every move keeps the solution feasible.

**Representation.** One list of customer nodes per vehicle (`routes[k]`); the depot at each end is
implicit. For each route the search caches its load, travel, service starts, and *latest feasible
service start* at each position. The latest starts make a time-window check for an insertion O(1).

**Steps.**
1. *Construction (Solomon I1).* For each vehicle in identifier order, seed a route with the unrouted
   customer that is farthest from the depot or has the earliest window end. Then insert the customer with
   the largest c2 = λ·t(depot,u) − c1, where c1 = α1·(added travel, μ = 1) + (1 − α1)·(push-forward of the
   next stop). Use its cheapest feasible position that does not make the route cross itself. When nothing
   fits, start the next vehicle. The grid of 12 starts is α1 ∈ {0, 0.5, 1} × λ ∈ {1, 2} × the 2 seed
   rules.
2. *Local search* (first improvement, repeated until no move improves total travel) over:
   - relocate a run of 1–3 consecutive customers to another route, in either orientation (or-opt);
   - exchange two customers between routes;
   - exchange route tails (2-opt\*);
   - within a route, reverse any segment (2-opt) or move any run of 1–3 customers (or-opt).

   Moves between routes only pair a customer with its 12 nearest neighbors. Each candidate's travel
   change is computed first. Only an improving candidate is then checked for capacity, every window,
   the shift end, and self-crossing, and it is accepted only if all four pass.
3. *Ruin and recreate.* Four independent chains each start from the best stage-2 solution. Each
   iteration removes 4 to 30% of the customers (at most 30) by random, worst-detour, related (Shaw), or
   whole-short-route removal. It reinserts them by regret-2 or greedy insertion, with or without small
   noise, and may open an unused vehicle. Stage 2 then runs on the changed routes. The result is accepted
   by simulated annealing: the start temperature accepts a 0.5% worse result half the time, and it cools
   geometrically to 1% of that. The best solution over all chains is returned.

**Stopping rule.** 4 chains × 2,000 ruin-and-recreate iterations, a fixed count. The 480-second time
limit is only a safety cap and is never reached on the supplied instances. `summary.md` reports which
rule stopped the run.

**Randomization and seed.** Default seed 522. Chain *c* uses `random.Random(100·seed + c)`, so a rerun
reproduces the decision exactly (tested).

**Known limitations.** It is a heuristic with no optimality proof. Different seeds can end about 1%
apart on the 120-customer instance. It minimizes travel only, so vehicles used is not targeted directly
(it falls anyway). It plans for exact travel times and builds in no slack. If no crossing-free feasible
plan exists, it reports none even when a crossing plan would exist. Runtime grows with size (about 40 s
at 45 customers and about 2.5 min at 120 on our laptop).

## Independent checker

`vrptw/checker.py` reads only the instance files and `decision.json`, and it recomputes every arrival,
service start, return time, load, and measure from the visit lists. It uses identifiers and its own
timing and crossing geometry; it imports nothing from either method. It reports each violated
constraint by vehicle or customer: customer missing or served twice, vehicle used twice or unknown,
capacity, window, and shift end. It applies the instructor's 1e-8 tolerance at window and shift ends,
flags reported times that disagree with its own, and counts self-crossings for the team constraint. A
test confirms that the method's crossing test and the checker's agree on 400 random routes.

## Deterministic comparison (`results/comparison.md`)

Computer: Windows 11 laptop, Intel Core (Family 6 Model 140), Python 3.12 (Pixi). The rule has no time
limit; the researched method uses its defaults above.

| Instance | Customers | Rule travel (min) | Researched travel (min) | Saving | Vehicles rule → researched | Self-crossings rule / researched | Researched time (s) |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |
| hand_checkable | 6 | 352.417 | 329.670 | 6.5% | 2 → 2 | 0 / 0 | ~5 |
| development_small | 15 | 620.581 | 483.044 | 22.2% | 5 → 4 | 1 / 0 | ~14 |
| development_medium | 45 | 1683.397 | 1071.159 | 36.4% | 11 → 8 | 0 / 0 | ~40 |
| development_large | 120 | 3523.223 | 2153.904 | 38.9% | 25 → 19 | 8 / 0 | ~160 |
| edge_case | 10 | no feasible decision found | no feasible decision found | | | | <0.1 |

Both methods pass the checker on every instance. The rule runs in milliseconds. The gap widens with
size: on 6 customers the rule's greedy choices cost little, but on 45 and 120 customers they strand
customers that need extra vehicles and long trips. The researched method's waiting time is sometimes
higher (hand_checkable), because it trades waiting, which is free under the brief's measure, for
travel. These results cover four synthetic instances from one generator; they do not show the method
is best in general.

## Stress test of the fixed plans (`results/stress/`)

- **Uncertain input:** travel time. Scenario *s* multiplies every leg by C_s × E_ij. C_s is one
  day-wide congestion factor and E_ij is a factor for each leg; both are independent lognormal draws
  with mean 1, with coefficients of variation 0.15 and 0.10.
- **Scenarios:** 30, from seed 20261103, saved to `results/stress/scenarios/` before either plan is
  executed (`reproduce` generates them first).
- **Execution rule (brief):** follow each planned route of `development_medium` in order and wait when
  early. Every service that starts after its window end and every late return counts as a violation.
  No decision changes.

| Measure (30 scenarios) | Rule to beat | Researched |
| --- | ---: | ---: |
| Mean / 90th percentile total travel (min) | 1639.4 / 1918.6 | 1046.4 / 1241.6 |
| Mean / 90th percentile vehicles used | 11 / 11 | 8 / 8 |
| Scenarios with at least one violation | 6 | 7 |
| Violations in total (late services + late returns) | 12 (6 + 6) | 12 (12 + 0) |
| Minutes late per scenario, mean | 2.1 | 1.7 |

The per-scenario plot is `results/stress/stress_per_scenario.png`. Mean realized travel is slightly
below planned travel for both plans because these 30 congestion draws average a little under 1.

**Sensitivity** (`results/stress/sensitivity.md`): the same saved scenarios rescaled to heavier average
congestion.

| Mean congestion | Scenarios with a violation (rule / researched) | Violations in total (rule / researched) | Late returns (rule / researched) |
| ---: | --- | --- | --- |
| 1.0 | 6 / 7 | 12 / 12 | 6 / 0 |
| 1.1 | 8 / 12 | 25 / 25 | 10 / 1 |
| 1.2 | 19 / 20 | 61 / 56 | 21 / 4 |
| 1.3 | 23 / 28 | 100 / 96 | 32 / 9 |

## Recommendation

**Adopt the researched method.** On the 45-customer development day it cuts planned travel by 612 min
(36%) and uses 3 fewer vehicles (8 instead of 11). Under the 30 travel-time scenarios it keeps that
saving: 593 min less realized travel on average. It has the same number of violations (12 vs 12), no
late returns, and fewer minutes late. **The tradeoff accepted:** its routes are tighter, so with
heavier congestion it has a slightly higher chance that a given day has at least one late service
(7 vs 6 of 30 days at the planned level, 12 vs 8 at +10%). **The recommendation would change** if average
congestion runs about 10% or more above the planning data *and* the dispatcher judges a day by whether
any window is missed, rather than by total violations or travel. Then neither fixed plan is acceptable
as is, and the plan should be rebuilt with buffered travel times or replanned during the day.

## Tools used

Claude Code (Anthropic), an agentic coding tool, researched the method and drafted the code, tests,
README, and presentation; the team reviewed every component. We used Python 3.12, matplotlib, pytest,
and Pixi. No code from the in-class notebooks was reused. No paid service, private account, or
external system is needed to run or grade the tool.
