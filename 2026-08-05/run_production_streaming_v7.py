"""
2026-08-05: direct continuation of 2026-08-03/2026-08-04's s=9,10,12
catch-up (top priority item #1 in 2026-08-04's PROGRESS.md "次に何を試す
つもり"), resuming from ../2026-08-04/production_streaming_v6_results_merged.json.

WHY THIS AND NOT A NEW TOPIC: 2026-08-04 doubled PER_S_TIME_BUDGET from
1200s to 2400s and still left s=9 (A=111->129), s=10 (A=84->92), and
s=12 (A=64->70) short of their NATURAL ceiling under the unchanged
MEM_ITEM_BUDGET=15,000,000 (all three stopped on the *control-timed*
PER_S_TIME_BUDGET, not on the PER_A_TIME_LIMIT=900s natural-ceiling check).
All other s in [9..18] (11,13,14,15,16,17,18) already confirmed at their
natural ceiling as of 2026-08-04.

BEFORE writing any run today, a dry-run projection was done (same
choose_k_for_memory_budget()/comb() formulas the production script uses,
no new estimation logic) starting from 2026-08-04's actual stopping point
(A=130, 93, 71 respectively) to find out how much MORE work each of these
three needs to reach ITS OWN natural ceiling (first A where the streamed
side estimate exceeds PER_A_TIME_LIMIT=900s):

    s= 9: A 130->144 (15 more A steps, ~4873.5s of streamed-side work) then
          natural ceiling at A=145 (est 10231.0s, correctly rejected)
    s=10: A  93-> 99 ( 7 more A steps, ~5028.9s) then natural ceiling at
          A=100 (est 927.0s, just over the 900s limit)
    s=12: A  71-> 72 ( 2 more A steps, ~1648.4s) then natural ceiling at
          A=73 (est 969.4s)

Unlike 2026-08-03/04 (which used a fixed, smaller PER_S_TIME_BUDGET and
accepted partial progress), this projection shows FULL natural completion
of all three is achievable in ~11550s of total CPU-time -- and splitting
across the 2 available cores as {s=9, s=12} on one half (~6521.9s) and
{s=10} alone on the other (~5028.9s) balances the two halves to within
~1500s of each other (better balance than any other 2-way grouping of
these three items), for a projected wall time of ~6521.9s (~109 min) on
the busier half. This is within the ~90-150 CPU-min/half norm this project
has used in prior sessions, so THIS session targets full natural
completion of s=9, 10, 12 rather than another partial-progress pass.

No change to the search algorithm (byte-for-byte copy of
../2026-08-04/mitm_streaming.py), the target (q=5, T_5 map, n1 = 4 mod 5),
the exhaustiveness guarantee, or MEM_ITEM_BUDGET (that stays at
15,000,000 for this main production run; the separate question of
verifying a HIGHER budget under real concurrent 2-process load is handled
in a distinct, smaller script today -- concurrent_budget_probe.py -- kept
out of this run for the same reason 2026-08-04 kept its budget probe
separate: don't add a second untested variable to a multi-hour job).

A generous safety wall-clock cap (SAFETY_WALL_CAP = 7200s per half) is
still kept in case the projection above is wrong (e.g. actual throughput
differs from the EMPIRICAL_RATE=1e6 items/s/core assumption) -- if hit,
the run stops early and records why, same convention as previous sessions.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 15_000_000     # unchanged; see docstring
EMPIRICAL_RATE = 1_000_000       # same conservative estimate used since 2026-08-02
PER_A_TIME_LIMIT = 900.0         # unchanged: natural per-A ceiling
SAFETY_WALL_CAP = 7200.0         # generous safety net; see docstring

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

with open("../2026-08-04/production_streaming_v6_results_merged.json") as f:
    prev = json.load(f)["results"]

# Resume s=9, 10, 12 from where 2026-08-04's run stopped.
TARGETS = [9, 10, 12]
RESUME_PLAN = {}
for s in TARGETS:
    rec = prev[str(s)]
    RESUME_PLAN[s] = rec["A_max_reached"] + 1

# split: {9, 12} on half A (heaviest + lightest, balances against {10} alone
# on half B), per the projection in the docstring above.
if HALF == "A":
    PLAN = [(9, RESUME_PLAN[9]), (12, RESUME_PLAN[12])]
else:
    PLAN = [(10, RESUME_PLAN[10])]

print(f"[half {HALF}] plan: {PLAN}", flush=True)

results = {}
grand_total_equiv = 0
grand_hits = []
t_grand0 = time.time()

for s, A_start in PLAN:
    print(f"\n=== [half {HALF}] s={s} starting from A={A_start} ===", flush=True)
    t_s0 = time.time()
    A = A_start
    per_s_equiv = 0
    per_s_hits = []
    last_A_completed = None
    stop_reason = None
    while True:
        k = choose_k_for_memory_budget(s, A, MEM_ITEM_BUDGET)
        max1 = A - (s - k)
        max2 = A - k
        c1 = comb(max1, k) if max1 >= k else 0
        c2 = comb(max2, s - k) if max2 >= (s - k) else 0
        mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
        est_time = mx / EMPIRICAL_RATE

        if est_time > PER_A_TIME_LIMIT:
            stop_reason = (f"stopping s={s} BEFORE A={A}: chosen k={k} estimated streamed-side "
                            f"{mx:.3e} items -> ~{est_time:.1f}s > limit {PER_A_TIME_LIMIT}s "
                            f"(materialized side {mn:.3e} items, within {MEM_ITEM_BUDGET:,} budget) "
                            f"[NATURAL ceiling under current MEM_ITEM_BUDGET]")
            print(f"  [half {HALF}] {stop_reason}", flush=True)
            break

        t_a0 = time.time()
        hits, n1c, n2c = mitm_search_one_A_streaming(Q, s, A, TARGET_RESIDUE, TARGET_MOD, k=k)
        dt_a = time.time() - t_a0
        equiv = comb(A - 1, s - 1)
        per_s_equiv += equiv
        per_s_hits.extend(hits)
        last_A_completed = A
        elapsed_s = time.time() - t_s0
        print(f"  [half {HALF}] s={s:3d} A={A:4d} k={k:3d}  dt={dt_a:7.2f}s (est {est_time:6.1f}s)  "
              f"n1={n1c:12,d} n2={n2c:12,d}  brute_equiv={equiv:.3e}  cum_equiv={per_s_equiv:.3e}  "
              f"hits_this_A={len(hits)}  cum_time_this_s={elapsed_s:7.1f}s", flush=True)
        if hits:
            print(f"  !!! HIT FOUND: {hits}", flush=True)

        if elapsed_s > SAFETY_WALL_CAP:
            stop_reason = (f"stopping s={s}: cumulative ACTUAL time {elapsed_s:.1f}s > SAFETY cap "
                            f"{SAFETY_WALL_CAP}s (projection was wrong or throughput lower than "
                            f"expected -- NOT natural exhaustion, see PROGRESS.md)")
            print(f"  [half {HALF}] {stop_reason}", flush=True)
            break
        A += 1

    results[s] = {
        "A_min": A_start,
        "A_max_reached": last_A_completed,
        "total_shapes_equivalent": per_s_equiv,
        "hits": per_s_hits,
        "wall_time_s": time.time() - t_s0,
        "stop_reason": stop_reason,
    }
    grand_total_equiv += per_s_equiv
    grand_hits.extend(per_s_hits)
    print(f"=== [half {HALF}] s={s} done: A in [{A_start},{last_A_completed}], "
          f"{per_s_equiv:.3e} brute-force-equivalent shapes, {results[s]['wall_time_s']:.1f}s, "
          f"hits={per_s_hits} ===", flush=True)

    with open(f"production_streaming_v7_results_{HALF}.json", "w") as f:
        json.dump({
            "half": HALF,
            "results": {str(k): v for k, v in results.items()},
            "grand_total_equiv": grand_total_equiv,
            "grand_hits": grand_hits,
            "elapsed_total_s": time.time() - t_grand0,
        }, f, indent=2, default=str)

print(f"\n\n[half {HALF}] GRAND TOTAL: {grand_total_equiv:.3e} brute-force-equivalent shapes checked, "
      f"total wall time {time.time()-t_grand0:.1f}s", flush=True)
print(f"[half {HALF}] GRAND HITS: {grand_hits}", flush=True)
