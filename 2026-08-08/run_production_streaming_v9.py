"""
2026-08-08: direct continuation of 2026-08-07's top-priority item for next
session ("次回セッションの最優先候補"): actually raise the MAIN PRODUCTION
script's MEM_ITEM_BUDGET from 18,000,000 to 21,000,000 (not just a probe)
and push all five newly-unlocked s ([9,11,13,14,16]) to their natural
ceiling under this new budget.

BACKGROUND: 2026-08-07's concurrent_budget_probe_21M.py already established,
via a REAL 2-process concurrent run of the two heaviest newly-unlocked
cells at 21M ((s=13,A=59) and (s=16,A=49)), that MEM_ITEM_BUDGET=21,000,000
is safe under concurrent 2-process load (combined peak RSS ~4.49 GiB, ~57%
of the ~7.84 GiB sandbox ceiling). That probe did NOT run any of the five
cells as part of an actual production sweep across many A steps, and did
not push s=9/s=11/s=14 (the other three formula-predicted movers) at all.

BEFORE writing this script, a dry-run projection was done with the SAME
choose_k_for_memory_budget()/comb() formulas the production script uses
(see project_21M.py in ../2026-08-07/, re-run here for this session's
record -- see project_21M_rerun_log.txt), starting from each s's confirmed
2026-08-07 natural ceiling under the OLD 18,000,000 budget:

    s= 9: 150 -> 156 (6 more A steps, ~3494.7s projected)  [MOVES]
    s=10:  99 -> 99  (0 more steps -- still not unlocked at 21M)
    s=11:  81 -> 83  (2 more A steps, ~493.9s projected)   [MOVES]
    s=12:  72 -> 72  (0 more steps)
    s=13:  58 -> 59  (1 more A step, ~154.1s projected)    [MOVES]
    s=14:  58 -> 59  (1 more A step, ~886.3s projected)    [MOVES]
    s=15:  51 -> 51  (0 more steps)
    s=16:  48 -> 49  (1 more A step, ~445.9s projected)    [MOVES]
    s=17:  47 -> 47  (0 more steps)
    s=18:  44 -> 44  (0 more steps)

So under 21,000,000, only s=9, 11, 13, 14, 16 actually move (consistent
with 2026-08-07's probe, which identified exactly these 5 cells as newly
unlocked); s=10,12,15,17,18 remain exactly at their 18,000,000 natural
ceiling. Total projected single-core sequential CPU time for the 5 movers:
~5474.9s (~91.3 min).

Balancing the two cores: s=9 alone (~3494.7s) is already more than half of
the 5474.9s grand total, so no 2-way split can bring the max half below
~3494.7s regardless of how the other four are grouped. Following the same
reasoning as 2026-08-07 (and 2026-08-05 before it), s=9 is kept alone on
one core; the other four movers (11,13,14,16) share the other core
(493.9+154.1+886.3+445.9 = ~1980.2s projected), which will finish well
before half A and simply idle -- acceptable, this is the best achievable
balance without splitting a single s's A-range across processes (which the
current script structure does not support).

MEM_ITEM_BUDGET = 21,000,000 (raised from 18,000,000 -- this IS the change
under test this session). PER_A_TIME_LIMIT unchanged at 900s. No change to
the search algorithm itself (byte-for-byte copy of
../2026-08-07/mitm_streaming.py), the target (q=5, T_5 map, n1 = 4 mod 5),
or the exhaustiveness guarantee -- only the memory-budget constant that
governs which k (materialized/streamed split) is chosen for a given
(s, A).

monitor_memory.py is run alongside this script (separately, via nohup) to
record the REAL combined RSS of both halves throughout -- this is the
first time 21,000,000 is exercised across a real multi-A-step production
sweep for all 5 movers together (2026-08-07's probe only exercised the
single heaviest PAIR of A-steps, not a full sweep), so real measurement is
still warranted before fully trusting this budget for future sessions.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 21_000_000     # RAISED from 18,000,000 -- see docstring
EMPIRICAL_RATE = 1_000_000       # same conservative estimate used since 2026-08-02
PER_A_TIME_LIMIT = 900.0         # unchanged: natural per-A ceiling
SAFETY_WALL_CAP = 7200.0         # generous safety net; see docstring

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

# 2026-08-07 natural ceilings under the OLD 18,000,000 budget (resume points).
CEILINGS_18M = {9: 150, 10: 99, 11: 81, 12: 72, 13: 58, 14: 58, 15: 51, 16: 48, 17: 47, 18: 44}

# Only these move under 21,000,000 (confirmed by project_21M.py dry run, see docstring).
if HALF == "A":
    PLAN = [(9, CEILINGS_18M[9] + 1)]
else:
    PLAN = [
        (11, CEILINGS_18M[11] + 1),
        (13, CEILINGS_18M[13] + 1),
        (14, CEILINGS_18M[14] + 1),
        (16, CEILINGS_18M[16] + 1),
    ]

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

    with open(f"production_streaming_v9_results_{HALF}.json", "w") as f:
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
