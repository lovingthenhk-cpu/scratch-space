"""
2026-07-30: production MITM sweep using the memory-efficient streaming
implementation (`mitm_streaming.py`), extending 2026-07-29's
`run_mitm_production.py` coverage.

Same target as every day since 2026-07-27: q=5, T_5 map, does a nontrivial
cycle exist with n1 = 4 (mod 5) (Santos 2020, arXiv:2005.00346, Remark 3's
open congruence class)?

WHY A SEPARATE SCRIPT INSTEAD OF JUST RE-RUNNING 2026-07-29's WITH A BIGGER
A_max: yesterday's `mitm_search_one_A` always uses a SYMMETRIC k=(s+1)//2
split and materializes BOTH halves fully -- for s=9..18 that was fine (never
the memory bottleneck, only ever the 90s/240s TIME budget that stopped it),
but pushing to LARGER s (this file's actual new contribution: s=19..22, not
attempted before) makes even the SYMMETRIC split's item count large enough
to risk OOM before the time budget would have stopped it anyway. Today's
`mitm_search_one_A_streaming` (see that file's docstring for the full
memory-vs-time trade story, including a documented FAILED first attempt)
lets us pick an intentionally asymmetric k via `choose_k_for_memory_budget`
that keeps peak memory bounded (materialized side <= MEM_ITEM_BUDGET items,
empirically ~140-180 bytes/item -> a few hundred MB at most) regardless of
s, at the cost of a slower per-A search (the streamed side is bigger than a
symmetric split's would be) -- an intentional trade given we have much more
slack on wall-clock (background execution) than on the fixed 8 GB ceiling.

CRITICAL: `mitm_search_one_A_streaming` has NO internal deadline check --
once called for a given A it runs to completion, however long that takes.
So THIS script must pre-filter using the (cheap, `math.comb`-based) item
count *estimate* for the chosen k, and refuse to even attempt an A whose
estimated streamed-side size would blow the time budget, rather than
launching the call and hoping. EMPIRICAL_RATE below is a conservative
measured items/sec (see REPORT.md Part K benchmarks: streaming measured
~1.0-1.4M items/s across k=5,6,8 trials on this session's 2-core box;
using 700k/s here to leave real margin, consistent with the project's
running "measure on THIS box, don't trust yesterday's number" policy from
../PROGRESS.md's environment notes).
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 2_000_000     # materialized-side item cap (~ a few hundred MB, see REPORT.md)
EMPIRICAL_RATE = 700_000        # conservative items/sec, streamed-side cost driver
PER_A_TIME_LIMIT = 150.0        # stop growing A for this s once one A is estimated to cost more than this
PER_S_TIME_BUDGET = 420.0       # stop growing A for this s once cumulative ACTUAL time exceeds this
S_LIST = [19, 20, 21, 22]       # new territory: 2026-07-29's run_mitm_production.py covered s=9..18 only

results = {}
grand_total_equiv = 0
grand_hits = []
t_grand0 = time.time()

for s in S_LIST:
    print(f"\n=== s={s} starting ===", flush=True)
    t_s0 = time.time()
    A = s
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
                            f"(materialized side {mn:.3e} items, within {MEM_ITEM_BUDGET:,} budget)")
            print(f"  {stop_reason}", flush=True)
            break

        t_a0 = time.time()
        hits, n1c, n2c = mitm_search_one_A_streaming(Q, s, A, TARGET_RESIDUE, TARGET_MOD, k=k)
        dt_a = time.time() - t_a0
        equiv = comb(A - 1, s - 1)   # what brute force / symmetric MITM would have paid, for comparability
        per_s_equiv += equiv
        per_s_hits.extend(hits)
        last_A_completed = A
        elapsed_s = time.time() - t_s0
        print(f"  s={s:3d} A={A:4d} k={k:3d}  dt={dt_a:7.2f}s (est {est_time:6.1f}s)  "
              f"n1={n1c:12,d} n2={n2c:12,d}  brute_equiv={equiv:.3e}  cum_equiv={per_s_equiv:.3e}  "
              f"hits_this_A={len(hits)}  cum_time_this_s={elapsed_s:7.1f}s", flush=True)
        if hits:
            print(f"  !!! HIT FOUND: {hits}", flush=True)

        if elapsed_s > PER_S_TIME_BUDGET:
            stop_reason = f"stopping s={s}: cumulative ACTUAL time {elapsed_s:.1f}s > budget {PER_S_TIME_BUDGET}s"
            print(f"  {stop_reason}", flush=True)
            break
        A += 1

    results[s] = {
        "A_min": s,
        "A_max_reached": last_A_completed,
        "total_shapes_equivalent": per_s_equiv,
        "hits": per_s_hits,
        "wall_time_s": time.time() - t_s0,
        "stop_reason": stop_reason,
    }
    grand_total_equiv += per_s_equiv
    grand_hits.extend(per_s_hits)
    print(f"=== s={s} done: A in [{s},{last_A_completed}], "
          f"{per_s_equiv:.3e} brute-force-equivalent shapes, {results[s]['wall_time_s']:.1f}s, "
          f"hits={per_s_hits} ===", flush=True)

    with open("production_streaming_results.json", "w") as f:
        json.dump({
            "results": {str(k): v for k, v in results.items()},
            "grand_total_equiv": grand_total_equiv,
            "grand_hits": grand_hits,
            "elapsed_total_s": time.time() - t_grand0,
        }, f, indent=2, default=str)

print(f"\n\nGRAND TOTAL: {grand_total_equiv:.3e} brute-force-equivalent shapes checked across "
      f"s={S_LIST}, total wall time {time.time()-t_grand0:.1f}s", flush=True)
print(f"GRAND HITS: {grand_hits}", flush=True)
