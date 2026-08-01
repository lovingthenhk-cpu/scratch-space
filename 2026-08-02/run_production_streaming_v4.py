"""
2026-08-02: direct continuation of 2026-08-01's Part S
(`../2026-08-01/run_production_streaming_v3.py`), addressing homework item
(b) from that session's "next steps" list in PROGRESS.md:

    "choose_k_for_memory_budget's k selection logic may not be optimal --
    s=21 got stuck at A=40 even with the raised 700s/A limit, worth
    checking by hand whether s=21 is genuinely harder than its neighbors
    or whether the k-selection is just leaving time on the table."

FINDING (see bench_materialize_memory.py + REPORT.md Part T for the full
table): s=21 is NOT intrinsically harder than s=19/20/22/... at A=40 -- it's
the same order of magnitude. The real problem is that
MEM_ITEM_BUDGET=2,000,000 (unchanged since 2026-07-29, chosen back then with
zero empirical basis, just "seemed conservative") was far too small. Hand
tabulating comb() sizes for k=1..s-1 at s=19..26, A=40 shows the materialized
side sitting at MEM_ITEM_BUDGET's cap forces a very lopsided split (e.g.
s=21,A=40: k=7 gives mat=6.58e5 but forces stream=8.19e8, ~910s) when a much
more balanced k is available almost for free (k=9: mat=6.91e6, stream=
1.41e8, ~10x fewer streamed items) IF the budget is allowed to grow past 2e6.

We benchmarked (bench_materialize_memory.py, run in fresh subprocesses per
the 2026-07-30 lesson about ru_maxrss contamination) the actual bytes/item
of the materialized index dict across several (s,A,k) combinations spanning
~9e5 to ~1.4e7 items: consistently ~158-183 bytes/item, no degradation at
the larger end (no evidence of a hash-resize cliff in this range). At
~180 bytes/item (rounding up for safety), 15,000,000 items is ~2.7 GB in the
worst case seen in our target (s,A) range. Two of these processes running
concurrently (our now-standard --half {A,B} pattern) could in the worst
case (both hitting their peak simultaneously) use ~5.4 GB against the
sandbox's 8 GB cap -- comfortable margin (~2.5 GB) for Python/OS baseline
and the smaller non-worst-case items most (s,A) pairs actually produce.
This raises MEM_ITEM_BUDGET 2,000,000 -> 15,000,000 (7.5x). One real
timed test (s=21, A=40, k chosen under the new budget) measured 125.3s wall
time against an old-budget stop threshold of "won't even start because
estimated 909.8s > 700s limit" -- i.e. this single fix alone unblocks the
exact case that stalled all of 2026-08-01's Part S run for s=21.

Two more additive (non-algorithmic) changes from v3, both permitted by the
freed-up time budget the above fix creates:
  1. MEM_ITEM_BUDGET 2,000,000 -> 15,000,000 (this file's main change).
  2. PER_A_TIME_LIMIT 700s -> 900s, PER_S_TIME_BUDGET 1500s -> 2200s: with
     each A now taking a fraction of the old wall time, the old thresholds
     would leave a lot of the raised MEM_ITEM_BUDGET's benefit on the table
     (stopping early even though the *actual* time-per-A dropped a lot).
  3. Still the same 2-core split pattern via --half {A,B}, standard since
     2026-08-01 (see PROGRESS.md "environment notes").

No change to the search algorithm itself, the target
(q=5, T_5 map, n1 = 4 mod 5), or the exhaustiveness guarantee -- k only
changes how the SAME exact shape space is partitioned into a materialized
half and a streamed half; every shape in [s, A_max] is still checked
exactly once either way. This is purely a runtime/memory tuning fix.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 15_000_000          # was 2_000_000 in v3 -- see module docstring
EMPIRICAL_RATE = 1_000_000            # measured today ~1.126e6/s on the streamed side (s=21,A=40,k=9); keep a little margin below that
PER_A_TIME_LIMIT = 900.0              # was 700.0
PER_S_TIME_BUDGET = 2200.0            # was 1500.0

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

with open("../2026-08-01/production_streaming_v3_results_merged.json") as f:
    prev = json.load(f)["results"]

# Resume s=19..26 from where v3 stopped. s=21 has A_max_reached=null (got
# stuck before completing even A=40) so resume AT its stated A_min, not
# A_min+1 -- this time it should actually get through it (see docstring).
RESUME_PLAN = []
for s in [19, 20, 21, 22, 23, 24, 25, 26]:
    rec = prev[str(s)]
    if rec["A_max_reached"] is None:
        a_start = rec["A_min"]
    else:
        a_start = rec["A_max_reached"] + 1
    RESUME_PLAN.append((s, a_start))
# New s values, extending the frontier further than any prior session
# (2026-07-29..08-01 covered s=9..26). Start each at A=s (minimum possible).
NEW_PLAN = [(s, s) for s in [27, 28]]
FULL_PLAN = RESUME_PLAN + NEW_PLAN

# split across the two halves: alternate assignment (even index -> A, odd -> B)
if HALF == "A":
    PLAN = [p for i, p in enumerate(FULL_PLAN) if i % 2 == 0]
else:
    PLAN = [p for i, p in enumerate(FULL_PLAN) if i % 2 == 1]

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
            stop_reason = f"stopping s={s}: cumulative ACTUAL time {elapsed_s:.1f}s > budget {PER_S_TIME_BUDGET}s"
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

    with open(f"production_streaming_v4_results_{HALF}.json", "w") as f:
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
