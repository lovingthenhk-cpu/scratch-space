"""
2026-08-09: addresses 2026-08-08 REPORT.md "次回" priority 2 (previously
untouched): s=10,12,15,17,18 have been stuck at the SAME (s,A) ceiling for
five straight sessions (2026-08-04..08-08) even as MEM_ITEM_BUDGET rose
15M->18M->21M, because -- as saturation_analysis_24M.py's "21M" column
shows -- their next A step's materialized side is comfortably within the
21,000,000 budget (12.7%-60.1% saturation) but the STREAMED side estimate
exceeds PER_A_TIME_LIMIT=900s. These five are TIME-limited, not
MEMORY-limited, at the CURRENT (already-safe) 21,000,000 budget.

project_time_limit_extension.py projected several PER_A_TIME_LIMIT values
without running anything. PER_A_TIME_LIMIT=1200s (up from 900s, a modest
+33% wall-clock increase, MEM_ITEM_BUDGET UNCHANGED at 21,000,000) gives a
good balance: s=10 advances 5 steps (99->104), s=12 advances 3 (72->75),
s=15 advances 1 (51->52), s=17 advances 1 (47->48); s=18 gains nothing at
this limit (its next step needs ~1203s, just over) and is left for a future
session with a slightly higher limit. Grand total projected single-core
time ~10750s; split across 2 cores as {s=10 alone, ~5280s} / {s=12,15,17
together, ~5470s} -- well balanced (checked with the SAME balancing logic
as 2026-08-07/08's v8/v9 scripts: put the single largest s alone if it
exceeds half the grand total, otherwise group).

MEMORY SAFETY: unlike 2026-08-08's MEM_ITEM_BUDGET-raise experiments, this
change carries NO new OOM risk -- MEM_ITEM_BUDGET stays at 21,000,000 (the
value already proven safe across a full production sweep on 2026-08-08,
real combined peak ~4.26 GiB). The saturation of every NEW step reached
under PER_A_TIME_LIMIT=1200s tops out at 60.1% (s=17,A=48) -- see
project_time_limit_extension.py's detailed per-step printout -- far below
the 88-98% saturation levels that made the 24,000,000 probe (see
concurrent_probe_repeat_results.json, reproduced today at max combined RSS
7.12 GiB, 90.7% of the ~7.84 GiB ceiling -- WORSE than 2026-08-08's 6.83
GiB, confirming 24,000,000 is genuinely unsafe, not a one-off) dangerous.
monitor_memory.py runs alongside this script regardless, as a matter of
course (see PROGRESS.md environment notes -- always verify empirically,
never trust a projection alone).
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 21_000_000     # UNCHANGED from 2026-08-08 (already proven safe)
EMPIRICAL_RATE = 1_000_000
PER_A_TIME_LIMIT = 1200.0        # RAISED from 900.0 -- see docstring; MEMORY budget untouched
SAFETY_WALL_CAP = 7200.0

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

# 2026-08-08 natural ceilings under the (unchanged) 21,000,000 budget.
CEILINGS_21M = {9: 156, 10: 99, 11: 83, 12: 72, 13: 59, 14: 59, 15: 51, 16: 49, 17: 47, 18: 44}

if HALF == "A":
    PLAN = [(10, CEILINGS_21M[10] + 1)]
else:
    PLAN = [
        (12, CEILINGS_21M[12] + 1),
        (15, CEILINGS_21M[15] + 1),
        (17, CEILINGS_21M[17] + 1),
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
                            f"[NATURAL ceiling under current PER_A_TIME_LIMIT]")
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

    with open(f"production_streaming_v10_results_{HALF}.json", "w") as f:
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
