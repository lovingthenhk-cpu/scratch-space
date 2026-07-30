"""
2026-07-31: direct continuation of 2026-07-30's
`../2026-07-30/run_production_streaming.py`.

Two changes from yesterday's run, both just "push the same knobs further",
no new algorithmic idea (that would be dishonest to claim -- the streaming
MITM machinery itself is unchanged, imported verbatim from
`mitm_streaming.py`, copied over from 2026-07-30):

  1. RESUME s=19..22 from where yesterday's per-A time-budget check made it
     stop (A=37 or 38), instead of restarting from A=s. Starting A for each
     s is read from `../2026-07-30/production_streaming_results.json`
     ("A_max_reached" + 1).
  2. Raise PER_A_TIME_LIMIT (150s -> 400s) and PER_S_TIME_BUDGET (420s ->
     900s). Yesterday's stopping reason was *always* "estimated time for
     the next A exceeds the budget", never an actual crash/OOM -- i.e. a
     self-imposed schedule limit, not a hard wall. Since this runs
     unattended in the background there is slack to spend more wall-clock
     per A before giving up on a given s.
  3. New territory: s=23, 24 (yesterday covered s=9..22; today extends by
     two more).

Same target as every session since 2026-07-27: q=5, T_5 map ((5n+1)/2 for
odd n, n/2 for even n), does a nontrivial cycle exist with
n1 = 4 (mod 5) (Santos 2020, arXiv:2005.00346, Remark 3's open congruence
class)? Still zero hits expected/hoped-for either way -- a hit would be
the actual headline result, its absence just extends the exhaustive-search
lower bound on any counterexample's cycle shape.
"""
import json
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 2_000_000
EMPIRICAL_RATE = 700_000
PER_A_TIME_LIMIT = 400.0
PER_S_TIME_BUDGET = 900.0

with open("../2026-07-30/production_streaming_results.json") as f:
    prev = json.load(f)["results"]

# (s, starting A)
RESUME_PLAN = [(s, prev[str(s)]["A_max_reached"] + 1) for s in [19, 20, 21, 22]]
NEW_PLAN = [(s, s) for s in [23, 24]]
PLAN = RESUME_PLAN + NEW_PLAN

results = {}
grand_total_equiv = 0
grand_hits = []
t_grand0 = time.time()

for s, A_start in PLAN:
    print(f"\n=== s={s} starting from A={A_start} ===", flush=True)
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
                            f"(materialized side {mn:.3e} items, within {MEM_ITEM_BUDGET:,} budget)")
            print(f"  {stop_reason}", flush=True)
            break

        t_a0 = time.time()
        hits, n1c, n2c = mitm_search_one_A_streaming(Q, s, A, TARGET_RESIDUE, TARGET_MOD, k=k)
        dt_a = time.time() - t_a0
        equiv = comb(A - 1, s - 1)
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
        "A_min": A_start,
        "A_max_reached": last_A_completed,
        "total_shapes_equivalent": per_s_equiv,
        "hits": per_s_hits,
        "wall_time_s": time.time() - t_s0,
        "stop_reason": stop_reason,
    }
    grand_total_equiv += per_s_equiv
    grand_hits.extend(per_s_hits)
    print(f"=== s={s} done: A in [{A_start},{last_A_completed}], "
          f"{per_s_equiv:.3e} brute-force-equivalent shapes, {results[s]['wall_time_s']:.1f}s, "
          f"hits={per_s_hits} ===", flush=True)

    with open("production_streaming_v2_results.json", "w") as f:
        json.dump({
            "results": {str(k): v for k, v in results.items()},
            "grand_total_equiv": grand_total_equiv,
            "grand_hits": grand_hits,
            "elapsed_total_s": time.time() - t_grand0,
        }, f, indent=2, default=str)

print(f"\n\nGRAND TOTAL: {grand_total_equiv:.3e} brute-force-equivalent shapes checked, "
      f"total wall time {time.time()-t_grand0:.1f}s", flush=True)
print(f"GRAND HITS: {grand_hits}", flush=True)
