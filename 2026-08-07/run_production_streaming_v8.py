"""
2026-08-07: direct continuation of 2026-08-05's top-priority item #1 for
next session ("次回セッションの最優先候補"): actually raise the MAIN
PRODUCTION script's MEM_ITEM_BUDGET from 15,000,000 to 18,000,000 (not
just a small isolated probe) and push all ten s in [9,18] as far as this
new budget naturally allows.

BACKGROUND: 2026-08-05's concurrent_budget_probe.py already established,
via a REAL 2-process concurrent run of the two heaviest newly-unlocked
cells (s=14,A=58) and (s=16,A=48), that MEM_ITEM_BUDGET=18,000,000 is safe
under concurrent 2-process load (combined peak RSS ~3.91 GiB, well under
the ~7.84 GiB sandbox ceiling). That probe deliberately used the two
single heaviest cells as a stress test, but did NOT run either of them (or
s=9/s=11, the other two cells the formula said would unlock) as part of an
actual production sweep to their new natural ceiling, and did not verify
what happens across many A steps in a row for those s.

BEFORE writing this script, a dry-run projection was done with the SAME
choose_k_for_memory_budget()/comb() formulas the production script uses
(see project_18M.py in this directory), starting from each s's confirmed
2026-08-05 natural ceiling under the OLD 15,000,000 budget:

    s= 9: 144 -> 150 (6 more A steps, ~2839.7s projected)  [MOVES]
    s=10:  99 -> 99  (0 more steps -- still not unlocked at 18M)
    s=11:  78 -> 81  (3 more A steps, ~605.2s projected)   [MOVES]
    s=12:  72 -> 72  (0 more steps)
    s=13:  58 -> 58  (0 more steps)
    s=14:  57 -> 58  (1 more A step, ~752.5s projected)    [MOVES]
    s=15:  51 -> 51  (0 more steps)
    s=16:  47 -> 48  (1 more A step, ~350.3s projected)    [MOVES]
    s=17:  47 -> 47  (0 more steps)
    s=18:  44 -> 44  (0 more steps)

So under 18,000,000, only s=9, 11, 14, 16 actually move (consistent with
2026-08-05's probe, which identified exactly these 4 cells as newly
unlocked); s=10,12,13,15,17,18 remain exactly at their 15,000,000 natural
ceiling -- raising the budget by this increment does not help them yet.
Total projected single-core sequential CPU time for the 4 movers:
~4547.8s (~75.8 min), but since 10,12,13,15,17,18 need NO computation
(the formula alone re-confirms their ceiling, deterministically -- the
same choose_k_for_memory_budget()/comb() logic the production run itself
uses, no shortcuts), this run only actually EXECUTES s=9, 11, 14, 16.

Balancing the two cores: s=9 alone (~2839.7s projected) vs {s=11, s=14,
s=16} together (~605.2+752.5+350.3 = ~1708.0s projected) is the best
2-way split found (putting s=9 with anything else makes that half heavier
than putting it alone).

MEM_ITEM_BUDGET = 18,000,000 (raised from 15,000,000 -- this IS the
change under test this session). PER_A_TIME_LIMIT unchanged at 900s. No
change to the search algorithm itself (byte-for-byte copy of
../2026-08-05/mitm_streaming.py), the target (q=5, T_5 map, n1 = 4 mod 5),
or the exhaustiveness guarantee -- only the memory-budget constant that
governs which k (materialized/streamed split) is chosen for a given
(s, A).

monitor_memory.py is run alongside this script (separately, via nohup) to
record the REAL combined RSS of both halves throughout -- this is the
first time 18,000,000 is exercised in the actual multi-A-step production
path (not just a single hand-picked cell), so real measurement (not just
the extrapolation from the single-cell probe) is warranted before trusting
this budget for future sessions.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 18_000_000     # RAISED from 15,000,000 -- see docstring
EMPIRICAL_RATE = 1_000_000       # same conservative estimate used since 2026-08-02
PER_A_TIME_LIMIT = 900.0         # unchanged: natural per-A ceiling
SAFETY_WALL_CAP = 7200.0         # generous safety net; see docstring

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

# 2026-08-05 natural ceilings under the OLD 15,000,000 budget (resume points).
CEILINGS_15M = {9: 144, 10: 99, 11: 78, 12: 72, 13: 58, 14: 57, 15: 51, 16: 47, 17: 47, 18: 44}

# Only these move under 18,000,000 (confirmed by project_18M.py dry run above).
if HALF == "A":
    PLAN = [(9, CEILINGS_15M[9] + 1)]
else:
    PLAN = [(11, CEILINGS_15M[11] + 1), (14, CEILINGS_15M[14] + 1), (16, CEILINGS_15M[16] + 1)]

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

    with open(f"production_streaming_v8_results_{HALF}.json", "w") as f:
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
