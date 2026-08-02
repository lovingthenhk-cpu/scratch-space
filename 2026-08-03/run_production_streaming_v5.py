"""
2026-08-03: catch-up pass on s=9..18, addressing homework candidate (d)
from 2026-08-02's PROGRESS.md "next steps" list:

    "(d) s=9〜18(2026-07-29で止まったところ)の延長"

WHY THIS, AND NOT ANOTHER STEP ON s=19..28: s=19..28's frontier (A up to
42-44, see ../2026-08-02/production_streaming_v4_results_merged.json) is
now expensive enough that a SINGLE further A-step per s costs ~900-2700s
each (checked by hand with choose_k_for_memory_budget before writing this
script) -- advancing all 10 of those s values by even one more A would cost
on the order of 2.5 hours of wall-clock (two cores, worst-of-the-two-halves)
for a comparatively small amount of NEW shape coverage (10 more shapes,
each combinatorially large but still just +1 in A per s).

By contrast, s=9..18 have not been touched since 2026-07-29
(`../2026-07-29/mitm_results.json`), which used the ORIGINAL non-streaming
MITM (`../2026-07-29/mitm_cycle_search.py`) with much smaller ad hoc
per-A/per-s time budgets (90s/240s) than what we now know is safe
(15,000,000-item MEM_ITEM_BUDGET, established 2026-08-02 with an actual
bytes/item measurement). Because comb(A-1, s-1) grows only polynomially in
A for FIXED small s (vs. combinatorial explosion as s itself grows), these
small-s values can be pushed MUCH further in A per unit of compute time
than the current s=19..28 frontier can advance by even one step. This is a
better use of a bounded compute budget: more new exhaustively-verified
shape coverage per CPU-second.

No change to the search algorithm (same `mitm_streaming.py`, byte-for-byte
copy of 2026-08-02's file), the target (q=5, T_5 map, n1 = 4 mod 5), or the
exhaustiveness guarantee. Only the (s, A) region being extended changes.

MEM_ITEM_BUDGET is kept at 15,000,000, same as 2026-08-02 -- this session
does NOT raise it further, because a hand-computed worst-case check (see
REPORT.md) shows the theoretical two-process-simultaneous-peak envelope at
higher budgets (e.g. 20,000,000+) leaves uncomfortably thin margin against
this sandbox's actual `free -h` total (7.8 GiB, not a clean 8 GB). Instead
of guessing higher, `monitor_memory.py` runs alongside this script for the
first time to sample REAL concurrent RSS + MemAvailable throughout the run
-- see REPORT.md for what that log shows and whether it justifies raising
the budget in a future session.

PER_S_TIME_BUDGET is set lower than 2026-08-02's 2200s (to 1200s) --
deliberately, so that with 5 s-values per half the worst-case per-half wall
time stays in the ~90-150 min range the last several sessions have
established as a normal single-session compute allocation, rather than the
~2.5h a literal "let every s run until its budget" policy would produce
here (many of s=9..18's *natural* completion times -- i.e. running until
the NEXT A's estimate exceeds the 900s per-A limit -- are several thousand
seconds; see the hand-computed table in REPORT.md). This means several of
the more expensive s values (9, 10, 12, 14, 15, 17) will stop control-timed
rather than exhausting every A up to their natural 900s-per-A ceiling --
that remaining headroom is recorded per-s in the results JSON's
stop_reason and PROGRESS.md's "next steps", not silently dropped.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 15_000_000     # unchanged from 2026-08-02; see docstring
EMPIRICAL_RATE = 1_000_000       # same conservative estimate used since 2026-08-02
PER_A_TIME_LIMIT = 900.0         # unchanged from 2026-08-02 (standard per-A ceiling)
PER_S_TIME_BUDGET = 1200.0       # lower than 2026-08-02's 2200s; see docstring

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

with open("../2026-07-29/mitm_results.json") as f:
    prev = json.load(f)["results"]

# Resume s=9..18 from where the ORIGINAL (non-streaming) 2026-07-29 run
# stopped -- that run used a much smaller ad hoc time budget, not a
# MEM_ITEM_BUDGET-based stopping rule, so every one of these has
# A_max_reached set (none got stuck mid-A the way 2026-08-01's s=21 did).
RESUME_PLAN = []
for s in [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
    rec = prev[str(s)]
    a_start = rec["A_max_reached"] + 1
    RESUME_PLAN.append((s, a_start))

# split across the two halves: alternate assignment (even index -> A, odd -> B)
if HALF == "A":
    PLAN = [p for i, p in enumerate(RESUME_PLAN) if i % 2 == 0]
else:
    PLAN = [p for i, p in enumerate(RESUME_PLAN) if i % 2 == 1]

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
                            f"(materialized side {mn:.3e} items, within {MEM_ITEM_BUDGET:,} budget)")
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

        if elapsed_s > PER_S_TIME_BUDGET:
            stop_reason = f"stopping s={s}: cumulative ACTUAL time {elapsed_s:.1f}s > budget {PER_S_TIME_BUDGET}s (control-timed, not natural exhaustion -- see docstring)"
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

    with open(f"production_streaming_v5_results_{HALF}.json", "w") as f:
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
