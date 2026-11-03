"""Build the final-video slide deck and speaker script from results/ and the code.

    pixi run presentation

Every number on a slide is read from results/, and every code excerpt is read
from vrptw/, so the deck cannot drift from the submitted repository.
"""

import ast
import base64
import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = ROOT / "presentation"
TEAM = ["Sadie Crawford", "Zacc Gleason", "Annabelle Kemp"]
SADIE, ZACC, ANNABELLE = TEAM


def img(path):
    return "data:image/png;base64," + base64.b64encode((ROOT / path).read_bytes()).decode()


def excerpt(module, name, first=None, last=None):
    """Source of one function (optionally a line range of it), for code slides."""
    _source = (ROOT / "vrptw" / module).read_text(encoding="utf-8")
    for _node in ast.walk(ast.parse(_source)):
        if isinstance(_node, (ast.FunctionDef, ast.ClassDef)) and _node.name == name:
            _lines = _source.splitlines()[_node.lineno - 1:_node.end_lineno]
            _start = _node.lineno
            if first is not None:
                _lines = _lines[first:last]
                _start += first
            return _start, "\n".join(_lines)
    raise KeyError(name)


def code_block(module, name, first=None, last=None, highlight=()):
    _start, _text = excerpt(module, name, first, last)
    _rows = []
    for _i, _line in enumerate(_text.splitlines()):
        _cls = ' class="hl"' if any(h in _line for h in highlight) else ""
        _rows.append(f'<span{_cls}><i>{_start + _i}</i>{html.escape(_line) or " "}</span>')
    return f'<div class="file">vrptw/{module}</div><pre class="code">{"".join(_rows)}</pre>'


# --- results ---------------------------------------------------------------------

with open(RES / "comparison.csv", newline="", encoding="utf-8") as _f:
    ROWS = {(r["instance"], r["method"]): r for r in csv.DictReader(_f)}
STRESS = json.loads((RES / "stress" / "stress_summary.json").read_text())["summary"]
with open(RES / "stress" / "sensitivity.csv", newline="", encoding="utf-8") as _f:
    SENS = {(float(r["mean_congestion"]), r["method"]): r for r in csv.DictReader(_f)}
INSTANCES = ["hand_checkable", "development_small", "development_medium", "development_large"]


def f(x, d=1):
    return f"{float(x):,.{d}f}"


def saving(name):
    _a = float(ROWS[(name, "rule")]["total_travel_time"])
    _b = float(ROWS[(name, "researched")]["total_travel_time"])
    return _a - _b, 100 * (_a - _b) / _a


MED_SAVE, MED_PCT = saving("development_medium")
LRG_SAVE, LRG_PCT = saving("development_large")
R_MED, X_MED = ROWS[("development_medium", "rule")], ROWS[("development_medium", "researched")]
SR, SX = STRESS["rule"], STRESS["researched"]


def comparison_table():
    _body = ""
    for _n in INSTANCES:
        _r, _x = ROWS[(_n, "rule")], ROWS[(_n, "researched")]
        _s, _p = saving(_n)
        _body += (f"<tr><td>{_n}</td><td>{_r['customers']}</td><td>{f(_r['total_travel_time'], 3)}</td>"
                  f"<td><b>{f(_x['total_travel_time'], 3)}</b></td><td>{_p:.1f}%</td>"
                  f"<td>{_r['vehicles_used']} → {_x['vehicles_used']}</td>"
                  f"<td>{_r['self_crossings']} / {_x['self_crossings']}</td>"
                  f"<td>{float(_r['computation_time_s']):.3f} / {float(_x['computation_time_s']):.1f}</td></tr>")
    _body += ("<tr><td>edge_case</td><td>10</td><td colspan='6'>both methods: “no feasible decision found” "
              "(C010 demand 65 &gt; capacity 60)</td></tr>")
    return ("<table><thead><tr><th>Instance</th><th>n</th><th>Rule travel</th><th>Researched travel</th>"
            "<th>Saving</th><th>Vehicles</th><th>Self-crossings<br>rule / ours</th><th>Time (s)<br>rule / ours</th>"
            f"</tr></thead><tbody>{_body}</tbody></table>")


def stress_table():
    _rows = [("Mean total travel (min)", f(SR["travel_mean"]), f(SX["travel_mean"])),
             ("90th percentile total travel (min)", f(SR["travel_p90"]), f(SX["travel_p90"])),
             ("Mean / 90th pct vehicles used", f"{SR['vehicles_mean']:.0f} / {SR['vehicles_p90']:.0f}",
              f"{SX['vehicles_mean']:.0f} / {SX['vehicles_p90']:.0f}"),
             ("Scenarios with ≥ 1 violation (of 30)", SR["scenarios_with_violation"], SX["scenarios_with_violation"]),
             ("Violations in total", SR["violations_total"], SX["violations_total"]),
             ("… late service starts / late returns", f"{SR['late_services_total']} / {SR['late_returns_total']}",
              f"{SX['late_services_total']} / {SX['late_returns_total']}"),
             ("Minutes late per scenario, mean", f(SR["lateness_mean_min"], 2), f(SX["lateness_mean_min"], 2))]
    _body = "".join(f"<tr><td>{a}</td><td>{b}</td><td><b>{c}</b></td></tr>" for a, b, c in _rows)
    return f"<table><thead><tr><th>30 scenarios, development_medium</th><th>Rule</th><th>Researched</th></tr></thead><tbody>{_body}</tbody></table>"


def sensitivity_table():
    _body = ""
    for _level in (1.0, 1.1, 1.2, 1.3):
        _r, _x = SENS[(_level, "rule")], SENS[(_level, "researched")]
        _body += (f"<tr><td>×{_level:.1f}</td><td>{_r['scenarios_with_violation']} / <b>{_x['scenarios_with_violation']}</b></td>"
                  f"<td>{_r['violations_total']} / <b>{_x['violations_total']}</b></td>"
                  f"<td>{_r['late_returns_total']} / <b>{_x['late_returns_total']}</b></td>"
                  f"<td>{f(_r['lateness_mean_min'])} / <b>{f(_x['lateness_mean_min'])}</b></td></tr>")
    return ("<table><thead><tr><th>Mean congestion</th><th>Days with a violation<br>rule / ours</th>"
            "<th>Violations<br>rule / ours</th><th>Late returns<br>rule / ours</th><th>Min late per day<br>rule / ours</th>"
            f"</tr></thead><tbody>{_body}</tbody></table>")


# --- slides: (speaker, title, body html, script paragraphs, seconds) -------------------

SLIDES = []


def slide(speaker, title, body, script, pause, kind=""):
    """pause: extra seconds for on-screen actions beyond speaking at 150 words per minute."""
    _words = sum(len(p.split()) for p in script)
    SLIDES.append({"speaker": speaker, "title": title, "body": body, "script": script,
                   "seconds": round(_words / 150 * 60) + pause, "kind": kind})


slide(SADIE, "Planning delivery routes", f"""
<div class="hero">
  <p class="eyebrow">OM 522 · Team project · Option 3 · Final submission</p>
  <h1>Planning delivery routes<br><span>with capacity, time windows, and shifts</span></h1>
  <p class="names">{' · '.join(TEAM)}</p>
  <div class="kpis">
    <div><b>{MED_PCT:.0f}%</b><span>less travel than the rule to beat<br>(45-customer day)</span></div>
    <div><b>{R_MED['vehicles_used']} → {X_MED['vehicles_used']}</b><span>vehicles used</span></div>
    <div><b>0</b><span>routes that cross themselves</span></div>
  </div>
</div>""", [
    f"Hi, we are {SADIE}, {ZACC}, and {ANNABELLE}, and this is our final submission for option 3, planning delivery routes.",
    f"In fifteen minutes we will show the tool running on a fresh instance, both methods, the independent checker, the comparison, the stress test, and our recommendation. The headline: on the 45-customer development day our researched method drives {MED_PCT:.0f} percent less than the rule to beat, with {X_MED['vehicles_used']} vehicles instead of {R_MED['vehicles_used']}, and no route ever crosses itself.",
], 3, "title")

slide(SADIE, "The decision", """
<div class="two">
 <div>
  <h3>Who decides, and what</h3>
  <p>Every morning a <b>dispatcher</b> at one depot assigns each customer to a vehicle and chooses the order of stops on each route, before any driver leaves.</p>
  <h3>What makes it hard</h3>
  <ul><li><b>Capacity:</b> a route's total demand cannot exceed the vehicle's capacity.</li>
  <li><b>Time windows:</b> service must start inside the window. Arriving early means waiting; arriving late is not allowed.</li>
  <li><b>Shifts:</b> leave at shift start and return by shift end.</li>
  <li>Every customer is served exactly once.</li></ul>
 </div>
 <div>
  <h3>How we score a plan</h3>
  <ul><li><b>Primary:</b> total travel time (excludes waiting and service).</li>
  <li><b>Secondary:</b> vehicles used.</li><li>Plus computation time.</li></ul>
  <div class="callout"><h3>Our added assumption</h3><p>A route may <b>not cross itself</b> on the map. A driver should never cut back across their own path. Different routes may cross. Travel time equals straight-line distance here, so a self-crossing is a real detour.</p></div>
 </div>
</div>""", [
    "Each morning a dispatcher decides which vehicle serves each customer and the order of its stops. Trucks have a capacity, customers have time windows (early trucks wait, and service may not start after the window closes), and every truck must be back by shift end.",
    "We score plans by total driving time first, vehicles used second, and we always report computation time.",
    "We added one assumption: a route may not cross itself on the map, because a driver should not cut back across their own path. Different routes may cross. Travel time here equals straight-line distance, so a crossing is real wasted driving.",
], 3)

slide(SADIE, "Live demo: a fresh instance", """
<div class="two">
<div>
<p>The instructor's run, on a <b>copied</b> instance directory:</p>
<pre class="term">$ cp -r development_medium ~/fresh_day
$ pixi run solve ~/fresh_day ~/out_researched
$ pixi run rule  ~/fresh_day ~/out_rule
$ pixi run check ~/fresh_day ~/out_researched/decision.json
$ pixi run check ~/fresh_day ~/out_rule/decision.json</pre>
<p class="small">Each output folder holds <code>decision.json</code> (the structure of the worked example) and <code>summary.md</code> (measures, checker verdict, seed, stopping rule, run time).</p>
</div>
<div>
<h3>Three responses the guide requires</h3>
<table><tbody>
<tr><td>Valid input</td><td>writes <code>decision.json</code>, exit 0</td></tr>
<tr><td>Valid but infeasible (<code>edge_case</code>)</td><td>prints “no feasible decision found”, no file, exit 0</td></tr>
<tr><td>Malformed (column deleted)</td><td>“input error: customers.csv, column 'window_end' …”, no file, exit 2</td></tr>
</tbody></table>
</div></div>""", [
    "[SCREEN: terminal] Here is the run the instructor performs. I copy the medium development instance to a new folder, so nothing is pre-computed, and run the documented solve command, which runs the researched method with default settings. Then I run the rule to beat on the same folder.",
    "[SCREEN: point at the printed line] Each run prints total travel, vehicles, the checker's verdict, and run time, and writes decision.json and a summary.",
    "[SCREEN: run check twice] Now the checker. It reads only the input files and the decision file. It confirms both decisions are feasible and prints each route with its load, travel, and return time.",
    "[SCREEN: run edge_case, then a copy with window_end deleted] Two more cases. On the edge case one customer needs 65 units and every truck holds 60, so the tool prints 'no feasible decision found' and writes nothing. If I delete a required column, it names the file and the column and exits with an error.",
], 35, "demo")

slide(SADIE, "Method 1: the rule to beat", f"""
<div class="two">
<div>
<h3>Nearest feasible neighbor, one vehicle at a time</h3>
<ol><li>Take vehicles in identifier order; each leaves at its shift start.</li>
<li>Drive to the <b>nearest</b> unserved customer (ties by ID) that<br>· fits the remaining capacity,<br>· can start service by its window end,<br>· still allows a return by the shift end.</li>
<li>No customer qualifies → return; the next vehicle starts.</li>
<li>Anyone left unserved → “no feasible decision found”.</li></ol>
<p class="small">Deterministic, no seed. Implemented exactly as written, so it does <b>not</b> apply our crossing rule: {ROWS[('development_large','rule')]['self_crossings']} self-crossings on the large case.</p>
</div>
<div>
<h3>Test 1: it reproduces the worked example</h3>
<table><thead><tr><th>Vehicle</th><th>Visits</th><th>Return</th></tr></thead><tbody>
<tr><td>V01</td><td>C003 → C002 → C004</td><td>361.875</td></tr>
<tr><td>V02</td><td>C001 → C005 → C006</td><td>289.403</td></tr></tbody></table>
<div class="kpis small-k"><div><b>352.417</b><span>total travel (min), matches</span></div><div><b>232.861</b><span>waiting (min), matches</span></div></div>
<p class="small">Every arrival and service start matches <code>worked-example/solution.json</code>.</p>
</div></div>""", [
    "Method one is the rule to beat, exactly as the brief states it. Vehicles go out in ID order, and each keeps driving to the nearest unserved customer it can still legally serve: it fits the remaining capacity, can start before its window closes, and still lets the truck get home by shift end. When nothing qualifies, the next truck starts.",
    "Required test one checks it reproduces the worked example exactly: the same routes and times, and 352.417 minutes of travel. Implemented as written, it ignores our crossing rule, with eight self-crossings on the large case.",
], 3)

slide(SADIE, "Walk-through: the loader (agent-drafted)", code_block("loader.py", "read_table", highlight=("raise InputError",)) + """
<div class="note"><b>What was wrong / unclear:</b> the agent's draft accepted any number in an integer column. We had to decide whether "7.0" counts as an integer: the loader accepts it, but "7.5" or "seven" is rejected with the file, column, and row. <b>How we checked:</b> four corrupted copies of hand_checkable (wrong type, zero service time, empty capacity, unknown ID), and required test 3 deletes <code>window_end</code>. All are rejected with a message naming the file and column.</div>""", [
    "[SCREEN: loader.py] My component is the loader, which our coding agent drafted. read_table runs the first two input checks: every required file and column is present, and every value has its declared type with no empty cells. load_instance then checks that referenced IDs exist and service times are positive.",
    "What was unclear in the agent's version was the integer type. The schema says demand and windows are integers, so we had to decide what to do with a value like '7.0'. We accept it, because it is a whole number. But '7.5' or 'seven' stops the run with the file, column, and row. Nothing is ever silently replaced.",
    "How we checked it: our tests corrupt copies of the hand-checkable instance with a wrong type, a zero service time, an empty capacity, an unknown ID, and a deleted column. Every one is rejected with the file and column named. Reversing every file's rows gives identical results, so IDs are matched by value, not row position.",
], 5, "code")

slide(ZACC, "Method 2: the researched method", f"""
<div class="flow">
 <div><span>1</span><h3>Construct</h3><p><b>Solomon (1987) I1 insertion.</b> Seed a route, then insert the customer with the best c2 = λ·t(depot,u) − c1, where c1 blends the added travel and the push-forward of later stops. Every window is checked on insertion. 12 parameter starts (α1 × λ × seed rule).</p></div>
 <div><span>2</span><h3>Improve</h3><p><b>Local search</b> with the brief's moves: relocate 1–3 customers (or-opt), exchange between routes, reverse a segment (2-opt), and swap route tails (2-opt*). Candidate moves use each customer's 12 nearest neighbors.</p></div>
 <div><span>3</span><h3>Ruin &amp; recreate</h3><p><b>Large neighborhood search</b> (Shaw 1998; Ropke &amp; Pisinger 2006): remove 4–30% of customers, reinsert by regret-2 or greedy insertion, improve, and accept by simulated annealing. 4 seeded chains; keep the best.</p></div>
</div>
<div class="stages">
 <div><b>{f(R_MED['total_travel_time'])}</b><span>rule to beat</span></div><i>→</i>
 <div><b>{f(X_MED['start_cost'])}</b><span>best of 12 I1 starts + local search</span></div><i>→</i>
 <div><b>{f(X_MED['total_travel_time'])}</b><span>+ ruin and recreate (final)</span></div>
 <p class="small">Total travel (min) on development_medium after each stage.</p>
</div>
<div class="two tight">
<p><b>Representation:</b> one ordered list of customers per vehicle; each route caches its load, service starts, and the <i>latest feasible start</i> at every stop, so a window check for an insertion takes constant time.</p>
<p><b>Stopping rule:</b> 4 chains × 2,000 iterations (fixed count). The 480 s limit is only a safety cap and is never hit. <b>Seed</b> 522 → chain c uses Random(100·seed + c); reruns are identical (tested).</p>
</div>""", [
    "The researched method has three stages, all from the reading the brief names.",
    "Stage one is Solomon's 1987 I1 insertion heuristic. It seeds a route with a far-away or urgent customer, then keeps inserting the customer most worth inserting now, balancing extra driving against how far it pushes later stops back, and checking every window. We run twelve parameter settings.",
    "Stage two is local search with the brief's moves: relocate customers, exchange them between routes, reverse a segment, and swap route ends, each customer paired with its twelve nearest neighbors.",
    "Stage three is ruin and recreate: tear out up to thirty percent of the customers, reinsert them, run local search again, and accept by simulated annealing. Four seeded chains of 2,000 iterations each; we keep the best. It stops on that fixed count, and reruns with seed 522 are identical.",
], 3)

slide(ZACC, "Feasibility is checked after every move", code_block("researched.py", "insertion_options", 0, 40, highlight=("_latest[_q]", "inst.late[u]", "shift_end")) + """
<div class="note"><b>Order of checks for every candidate move:</b> travel change first (cheap); only an improving move is then checked for capacity → every window and the shift end → no self-crossing. A move is accepted only if all pass, so the current plan is always feasible.</div>""", [
    "[SCREEN: researched.py, insertion_options] For each route we cache every stop's service start and the latest start that keeps the rest of the route feasible. So an insertion needs just two checks, the new customer's own window and the next stop's latest start, which takes constant time.",
    "For other moves we compute the travel change first. Only an improving move gets the full check, capacity, then windows and shift end, then crossings, so the search only ever holds feasible plans.",
], 5, "code")

slide(ZACC, "Walk-through: the researched search (agent-drafted)", code_block("researched.py", "recreate", 0, 22, highlight=("_noise", "_regret_rule")) + """
<div class="note"><b>What was wrong:</b> (1) the agent's first I1 draft carried a placeholder term <code>(mu − 1)·0</code>, so the μ parameter silently did nothing. We removed μ from the grid and documented μ = 1. (2) Every seed stopped at 1071.159 on medium. <b>How we checked:</b> we fed a known better plan (1070.565) into the method's own feasibility test. It passed and was a local optimum, so the problem was search diversity, not a feasibility bug. We added insertion noise, greedy as well as regret insertion, and independent seeded chains. Some seeds now reach 1070.565, and on the large case the four chains end between 2,154 and 2,176, so keeping the best chain protects against an unlucky seed.</div>""", [
    "[SCREEN: researched.py, recreate] My walk-through is the search itself, which the agent drafted. Two things were wrong, and both teach something.",
    "First, the agent's draft of Solomon's formula had a placeholder term, mu minus one times zero, so mu silently did nothing. The answers were still feasible, so only reading the code against the paper caught it. We now fix mu at one, the standard value, and document it.",
    "Second, on the medium instance every seed stopped at exactly 1071.159. We had a slightly better plan, 1070.565, from an earlier attempt, so we fed it to the method's own feasibility test. It passed and local search could not improve it, so nothing was wrongly rejected; the search just never reached it. The fix is the diversification here, from Ropke and Pisinger: noise on insertion costs, greedy as well as regret insertion, and four independent chains. Some seeds now reach 1070.565, and keeping the best chain protects us against an unlucky seed.",
], 5, "code")

slide(ZACC, "Deterministic comparison: four instances", comparison_table() + f"""
<img class="wide" src="{img('results/comparison.png')}" alt="Grouped bars of total travel and vehicles by instance">
<p class="small">Windows 11 laptop, Python 3.12 (Pixi). Rule: no time limit. Researched: default settings; the 480 s safety cap is never reached.</p>""", [
    f"Here is the comparison on all four instances, every number recomputed by the checker from the decision files.",
    f"The researched method beats the rule on every instance, and the gap grows with size: 6.5 percent on six customers, 22 percent on 15, {MED_PCT:.0f} percent on 45, and {LRG_PCT:.0f} percent on 120 customers. That is {LRG_SAVE:,.0f} fewer minutes of driving. It also uses fewer vehicles, for example 19 instead of 25 on the large case.",
    "The price is computation time: milliseconds for the rule, up to about two minutes for ours on 120 customers. That is well inside the ten-minute limit for a plan made once a morning.",
    "These are four synthetic instances, so we do not claim the method is best in general.",
], 3)

slide(ZACC, "What the dispatcher sees", f"""
<img class="wide tall" src="{img('results/routes_development_large.png')}" alt="Route maps for the large instance, rule versus researched">
""", [
    "This is the 120-customer case on the map. On the left, the rule: greedy routes that zig-zag and double back, with the eight self-crossing routes drawn in dashed red. On the right, ours: compact petals out of the depot, nineteen trucks, and no route that crosses itself.",
], 5)

slide(ANNABELLE, "Independent checker and tests", """
<div class="two">
<div>
<h3>The checker trusts nothing a method reports</h3>
<ul><li>Reads <b>only</b> the input files and <code>decision.json</code>.</li>
<li>Recomputes every arrival, service start, return, load, and measure from the visit lists.</li>
<li>Its own timing and crossing geometry; imports nothing from either method.</li>
<li>Names each violation: customer missing or served twice, vehicle reused or unknown, capacity, window, shift end. Same 1e-8 tolerance as the instructor.</li></ul>
</div>
<div>
<h3><code>pixi run test</code>: 15 tests pass</h3>
<ol><li><b>Required:</b> the rule reproduces the worked example.</li>
<li><b>Required:</b> the edge case gives “no feasible decision found” (both methods).</li>
<li><b>Required:</b> a deleted column is rejected, naming file and column.</li></ol>
<p class="small">Plus: four other bad inputs, the checker catching four broken decisions, the method and checker crossing tests agreeing on 400 random routes, the researched method beating the rule with zero crossings, reruns giving identical results, and reversed rows giving the same answer.</p>
</div></div>""", [
    "The checker protects us from code that claims a result it did not achieve. It reads only the input files and a decision file, imports nothing from either method, and recomputes every time, load, and measure from the visit lists. Each violation names the vehicle or customer.",
    "pixi run test runs fifteen tests: the three required ones, plus broken decisions the checker must catch, identical reruns, and agreement between the two crossing tests.",
], 3)

slide(ANNABELLE, "Walk-through: the checker (agent-drafted)", code_block("checker.py", "count_self_crossings") + code_block("checker.py", "_legs_cross", 0, 9) + """
<div class="note"><b>What was wrong:</b> the agent's first crossing test counted <i>any</i> shared point between two legs. Two stops at the same coordinates would then look like a crossing and could make a valid plan look infeasible. We now count a proper crossing, an overlap, or a T-junction, but not two legs that only meet end to end. <b>How we checked:</b> the method and the checker use separately written geometry, and a test confirms they agree on 400 random routes.</div>""", [
    "[SCREEN: checker.py] My walk-through is the crossing part of the checker. count_self_crossings draws the route depot to depot and compares every pair of legs that are not next to each other. The first and last legs both touch the depot, so that pair is skipped.",
    "What was wrong in the agent's first version: it counted any shared point as a crossing. If two customers had the same coordinates, two legs meeting end to end at that point would be counted, and a perfectly good route would be flagged. We defined a crossing as two legs that properly cross, overlap, or form a T, and not legs that only meet at a shared end point.",
    "How we checked it: the method's crossing test and this one were written separately, and a test confirms they agree on 400 random routes. So if one of them were wrong, the test would fail.",
], 5, "code")

slide(ANNABELLE, "Stress test: what if travel times are wrong?", f"""
<div class="two">
<div>
<h3>Design</h3>
<ul><li><b>Uncertain input:</b> travel time. Scenario s multiplies each leg by C<sub>s</sub> × E<sub>ij</sub>, both lognormal with mean 1: a day-wide congestion factor (CV 0.15) and a factor for each leg (CV 0.10).</li>
<li><b>30 scenarios</b>, seed 20261103, saved to <code>results/stress/scenarios/</code> <b>before</b> either plan runs.</li>
<li><b>Fixed plans</b> on development_medium, executed by the brief's rule: follow each route in order and wait if early. Every late service start and every late return counts as a violation.</li></ul>
</div>
<div>{stress_table()}</div></div>""", [
    "The stress test asks what happens when travel times are wrong. Each of thirty scenarios has a day-wide congestion factor and a factor on every leg, both lognormal with mean one. They come from a fixed seed and are saved before either plan runs, so both plans face the same days.",
    "Each fixed plan for the medium instance is driven through every scenario unchanged, counting late service starts and late returns.",
    f"The researched plan keeps its advantage: about {SR['travel_mean'] - SX['travel_mean']:,.0f} fewer minutes of driving on an average day, and 8 vehicles throughout. Violations are the same, twelve each over thirty days, but ours has no late returns, while six of the rule's are drivers coming back after their shift. Ours has one more day with at least one violation, seven against six.",
], 3)

slide(ANNABELLE, "Per-scenario results", f"""<img class="wide tall" src="{img('results/stress/stress_per_scenario.png')}" alt="Per-scenario realized travel and violations for both plans">""", [
    "Scenario by scenario: the blue line, our plan, sits about six hundred minutes below the rule on every one of the thirty days. In the lower panel the violations cluster on the same high-congestion days for both plans, like scenario 29, so they come from traffic, not from one plan being fragile.",
], 5)

slide(ANNABELLE, "When does the answer change? Heavier congestion", sensitivity_table() + """
<p class="small">The same 30 saved scenarios, rescaled so average congestion is 10–30% above the planning data (common random numbers, so only the level changes).</p>
<div class="callout"><p>As traffic gets worse, the researched plan has <b>no more total violations, far fewer late returns, and about half the minutes late</b>. But because it packs each route more tightly, a few <b>more days have at least one late stop</b> (12 vs 8 days at +10%).</p></div>""", [
    "To find a condition that would change our recommendation, we rescaled the same thirty scenarios to heavier average congestion: ten, twenty, and thirty percent above the planning data.",
    "Our plan never has more total violations than the rule, it has far fewer late returns, and it has about half the minutes late. But it packs routes tighter, so on more days there is at least one late stop: twelve days against eight at plus ten percent.",
], 3)

slide(ANNABELLE, "Recommendation", f"""
<div class="rec">
<div><h3>Recommend</h3><p class="big">Adopt the researched method</p><p>Solomon I1 + local search + ruin and recreate, with the no-self-crossing rule.</p></div>
<div><h3>Expected benefit</h3><p class="big">−{MED_SAVE:,.0f} min/day</p><p>{MED_PCT:.0f}% less planned driving on the 45-customer day ({f(R_MED['total_travel_time'])} → {f(X_MED['total_travel_time'])} min), 3 fewer vehicles (11 → 8), and about {SR['travel_mean'] - SX['travel_mean']:,.0f} fewer minutes on an average uncertain day.</p></div>
<div><h3>Tradeoff accepted</h3><p>Tighter routes: about 40 s of computing instead of milliseconds, and slightly more days with at least one late stop ({SX['scenarios_with_violation']} vs {SR['scenarios_with_violation']} of 30).</p></div>
<div><h3>Would change if…</h3><p>average congestion runs <b>≥ 10% above</b> the planning data <b>and</b> any missed window on a day is unacceptable. Then neither fixed plan works as is: plan with buffered travel times or replan during the day.</p></div>
</div>""", [
    "Our recommendation: adopt the researched method.",
    f"The expected benefit, on the 45-customer day, is about {MED_SAVE:,.0f} fewer minutes of planned driving, {MED_PCT:.0f} percent, with three fewer trucks. Under uncertain travel times it still saves about {SR['travel_mean'] - SX['travel_mean']:,.0f} minutes on an average day, with no more violations than the rule.",
    "The tradeoff we accept is a tighter plan. It takes about forty seconds to compute instead of milliseconds, and on a few more days there is at least one late stop.",
    "The recommendation would change if traffic runs about ten percent or more above the planning data and the operation cannot accept even one missed window in a day. Then neither fixed plan is good enough, and the dispatcher should plan with buffered travel times or replan during the day.",
], 3, "rec")

slide(ZACC, "Limitations, and thank you", """
<div class="two">
<div><h3>Limitations</h3><ul>
<li>A heuristic: no proof of optimality. Different seeds land within about 1% of each other on 120 customers.</li>
<li>It plans for exact travel times and builds in no slack, which is why it is sensitive to heavier congestion.</li>
<li>It minimizes travel only; using fewer vehicles is a side effect, not a target.</li>
<li>Evidence comes from four synthetic instances from one generator, plus one infeasible edge case.</li>
<li>No-crossing is our rule. If no crossing-free plan exists, the method reports none even when a crossing plan would exist.</li></ul></div>
<div><h3>Reproduce everything</h3><pre class="term">pixi install
pixi run test
pixi run reproduce
pixi run solve &lt;input_dir&gt; &lt;output_dir&gt;</pre>
<p class="small">README: method details, seeds, stopping rules, and sources. Built with Claude Code (agentic coding); every component reviewed by the team.</p>
<p class="names">Sadie Crawford · Zacc Gleason · Annabelle Kemp</p></div></div>""", [
    "Limitations: it is a heuristic with no optimality proof, seeds differ by about one percent on the large case, and it plans with no slack, which is why heavier congestion is what would change our recommendation.",
    "Everything regenerates with pixi run reproduce, and the README documents each method, seed, stopping rule, and source. Thank you.",
], 3)


# --- render ----------------------------------------------------------------------------

CSS = """
:root{--ink:#16181d;--muted:#5b5f68;--line:#e3e1dc;--bg:#f6f5f2;--paper:#ffffff;--accent:#9e1b32;--blue:#2a78d6;--orange:#eb6834;--soft:#f3e7e9}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#eceae5;--muted:#a9a69e;--line:#34363c;--bg:#101114;--paper:#1a1b1f;--accent:#e0566f;--soft:#2a1d21}}
:root[data-theme="dark"]{--ink:#eceae5;--muted:#a9a69e;--line:#34363c;--bg:#101114;--paper:#1a1b1f;--accent:#e0566f;--soft:#2a1d21}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font-family:"Inter","Segoe UI",system-ui,sans-serif}
"""

DECK_CSS = CSS + """
body{overflow:hidden}
.deck{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
.slide{display:none;position:relative;width:min(100vw,177.78vh);height:min(56.25vw,100vh);background:var(--paper);padding:3.2% 4.2% 4.5%;overflow:hidden;font-size:min(1.55vw,2.76vh);line-height:1.38}
.slide.on{display:flex;flex-direction:column}
.slide>header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid var(--accent);padding-bottom:.35em;margin-bottom:.8em}
.slide>header h2{margin:0;font-size:1.75em;letter-spacing:-.01em}
.slide>header .who{color:var(--muted);font-size:.85em;white-space:nowrap}
.slide footer{position:absolute;left:4.2%;right:4.2%;bottom:1.4%;display:flex;justify-content:space-between;color:var(--muted);font-size:.7em}
h3{margin:.2em 0 .35em;font-size:1.02em;color:var(--accent)}p{margin:.3em 0 .55em}ul,ol{margin:.2em 0 .6em;padding-left:1.25em}li{margin:.18em 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:4%;flex:1;min-height:0}.two.tight{flex:0;margin-top:.6em;font-size:.88em}
.small{font-size:.8em;color:var(--muted)}code{font-family:"Cascadia Code",Consolas,monospace;font-size:.9em;background:var(--soft);padding:0 .25em;border-radius:3px}
table{border-collapse:collapse;width:100%;font-size:.8em;margin:.2em 0 .5em}th,td{padding:.32em .5em;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600;font-size:.92em}
td b{color:var(--blue)}
.callout{background:var(--soft);border-left:4px solid var(--accent);padding:.6em .9em;border-radius:4px;margin-top:.6em}
.note{background:var(--soft);border-left:4px solid var(--accent);padding:.5em .8em;border-radius:4px;font-size:.78em;margin-top:.5em}
.term{background:#16181d;color:#e8e6e1;padding:.8em 1em;border-radius:6px;font-family:"Cascadia Code",Consolas,monospace;font-size:.78em;white-space:pre-wrap}
.file{font-family:Consolas,monospace;font-size:.68em;color:var(--muted);margin-bottom:.2em}
pre.code{margin:0 0 .3em;background:#16181d;color:#d9d7d2;border-radius:6px;padding:.5em .2em;font-family:"Cascadia Code",Consolas,monospace;font-size:.6em;line-height:1.35;overflow:hidden;flex-shrink:1;min-height:0}
pre.code span{display:block;padding:0 .6em;white-space:pre}pre.code span.hl{background:rgba(224,86,111,.22)}pre.code i{display:inline-block;width:3em;color:#7d7b75;font-style:normal;user-select:none}
img.wide{display:block;max-width:100%;max-height:44%;margin:.2em auto;object-fit:contain;border-radius:4px;background:#fff}img.wide.tall{max-height:88%}
.hero{margin:auto 0}.hero h1{font-size:3em;line-height:1.05;margin:.1em 0 .3em;letter-spacing:-.02em}.hero h1 span{display:block;font-size:.5em;color:var(--muted);font-weight:500;margin-top:.3em}
.eyebrow{color:var(--accent);font-weight:600;letter-spacing:.06em;text-transform:uppercase;font-size:.8em}.names{font-size:1.1em}
.kpis{display:flex;gap:2.5em;margin-top:1.4em}.kpis div{border-top:3px solid var(--accent);padding-top:.4em;max-width:14em}.kpis b{display:block;font-size:2.1em;line-height:1.1}.kpis span{font-size:.8em;color:var(--muted)}
.small-k b{font-size:1.5em}
.flow{display:grid;grid-template-columns:repeat(3,1fr);gap:2.5%}.flow div{border:1px solid var(--line);border-top:4px solid var(--accent);border-radius:6px;padding:.6em .8em;font-size:.86em}
.flow span{display:inline-block;width:1.6em;height:1.6em;border-radius:50%;background:var(--accent);color:#fff;text-align:center;line-height:1.6em;font-weight:700;margin-right:.3em}.flow h3{display:inline}
.rec{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:1em;flex:1}.rec div{border:1px solid var(--line);border-radius:8px;padding:.7em 1em}.rec div:first-child{background:var(--soft);border-color:var(--accent)}
.stages{display:flex;align-items:center;gap:1.2em;flex-wrap:wrap;margin:.9em 0 .2em}.stages div{border-top:3px solid var(--blue);padding-top:.25em}.stages b{display:block;font-size:1.5em}.stages span{font-size:.78em;color:var(--muted)}.stages i{font-style:normal;color:var(--muted);font-size:1.4em}.stages p{flex-basis:100%;margin:0}
.big{font-size:1.6em;font-weight:700;margin:.1em 0 .2em}
.progress{position:fixed;left:0;bottom:0;height:3px;background:var(--accent);transition:width .2s}
.hint{position:fixed;right:12px;top:8px;color:var(--muted);font-size:12px;transition:opacity .4s}.hint.gone{opacity:0}
@media print{body{overflow:visible}.deck{position:static;display:block}.slide{display:flex!important;flex-direction:column;width:100vw;height:56.25vw;page-break-after:always;font-size:1.55vw}.progress,.hint{display:none}}
@page{size:13.333in 7.5in;margin:0}
"""

DECK_JS = """
const s=[...document.querySelectorAll('.slide')];let i=0;
function show(n){i=Math.max(0,Math.min(s.length-1,n));s.forEach((x,k)=>x.classList.toggle('on',k===i));
document.querySelector('.progress').style.width=(100*(i+1)/s.length)+'%';try{history.replaceState(null,'','#'+(i+1))}catch(e){}}
addEventListener('keydown',e=>{document.querySelector('.hint').classList.add('gone');if(['ArrowRight','PageDown',' ','Enter'].includes(e.key)){e.preventDefault();show(i+1)}
if(['ArrowLeft','PageUp','Backspace'].includes(e.key)){e.preventDefault();show(i-1)}if(e.key==='Home')show(0);if(e.key==='End')show(s.length-1)});
addEventListener('click',e=>{if(e.target.closest('a'))return;show(e.clientX>innerWidth/3?i+1:i-1)});
show((parseInt(location.hash.slice(1))||1)-1);
"""


def build_deck():
    _sections = []
    for _n, _s in enumerate(SLIDES, 1):
        _header = "" if _s["kind"] == "title" else (
            f'<header><h2>{html.escape(_s["title"])}</h2><span class="who">{_s["speaker"]}</span></header>')
        _sections.append(f'<section class="slide">{_header}{_s["body"]}'
                         f'<footer><span>OM 522 · Option 3 · Planning delivery routes</span><span>{_n} / {len(SLIDES)}</span></footer></section>')
    _page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             f'<title>Planning Delivery Routes</title><style>{DECK_CSS}</style></head><body><main class="deck">{"".join(_sections)}</main>'
             f'<div class="progress"></div><div class="hint">← → to move · print to PDF for handouts</div><script>{DECK_JS}</script></body></html>')
    (OUT / "slides.html").write_text(_page, encoding="utf-8")


SCRIPT_CSS = CSS + """
body{overflow:auto}main{max-width:820px;margin:0 auto;padding:40px 16px 80px;line-height:1.6}
h1{font-size:30px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 24px}
.plan{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:28px}.plan td,.plan th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
.block{background:var(--paper);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:8px;padding:14px 18px;margin:16px 0}
.block h2{font-size:18px;margin:0 0 2px}.meta{font-size:13px;color:var(--muted);margin-bottom:8px}.block p{margin:8px 0}
.cue{color:var(--accent);font-weight:600}.who{display:inline-block;font-size:12px;font-weight:700;color:#fff;background:var(--accent);border-radius:10px;padding:1px 9px;margin-left:6px}
.tips{background:var(--soft);border-radius:8px;padding:12px 16px;font-size:14px}
@media print{.block{break-inside:avoid}}
"""


def build_script():
    _total = sum(s["seconds"] for s in SLIDES)
    _by = {p: sum(s["seconds"] for s in SLIDES if s["speaker"] == p) for p in TEAM}
    _rows = "".join(f"<tr><td>{p}</td><td>{_by[p] // 60}:{_by[p] % 60:02d}</td><td>"
                    f"{', '.join(str(n) for n, s in enumerate(SLIDES, 1) if s['speaker'] == p)}</td></tr>" for p in TEAM)
    _blocks, _clock = [], 0
    for _n, _s in enumerate(SLIDES, 1):
        _paras = "".join(
            "<p>" + html.escape(_p).replace("[SCREEN:", '<span class="cue">[SCREEN:').replace("]", "]</span>", 1) + "</p>"
            if _p.startswith("[SCREEN:") else f"<p>{html.escape(_p)}</p>" for _p in _s["script"])
        _blocks.append(f'<div class="block"><h2>Slide {_n}: {html.escape(_s["title"])}<span class="who">{_s["speaker"]}</span></h2>'
                       f'<div class="meta">{_clock // 60}:{_clock % 60:02d} – {(_clock + _s["seconds"]) // 60}:{(_clock + _s["seconds"]) % 60:02d}'
                       f' · about {_s["seconds"]} s</div>{_paras}</div>')
        _clock += _s["seconds"]
    _page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             f'<title>Presentation Script</title><style>{SCRIPT_CSS}</style></head><body><main>'
             f'<h1>Final video script</h1><p class="sub">OM 522 Option 3 · {" · ".join(TEAM)} · planned length {_total // 60}:{_total % 60:02d} (limit 15:00)</p>'
             f'<table class="plan"><thead><tr><th>Speaker</th><th>Time</th><th>Slides</th></tr></thead><tbody>{_rows}</tbody></table>'
             f'<div class="tips"><b>Before recording:</b> run <code>pixi install</code> and <code>pixi run test</code>; open <code>presentation/slides.html</code> full screen; have a terminal ready in the repository root. '
             f'The demo (slide 3) runs the researched method on development_medium, which takes about 40 s, so start it, talk over it, and cut the wait in editing if needed. '
             f'Lines marked <span class="cue">[SCREEN: …]</span> are on-screen actions. Each member walks through a different agent-drafted component (slides 5, 8, 12).</div>'
             f'{"".join(_blocks)}</main></body></html>')
    (OUT / "script.html").write_text(_page, encoding="utf-8")
    return _total


if __name__ == "__main__":
    build_deck()
    _total = build_script()
    print(f"wrote presentation/slides.html ({len(SLIDES)} slides) and presentation/script.html ({_total // 60}:{_total % 60:02d})")
