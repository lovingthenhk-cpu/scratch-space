"""
2026-08-13: direct continuation of 2026-08-09 REPORT.md "次回やろうとしていたこと"
priority 1. 2026-08-09 raised PER_A_TIME_LIMIT 900s->1200s (MEM_ITEM_BUDGET
UNCHANGED at 21,000,000, proven safe) and advanced s=10 (99->104), s=12
(72->75), s=15 (51->52), s=17 (47->48); s=18 gained nothing (next step
needed ~1203.3s, just over the 1200s limit).

project_time_limit_extension_v2.py (this folder) re-ran the SAME projection
methodology starting from the UPDATED post-2026-08-09 ceilings and scanned
1250/1300/1350/1400/1500s. Findings:
  - 1400s is the last candidate where every NEW step's materialized-side
    saturation stays comfortably in the previously-safe range (max seen:
    s=10 18.7%, s=12 53.5%, s=15 33.6%, s=18 25.6% -- all well under the
    88-98% saturation band that made the 24,000,000 MEM_ITEM_BUDGET probe
    dangerous on 2026-08-08/08-09).
  - 1500s pushes s=17's next step to 88.8% saturation -- squarely inside
    the danger band identified on 2026-08-08/08-09 for a DIFFERENT knob
    (MEM_ITEM_BUDGET), but the underlying risk (near-full materialized-side
    memory) is the same regardless of which knob produced it. Per the
    2026-08-09 lesson ("stop before 3rd risky measurement, not after"),
    1500s is deliberately NOT attempted this session; a future session
    could probe it in isolation with monitor_memory.py running throughout,
    but should not default straight into a full production sweep at that
    saturation level.
  - Chose PER_A_TIME_LIMIT = 1400.0 (up from 1200.0). Total single-core
    projected CPU time from the updated ceilings: 6509.8s (108.5 min).
    Balanced 2-way split (same balancing logic as 2026-08-07..09's v8-v10
    scripts -- minimize the max of the two group sums): {s=10,s=18}
    (3817.2s proj.) vs {s=12,s=15,s=17} (2692.5s proj., s=17 contributes 0
    -- its next step needs ~1471s > 1400s limit, so it is included only in
    case the real per-A time undershoots the projection, per the recurring
    observation that EMPIRICAL_RATE=1,000,000 items/s tends to be ~20-30%
    pessimistic vs measured wall time).

MEMORY SAFETY: MEM_ITEM_BUDGET is UNCHANGED at 21,000,000 (the value
proven safe across a full production sweep on 2026-08-08 and reconfirmed
2026-08-09, real combined peak ~2.27-4.26 GiB depending on which (s,A)
pairs are actually touched). monitor_memory.py runs alongside this script
as a matter of course (2026-08-02/08-09 lesson: verify empirically, never
trust a projection alone), even though this specific change is a pure
wall-clock knob with no a priori OOM mechanism.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 21_000_000     # UNCHANGED from 2026-08-08/09 (already proven safe)
EMPIRICAL_RATE = 1_000_000
PER_A_TIME_LIMIT = 1400.0        # RAISED from 1200.0 -- see docstring; MEMORY budget untouched
SAFETY_WALL_CAP = 6000.0         # per-s cumulative actual-time abort (real time, not projection)

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

# Ceilings actually reached as of 2026-08-09 (production_streaming_v10_results_merged.json).
CEILINGS_AFTER_0809 = {9: 156, 10: 104, 11: 83, 12: 75, 13: 59, 14: 59, 15: 52, 16: 49, 17: 48, 18: 44}

if HALF == "A":
    PLAN = [(10, CEILINGS_AFTER_0809[10] + 1), (18, CEILINGS_AFTER_0809[18] + 1)]
else:
    PLAN = [
        (12, CEILINGS_AFTER_0809[12] + 1),
        (15, CEILINGS_AFTER_0809[15] + 1),
        (17, CEILINGS_AFTER_0809[17] + 1),
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

    with open(f"production_streaming_v11_results_{HALF}.json", "w") as f:
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
