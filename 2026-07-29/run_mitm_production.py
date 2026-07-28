"""
Production MITM exhaustive sweep for the q=5, h=4 mod 5 (n=9 mod 10) open
cycle question (Santos 2020, arXiv:2005.00346, Remark 3 / Table 1 -- the
"congruence class 33 mod 40" / n = 4+5*lambda, lambda odd, i.e. n = 9 mod 10
in T_5 terms; see REPORT.md for full derivation/citation correction).

For each s (number of odd terms), sweeps A = s, s+1, s+2, ... exhaustively
(every A, no skipping) using mitm_search_one_A, and STOPS increasing A for
that s once a single-A computation takes longer than PER_A_TIME_LIMIT
seconds OR the cumulative time spent on this s exceeds PER_S_TIME_BUDGET --
whichever comes first. This makes the sweep self-calibrating: it uses
whatever A_max is affordable for the given s within the time budget, and
logs exactly what was covered (so the final report can state precise,
honest bounds, not aspirational ones).

Every candidate that survives the modular divisibility + residue check is
independently re-verified by forward simulation (_forward_reconstruct_and_check
in mitm_cycle_search.py) before being counted as a real hit.
"""
import json
import sys
import time
from math import comb

from mitm_cycle_search import mitm_search_one_A

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

PER_A_TIME_LIMIT = 90.0     # stop growing A for this s once one A costs more than this
PER_S_TIME_BUDGET = 240.0   # stop growing A for this s once cumulative time exceeds this
S_LIST = [10, 11, 12, 13, 14, 15, 16, 17, 18, 9]  # s=9 last: revisit/extend beyond yesterday's A<=45

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
    while True:
        t_a0 = time.time()
        hits, n1c, n2c = mitm_search_one_A(Q, s, A, TARGET_RESIDUE, TARGET_MOD)
        dt_a = time.time() - t_a0
        equiv = comb(A - 1, s - 1)
        per_s_equiv += equiv
        per_s_hits.extend(hits)
        last_A_completed = A
        elapsed_s = time.time() - t_s0
        print(f"  s={s:3d} A={A:4d}  dt={dt_a:7.2f}s  |S1|={n1c:11,d} |S2|={n2c:11,d} "
              f"equiv={equiv:.3e}  cum_equiv={per_s_equiv:.3e}  hits_this_A={len(hits)} "
              f"cum_time_this_s={elapsed_s:7.1f}s", flush=True)
        if hits:
            print(f"  !!! HIT FOUND: {hits}", flush=True)
        if dt_a > PER_A_TIME_LIMIT:
            print(f"  stopping s={s}: single-A time {dt_a:.1f}s > limit {PER_A_TIME_LIMIT}s", flush=True)
            break
        if elapsed_s > PER_S_TIME_BUDGET:
            print(f"  stopping s={s}: cumulative time {elapsed_s:.1f}s > budget {PER_S_TIME_BUDGET}s", flush=True)
            break
        A += 1

    results[s] = {
        "A_min": s,
        "A_max_reached": last_A_completed,
        "total_shapes_equivalent": per_s_equiv,
        "hits": per_s_hits,
        "wall_time_s": time.time() - t_s0,
    }
    grand_total_equiv += per_s_equiv
    grand_hits.extend(per_s_hits)
    print(f"=== s={s} done: A in [{s},{last_A_completed}], "
          f"{per_s_equiv:.3e} shapes-equivalent, {results[s]['wall_time_s']:.1f}s, "
          f"hits={per_s_hits} ===", flush=True)

    # persist incrementally so a partial run is still recoverable
    with open("mitm_results.json", "w") as f:
        json.dump({
            "results": {str(k): v for k, v in results.items()},
            "grand_total_equiv": grand_total_equiv,
            "grand_hits": grand_hits,
            "elapsed_total_s": time.time() - t_grand0,
        }, f, indent=2, default=str)

print(f"\n\nGRAND TOTAL: {grand_total_equiv:.3e} shapes-equivalent checked across "
      f"s={S_LIST}, total wall time {time.time()-t_grand0:.1f}s", flush=True)
print(f"GRAND HITS: {grand_hits}", flush=True)
