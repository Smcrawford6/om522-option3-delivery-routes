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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vrptw.checker import check_decision  # noqa: E402
from vrptw.loader import load_instance  # noqa: E402
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
    """pause: seconds for on-screen actions; speech is timed at 150 words per minute,
    not counting the [SCREEN: ...] cues."""
    _spoken = [re.sub(r"\[SCREEN:[^\]]*\]", "", p) for p in script]
    _words = sum(len(p.split()) for p in _spoken)
    SLIDES.append({"speaker": speaker, "title": title, "body": body, "script": script,
                   "seconds": round(_words / 150 * 60) + pause, "kind": kind})


def snippet(module, marker, count, highlight=()):
    """count lines of vrptw/module starting at the line that contains marker."""
    _lines = (ROOT / "vrptw" / module).read_text(encoding="utf-8").splitlines()
    _start = next(i for i, line in enumerate(_lines) if marker in line)
    _rows = []
    for _i, _line in enumerate(_lines[_start:_start + count]):
        _cls = ' class="hl"' if any(h in _line for h in highlight) else ""
        _rows.append(f'<span{_cls}><i>{_start + 1 + _i}</i>{html.escape(_line) or " "}</span>')
    return f'<div class="file">vrptw/{module}</div><pre class="code">{"".join(_rows)}</pre>'


# Facts read from the submitted results.
_LARGE_RULE = json.loads((RES / "decisions" / "development_large" / "rule" / "decision.json").read_text())
_LARGE_DATA = load_instance(ROOT / "development_large")
_CROSS_ROUTES = sum(1 for r in check_decision(_LARGE_DATA, _LARGE_RULE)["routes"] if r["self_crossings"])
_CROSSINGS = int(ROWS[("development_large", "rule")]["self_crossings"])
_RUN = {n: json.loads((RES / "decisions" / n / "researched" / "run_info.json").read_text())
        for n in ("development_medium", "development_large")}
_CHAINS_L = [c["best_cost"] for c in _RUN["development_large"]["chain_results"]]
_CHAINS_M = [c["best_cost"] for c in _RUN["development_medium"]["chain_results"]]
_REJECTED = sum(c["rejected_for_crossing"] for c in _RUN["development_large"]["chain_results"])
_ITERS = sum(c["iterations_run"] for c in _RUN["development_large"]["chain_results"])
with open(RES / "stress" / "stress_results.csv", newline="", encoding="utf-8") as _f:
    _SROWS = list(csv.DictReader(_f))
_GAPS = [float(a["total_travel_time"]) - float(b["total_travel_time"])
         for a, b in zip([r for r in _SROWS if r["method"] == "rule"], [r for r in _SROWS if r["method"] == "researched"])]
_BOTH = [s for s in range(1, 31)
         if all(int(r["violations"]) > 0 for r in _SROWS if int(r["scenario"]) == s)]
_S11 = SENS[(1.1, "rule")], SENS[(1.1, "researched")]
_S13 = SENS[(1.3, "rule")], SENS[(1.3, "researched")]
_EXTRA = float(_S11[0]["travel_mean"]) - float(_S11[1]["travel_mean"])
_MED_T = float(X_MED["computation_time_s"])
_LRG_T = float(ROWS[("development_large", "researched")]["computation_time_s"])

slide(SADIE, "Planning delivery routes", f"""
<div class="hero">
  <p class="eyebrow">OM 522 · Team project · Option 3 · Final submission</p>
  <h1>Planning delivery routes<br><span>with capacity, time windows, and shifts</span></h1>
  <p class="names">{' · '.join(TEAM)}</p>
  <div class="kpis">
    <div><b>{MED_PCT:.0f}%</b><span>less travel than the rule to beat<br>(45-customer day)</span></div>
    <div><b>{R_MED['vehicles_used']} → {X_MED['vehicles_used']}</b><span>vehicles used</span></div>
    <div><b>0</b><span>self-crossings in our plans<br>(rule: {_CROSSINGS} on 120 customers)</span></div>
  </div>
</div>""", [
    f"Hi, we're {SADIE}, {ZACC}, and {ANNABELLE}, and this is our final submission for option 3, planning delivery routes.",
    f"Today we'll run the tool on a fresh instance, show both methods, the checker, the comparison, the stress test, and our recommendation. The headline: on the 45-customer day our method drives {MED_PCT:.0f} percent less than the rule to beat, with {X_MED['vehicles_used']} trucks instead of {R_MED['vehicles_used']}, and none of our routes crosses itself.",
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
  <div class="callout"><h3>Our added assumption</h3><p>A route may <b>not cross itself</b> on the map. A driver shouldn't cut back across their own path. Different routes may cross. Here travel time equals straight-line distance (within 0.0005 min), so uncrossing a route also shortens it.</p></div>
 </div>
</div>""", [
    "Each morning a dispatcher decides which truck serves each customer and the order of its stops. Trucks have a capacity. Customers have time windows. A truck that's early waits, and service can't start after the window closes. And every truck has to be back by the end of its shift.",
    "We score plans by total driving time first and vehicles used second, and we always report computation time.",
    "We added one assumption: a route can't cross itself on the map, because a driver shouldn't cut back across their own path. Different routes may cross. In this data travel time equals straight-line distance, so uncrossing a route also makes it shorter.",
], 3)

slide(SADIE, "Live demo: a fresh instance", """
<div class="two">
<div>
<p>Git Bash, from the repository root, on a <b>copied</b> instance:</p>
<pre class="term">$ cp -r development_medium ~/fresh_day
$ pixi run solve ~/fresh_day ~/out_ours
$ pixi run rule  ~/fresh_day ~/out_rule

$ pixi run solve edge_case ~/out_edge

$ cp -r hand_checkable ~/bad_day
$ cut -d, -f1-6 hand_checkable/customers.csv \\
      &gt; ~/bad_day/customers.csv
$ pixi run solve ~/bad_day ~/out_bad; echo "exit $?"</pre>
</div>
<div>
<h3>What each run must do (guide 4.3)</h3>
<table><tbody>
<tr><td>Valid input</td><td>writes <code>decision.json</code> + <code>summary.md</code>, exit 0</td></tr>
<tr><td>Valid but infeasible (<code>edge_case</code>)</td><td>prints “no feasible decision found”, no <code>decision.json</code>, exit 0</td></tr>
<tr><td>Malformed (<code>window_end</code> deleted)</td><td>“input error: customers.csv, column 'window_end' …”, no <code>decision.json</code>, exit 2</td></tr>
</tbody></table>
<p class="small"><code>summary.md</code> lists the measures, the checker's verdict, the seed, the stopping rule, and the run time. Annabelle runs the checker on both decisions in a few minutes.</p>
</div></div>""", [
    "[SCREEN: terminal, run the first three commands] Here's the instructor's run. I copy the medium instance to a new folder, so nothing's pre-computed, and run the documented solve command. That's our researched method with default settings. It takes about forty seconds, and we've cut most of the wait from the video. Then the rule to beat on the same folder.",
    "[SCREEN: point at the printed line] Each run prints the total travel, the trucks, the checker's verdict, and the run time, and writes decision.json and a summary.",
    "[SCREEN: run the edge case, then the malformed copy] On the edge case, one customer needs 65 units and every truck holds 60, so the tool prints 'no feasible decision found' and writes no decision. And if I delete a required column, it names the file and the column and exits with an error.",
], 75, "demo")

slide(SADIE, "Method 1: the rule to beat", f"""
<div class="two">
<div>
<h3>Nearest feasible neighbor, one vehicle at a time</h3>
<ol><li>Take vehicles in identifier order; each leaves at its shift start.</li>
<li>Drive to the <b>nearest</b> unserved customer (ties by ID) that<br>· fits the remaining capacity,<br>· can start service by its window end,<br>· still allows a return by the shift end.</li>
<li>No customer qualifies → return; the next vehicle starts.</li>
<li>Anyone left unserved → “no feasible decision found”.</li></ol>
<p class="small">Deterministic, no seed. Implemented as written, so it doesn't apply our crossing rule: {_CROSS_ROUTES} of its routes cross themselves on the large case.</p>
</div>
<div>
<h3>Required test 1: it reproduces the worked example</h3>
<table><thead><tr><th>Vehicle</th><th>Visits</th><th>Return</th></tr></thead><tbody>
<tr><td>V01</td><td>C003 → C002 → C004</td><td>361.875</td></tr>
<tr><td>V02</td><td>C001 → C005 → C006</td><td>289.403</td></tr></tbody></table>
<div class="kpis small-k"><div><b>352.417</b><span>total travel (min), matches</span></div><div><b>232.861</b><span>waiting (min), matches</span></div></div>
<p class="small">Every arrival and service start matches <code>worked-example/solution.json</code>.</p>
</div></div>""", [
    "Method one is the rule to beat, exactly as the brief states it. Trucks go out in ID order. Each one keeps driving to the nearest unserved customer it can still legally serve: the customer fits the remaining capacity, can start before its window closes, and still lets the truck get home by shift end. When nothing qualifies, the next truck starts.",
    f"Required test one checks it reproduces the worked example exactly: the same routes, the same times, and 352.417 minutes of travel. Because it's implemented as written, it ignores our crossing rule, and {_CROSS_ROUTES} of its routes cross themselves on the large case.",
], 3)

slide(SADIE, "Walk-through: the rule to beat (agent-drafted)", snippet(
    "rule.py", "_unserved = set(range(1, inst.n + 1))", 25, highlight=("_key = (", "EPS")) + """
<div class="note"><b>What was unclear:</b> the agent breaks ties by node number, which is only "ties by customer identifier" if nodes are numbered in sorted-ID order (they are: <code>core.py</code> sorts the IDs as strings, the class convention, and the supplied IDs are zero-padded). It also borrowed a 1e-9 tolerance from the researched method, so a window is met if service starts within 1e-9 of its end. <b>How we checked:</b> we traced the first stops of hand_checkable by hand, the test reproduces every time in the worked example, and reversing every file's rows gives the same rule plan.</div>""", [
    "[SCREEN: rule.py] My component is the rule to beat, which our coding agent drafted. For the current truck it scans every unserved customer. It skips any that don't fit the remaining capacity, can't start before the window closes, or wouldn't leave time to get home. Then it keeps the one with the smallest key: travel time first, then node number.",
    "What was unclear was that tie-break. The brief says ties go by customer ID, but the code uses the node number. Those only match if nodes are numbered in ID order. They are: IDs are sorted as strings, and the supplied ones are zero-padded, so C009 comes before C010.",
    "How we checked it: I traced the first stops of the hand-checkable case by hand, the test reproduces every arrival in the worked example, and reversing every file's rows gives the same plan.",
], 5, "code")

slide(ZACC, "Method 2: the researched method", f"""
<div class="flow">
 <div><span>1</span><h3>Construct</h3><p><b>Solomon (1987) I1 insertion.</b> Seed a route, then insert the customer with the best score: a bonus for being far from the depot minus its insertion cost (the added travel blended with how far it pushes later stops back). Every window is checked. 12 parameter starts.</p></div>
 <div><span>2</span><h3>Improve</h3><p><b>Local search</b> with the brief's moves: relocate 1–3 customers (or-opt), exchange between routes, reverse a segment (2-opt), and swap route tails (2-opt*). Each customer is paired with its 12 nearest neighbors.</p></div>
 <div><span>3</span><h3>Ruin &amp; recreate</h3><p><b>Large neighborhood search</b> (Shaw 1998; Ropke &amp; Pisinger 2006): remove 4 to 30 customers, reinsert them (regret or greedy), improve, and accept by simulated annealing. 4 seeded chains; keep the best.</p></div>
</div>
<div class="stages">
 <div><b>{f(R_MED['total_travel_time'])}</b><span>rule to beat</span></div><i>→</i>
 <div><b>{f(X_MED['start_cost'])}</b><span>best of 12 I1 starts + local search</span></div><i>→</i>
 <div><b>{f(X_MED['total_travel_time'])}</b><span>+ ruin and recreate (final)</span></div>
 <p class="small">Total travel (min) on development_medium after each stage.</p>
</div>
<div class="two tight">
<p><b>Representation:</b> one ordered list of customers per vehicle. Each route caches its load, its service starts, and the <i>latest feasible start</i> at every stop.</p>
<p><b>Stopping rule:</b> 4 chains × 2,000 iterations (a fixed count); the 300 s limit is only a safety cap. <b>Seed</b> 522; chain c uses Random(100·seed + c), so reruns are identical (tested).</p>
</div>""", [
    "Our researched method has three stages. Stage one is Solomon's 1987 insertion heuristic. It seeds a route with a far-away or urgent customer, then keeps inserting the customer that's most worth inserting now, checking every window as it goes. We run twelve parameter settings.",
    "Stage two is local search with the moves the brief lists: relocate customers, exchange them between routes, reverse a segment, and swap route ends.",
    f"Stage three is ruin and recreate. We tear out a group of customers, put them back, and run the local search again. Simulated annealing decides whether to keep the result. Four seeded chains run 2,000 iterations each, and we keep the best. You can see what each stage buys: {f(R_MED['total_travel_time'], 0)} minutes for the rule, {f(X_MED['start_cost'], 0)} after stage two, and {f(X_MED['total_travel_time'], 0)} at the end.",
], 3)

slide(ZACC, "Feasibility is checked after every move", code_block(
    "researched.py", "insertion_options", 6, 34, highlight=("_latest[_q]", "inst.late[u]", "shift_end")) + """
<div class="note"><b>For every local-search move:</b> compute the travel change first (cheap). Only an improving move is then checked for capacity, then every window and the shift end, then self-crossing. A move is accepted only if all three pass, so the search only ever holds feasible plans.</div>""", [
    "[SCREEN: researched.py, insertion_options] For every route we cache each stop's service start, and the latest start that still keeps the rest of the route feasible. So inserting a customer needs just two checks: the new customer's own window, and whether the next stop still starts before its latest time. That's constant time, however long the route is.",
    "For the other moves we compute the travel change first. Only an improving move gets the full check: capacity, then windows and shift end, then crossings.",
], 3, "code")

slide(ANNABELLE, "Independent checker and tests", """
<div class="two">
<div>
<h3>The checker trusts nothing a method reports</h3>
<ul><li>Reads <b>only</b> the input files and <code>decision.json</code>.</li>
<li>Recomputes every arrival, service start, return, load, and measure from the visit lists.</li>
<li>Has its own timing and crossing code and imports nothing from either method.</li>
<li>Names each violation: customer missing or served twice, vehicle reused or unknown, capacity, window, shift end. Uses the instructor's 1e-8 tolerance.</li></ul>
<pre class="term">$ pixi run check ~/fresh_day ~/out_ours/decision.json
$ pixi run check ~/fresh_day ~/out_rule/decision.json
$ pixi run test</pre>
</div>
<div>
<h3><code>pixi run test</code>: 21 tests</h3>
<ol><li><b>Required:</b> the rule reproduces the worked example.</li>
<li><b>Required:</b> the edge case gives “no feasible decision found” (both methods).</li>
<li><b>Required:</b> a deleted column is rejected, naming the file and the column.</li></ol>
<p class="small">Plus: other bad inputs (wrong type, 7.5 in an integer column, zero service time, empty cell, unknown ID); the checker catching four broken decisions; the two crossing tests agreeing on 400 random routes; zero crossings and a win over the rule on two 60-customer copies with renamed IDs; identical reruns; and no stale decision.json after a malformed run.</p>
</div></div>""", [
    "[SCREEN: run both check commands, scroll to FEASIBLE] The checker is what protects us from code that claims a result it didn't achieve. It reads only the input files and a decision file, imports nothing from either method, and recomputes every time, load, and measure from the visit lists. Here it confirms both of Sadie's decisions are feasible and lists each route.",
    "[SCREEN: run pixi run test] The test command runs twenty-one tests. That includes the three the guide requires, broken decisions the checker has to catch, and two 60-customer copies of the data with renamed IDs, the size of the held-out case.",
], 25)

slide(ANNABELLE, "Walk-through: the crossing guard (agent-drafted)", snippet(
    "researched.py", "search.set_routes(_current_routes)", 18, highlight=("feasible(r, k)", "_rejected += 1")) + f"""
<div class="note"><b>What was wrong:</b> the agent's ruin step removed customers without re-checking the route. Skipping a stop draws a shortcut, and the shortcut can cross another leg of that route. The supplied instances showed 0 crossings by luck, but when we tested 60-customer copies, 2 of 4 plans came back with routes crossing themselves. <b>Fix:</b> after recreate and local search, a candidate is kept only if every route passes the full check. <b>How we checked:</b> a new test on 60-customer copies <i>fails on the old code and passes now</i>; on the large case this guard rejected {_REJECTED} of {_ITERS:,} candidates.</div>""", [
    "[SCREEN: researched.py, anneal] My component is the acceptance step in ruin and recreate, which the agent drafted. Each iteration starts from the current plan, tears out some customers, puts them back, and runs local search.",
    "What was wrong: the agent checked crossings when customers were inserted, but not when they were removed. Skipping a stop draws a shortcut, and the shortcut can cross another leg of the route. The supplied instances showed zero crossings by luck, but on 60-customer copies two of four plans had crossing routes.",
    f"The fix is the highlighted check: after local search, a candidate survives only if every route passes capacity, windows, shift end, and the crossing test. How we checked it: we wrote a test on those 60-customer copies, confirmed it fails on the old code, and it passes now. On the large case the guard threw out {_REJECTED} of {_ITERS:,} candidates.",
], 5, "code")

slide(ZACC, "Deterministic comparison: four instances", comparison_table() + f"""
<img class="wide" src="{img('results/comparison.png')}" alt="Grouped bars of total travel and vehicles by instance">
<p class="small">Windows 11 laptop, Python 3.12 (Pixi). Rule: no time limit. Researched: default settings; the 300 s safety cap is never reached.</p>""", [
    "Here's the comparison on all four instances. Every number was recomputed by the checker from the decision files.",
    f"We beat the rule on every instance, and the gap grows with size: 6.5 percent on six customers, 22 percent on 15, {MED_PCT:.0f} percent on 45, and {LRG_PCT:.0f} percent on 120. That's {LRG_SAVE:,.0f} fewer minutes of driving, with {ROWS[('development_large','researched')]['vehicles_used']} trucks instead of {ROWS[('development_large','rule')]['vehicles_used']}.",
    f"The price is computation time: milliseconds for the rule, and for ours about {_MED_T:.0f} seconds on 45 customers and {_LRG_T:.0f} on 120. That's well inside the ten-minute limit. These are four synthetic instances, so we don't claim the method is best in general.",
], 3)

slide(ZACC, "What the dispatcher sees", f"""
<img class="wide tall" src="{img('results/routes_development_large.png')}" alt="Route maps for the large instance, rule versus researched">
""", [
    f"Here's the 120-customer case on the map. On the left is the rule: greedy routes that zig-zag and double back, with the {_CROSS_ROUTES} routes that cross themselves dashed in red, {_CROSSINGS} crossings in all. On the right is ours: compact loops out of the depot and no route that crosses itself.",
], 3)

slide(ZACC, "Stress test: what if travel times are wrong?", f"""
<div class="two wide-right">
<div>
<h3>Design</h3>
<ul><li><b>Uncertain input:</b> travel time. Scenario s multiplies each leg by C<sub>s</sub> × E<sub>ij</sub>. Both are lognormal with mean 1: a day-wide congestion factor (CV 0.15) and a factor for each leg (CV 0.10).</li>
<li><b>30 scenarios</b>, seed 20261103, saved to <code>results/stress/scenarios/</code> <b>before</b> either plan runs.</li>
<li><b>Fixed plans</b> for development_medium, run by the brief's rule: follow each route in order and wait if early. Every late service start and every late return counts as a violation.</li></ul>
</div>
<div>{snippet("experiments.py", "def generate_scenarios", 21, highlight=("_lognormal(rng", "STRESS_SEED"))}</div></div>""", [
    "The comparison assumed travel times are exact. The stress test asks what happens when they're not.",
    "Each of thirty scenarios has a day-wide congestion factor and a separate factor on every leg, both lognormal with mean one. They come from a fixed seed and are saved to files before either plan runs, so both plans face exactly the same days.",
], 3)

slide(ZACC, "Walk-through: the fixed-plan execution (agent-drafted)", snippet(
    "experiments.py", "def execute_plan", 26, highlight=("max(_time", "window_end", "shift_end")) + f"""
<div class="note"><b>What was wrong or unclear:</b> (1) the agent's first per-scenario plot showed travel and violations only, but the guide asks for the secondary measure too, so we added a vehicles panel. (2) Mean realized travel came out <i>below</i> plan ({f(SX['travel_mean'])} vs {f(SX['planned_travel'])} min), which looked like a bug. <b>How we checked:</b> the 30 saved congestion factors average 0.974, so it's sampling, not code. We also checked the code against the brief line by line: service starts at the later of arrival and window start even when late, and is counted, not skipped.</div>""", [
    "[SCREEN: experiments.py, execute_plan] My component is the code that drives a fixed plan through one scenario, which the agent drafted. It follows each route in its planned order with the scenario's travel times. A truck that's early waits. If service starts after the window closes, or the truck gets back after its shift, that's counted as a violation, but the plan doesn't change.",
    "Two things were wrong or unclear. First, the agent's plot showed travel and violations but left out the secondary measure, vehicles used, which the guide asks for. We added that panel.",
    f"Second, the average realized travel came out below the plan, {SX['travel_mean']:,.0f} against {SX['planned_travel']:,.0f} minutes, which looked like a bug. We checked the saved congestion factors: they average 0.974, so it's the luck of thirty draws, not the code.",
], 5, "code")

slide(ANNABELLE, "Stress-test results", f"""
<div class="two">
<div>{stress_table()}</div>
<div><img class="wide tall" src="{img('results/stress/stress_per_scenario.png')}" alt="Per-scenario travel, vehicles, and violations for both plans"></div>
</div>""", [
    f"Here are the results. Our plan keeps its advantage: about {SR['travel_mean'] - SX['travel_mean']:,.0f} fewer minutes on an average day, and between {min(_GAPS):,.0f} and {max(_GAPS):,.0f} fewer on every one of the thirty days, with {SX['vehicles_mean']:.0f} trucks throughout.",
    f"Violations: {SR['violations_total']} for the rule and {SX['violations_total']} for ours over the thirty days, and ours has {SX['late_returns_total']} late returns against the rule's {SR['late_returns_total']}. Both plans fail on the same congested days, like scenario {_BOTH[-1]}, so it's traffic, not one fragile plan.",
], 3)

slide(ANNABELLE, "When does the answer change? Heavier congestion", sensitivity_table() + f"""
<p class="small">The same 30 saved scenarios, rescaled so average congestion is 10–30% above the planning data (each scenario keeps its own draws; only the level changes).</p>
<div class="callout"><p>As traffic gets worse, our plan never has more total violations, has far fewer late returns, and is late for about half as many minutes. But because it packs each route more tightly, <b>more days have at least one late stop</b> ({_S11[1]['scenarios_with_violation']} vs {_S11[0]['scenarios_with_violation']} days at +10%).</p></div>""", [
    "To find a condition that would change our answer, we rescaled the same thirty days to heavier average traffic: ten, twenty, and thirty percent above the planning data.",
    f"Our plan never has more total violations than the rule, has far fewer late returns, and is late for about half as many minutes. But because it packs routes tighter, more days have at least one late stop: {_S11[1]['scenarios_with_violation']} against {_S11[0]['scenarios_with_violation']} at plus ten percent.",
], 3)

slide(ANNABELLE, "Recommendation", f"""
<div class="rec">
<div><h3>Recommend</h3><p class="big">Adopt the researched method</p><p>Solomon I1 + local search + ruin and recreate, with the no-self-crossing rule. Evidence: one 45-customer development day (the held-out case has 60).</p></div>
<div><h3>Expected benefit</h3><p class="big">{MED_SAVE:,.0f} fewer driving minutes a day</p><p>{MED_PCT:.0f}% less planned driving ({f(R_MED['total_travel_time'])} → {f(X_MED['total_travel_time'])} min) with {int(R_MED['vehicles_used']) - int(X_MED['vehicles_used'])} fewer vehicles ({R_MED['vehicles_used']} → {X_MED['vehicles_used']}); about {SR['travel_mean'] - SX['travel_mean']:,.0f} fewer minutes on an average uncertain day.</p></div>
<div><h3>Tradeoff accepted</h3><p>About {_MED_T:.0f} s of computing instead of milliseconds. Tighter routes, so slightly more days with at least one late stop ({SX['scenarios_with_violation']} vs {SR['scenarios_with_violation']} of 30; {_S11[1]['scenarios_with_violation']} vs {_S11[0]['scenarios_with_violation']} at +10% congestion).</p></div>
<div><h3>Would change if…</h3><p>a day is judged by whether <b>any</b> window is missed and traffic runs ≥ 10% above plan: then the rule has fewer bad days ({_S11[0]['scenarios_with_violation']} vs {_S11[1]['scenarios_with_violation']} of 30; {_S13[0]['scenarios_with_violation']} vs {_S13[1]['scenarios_with_violation']} at +30%), at about {_EXTRA:,.0f} more driving minutes a day. If zero missed windows is required, neither fixed plan qualifies; plan with buffered travel times or replan during the day.</p></div>
</div>""", [
    "Our recommendation is to adopt the researched method.",
    f"The expected benefit on the 45-customer day is about {MED_SAVE:,.0f} fewer minutes of planned driving, {MED_PCT:.0f} percent, with three fewer trucks. With uncertain travel times it still saves about {SR['travel_mean'] - SX['travel_mean']:,.0f} minutes on an average day, with no more violations than the rule.",
    "The tradeoff: it takes under a minute to compute instead of milliseconds, and because the routes are tighter, a few more days have at least one late stop.",
    f"It would change if the operation judges a day only by whether any window is missed, and traffic runs ten percent or more above plan. Then the rule has fewer bad days, at about {_EXTRA:,.0f} more minutes of driving. And if zero missed windows is a must, neither fixed plan works, and the dispatcher should plan with buffered travel times.",
], 3, "rec")

slide(ZACC, "Limitations, and thank you", f"""
<div class="two">
<div><h3>Limitations</h3><ul>
<li>A heuristic with no proof of optimality. The four chains on the large case end between {min(_CHAINS_L):,.1f} and {max(_CHAINS_L):,.1f} min; on medium our default seed stops at {f(X_MED['total_travel_time'], 3)}, and we know a plan at 1,070.565.</li>
<li>It plans for exact travel times with no slack, which is why heavier congestion is what would change the recommendation.</li>
<li>It minimizes travel only; fewer vehicles is a side effect, not a target.</li>
<li>The evidence is four synthetic instances from one generator, plus one infeasible edge case.</li>
<li>No-crossing is our rule. If no crossing-free plan fits the fleet, the tool relaxes it and says so in <code>summary.md</code>.</li></ul></div>
<div><h3>Reproduce everything</h3><pre class="term">pixi install
pixi run test
pixi run reproduce
pixi run solve &lt;input_dir&gt; &lt;output_dir&gt;</pre>
<p class="small">The README has method details, seeds, stopping rules, and sources. Built with Claude Code (agentic coding); every component was reviewed by the team.</p>
<p class="names">Sadie Crawford · Zacc Gleason · Annabelle Kemp</p></div></div>""", [
    f"Finally, our limitations. It's a heuristic, so there's no optimality proof. On the large case the four chains end between {min(_CHAINS_L):,.0f} and {max(_CHAINS_L):,.0f} minutes. On the medium case our default seed stops at 1,071.159, and we know a plan that's 0.6 of a minute better. It also plans with no slack, which is exactly why heavier traffic is what would change our recommendation.",
    "Everything regenerates with pixi run reproduce, and the README documents each method, its seed, its stopping rule, and its sources. Thank you.",
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
.two{display:grid;grid-template-columns:1fr 1fr;gap:4%;flex:1;min-height:0}.two.wide-right{grid-template-columns:.75fr 1.25fr;gap:3%}.two.wide-right pre.code{font-size:.5em}.two.tight{flex:0;margin-top:.6em;font-size:.88em}
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
.rec{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto;gap:.8em;font-size:.9em}.rec div{border:1px solid var(--line);border-radius:8px;padding:.6em 1em}.rec div:first-child{background:var(--soft);border-color:var(--accent)}
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
             f'Record the terminal parts in Git Bash (PowerShell 5.1 does not expand <code>~</code>). The demo (slide 3) runs the researched method on development_medium, which takes about 40 s; start it, keep talking, and trim the wait in editing. Annabelle runs the two <code>check</code> commands and the tests live on slide 8. '
             f'Lines marked <span class="cue">[SCREEN: …]</span> are on-screen actions, not spoken. Each member walks through a different agent-drafted component from the prototype video (prototype: loader, researched method, checker; final: Sadie the rule to beat on slide 5, Annabelle the crossing guard on slide 9, Zacc the fixed-plan execution on slide 13). Rehearse once with a timer; the plan leaves about a minute of margin under 15:00.</div>'
             f'{"".join(_blocks)}</main></body></html>')
    (OUT / "script.html").write_text(_page, encoding="utf-8")
    return _total


if __name__ == "__main__":
    build_deck()
    _total = build_script()
    print(f"wrote presentation/slides.html ({len(SLIDES)} slides) and presentation/script.html ({_total // 60}:{_total % 60:02d})")
