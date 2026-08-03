"""
2026-08-04: direct continuation of 2026-08-03's s=9..18 catch-up pass
(top priority item #2 in 2026-08-03's PROGRESS.md "次回やろうとしていたこと"),
resuming from where 2026-08-03 stopped (production_streaming_v5_results_merged.json)
instead of the much-older 2026-07-29 baseline.

WHY THIS AND NOT A NEW TOPIC: 2026-08-03's own PROGRESS.md explicitly flagged
that s=9, 10, 12 were cut off by the *control-timed* PER_S_TIME_BUDGET (1200s),
not by hitting their natural per-A ceiling (PER_A_TIME_LIMIT=900s) -- i.e.
there was known, quantified headroom left on exactly these three. Before
writing any code today, a dry-run projection was done using the *exact same*
choose_k_for_memory_budget()/comb() formulas the production script uses (no
new estimation logic), to find out how far s=9, 10, 12 (and the others) could
go if run to their natural completion under the CURRENT (unchanged,
2026-08-02-established) MEM_ITEM_BUDGET=15,000,000:

    s= 9: A 111->144 (34 more A steps, ~7991s of streamed-side work)
    s=10: A  84-> 99 (16 more A steps, ~8742s)
    s=11: A  77-> 78 ( 2 more A steps, ~ 327s)
    s=12: A  64-> 72 ( 9 more A steps, ~5175s)
    s=13: A  59-> 58 -- ALREADY at its natural ceiling under this budget (0 more)
    s=14: A  54-> 57 ( 4 more A steps, ~2002s)
    s=15: A  50-> 51 ( 2 more A steps, ~1595s)
    s=16: A  48-> 47 -- ALREADY at its natural ceiling under this budget (0 more)
    s=17: A  47-> 47 ( 1 more A step,  ~ 848s)
    s=18: A  45-> 44 -- ALREADY at its natural ceiling under this budget (0 more)

Running s=9, 10, and 12 all the way to their natural ceiling would cost
~7991+8742+5175 =~ 21908s (~365 CPU-minutes) by itself -- multiple hours even
split across 2 cores, well beyond the ~90-150 min/half norm this project has
settled into over the past several sessions. Rather than balloon session
length to chase 100% natural completion in one shot (previous sessions have
consistently made large-but-partial progress and left the remainder for next
time -- see e.g. 2026-08-01's s=21, 2026-08-02's frontier extension), this
session instead DOUBLES the per-s time budget from 2026-08-03's 1200s to
2400s (still well short of what full natural completion of s=9/10/12 would
need) and keeps the same two-core alternating-half split 2026-08-03 used.
This is expected to:
  - let s=13, 16, 18 confirm (cheaply, near-instantly) that they are still at
    their natural ceiling under the unchanged 15,000,000 budget (0 cost --
    the very first choose_k check already exceeds PER_A_TIME_LIMIT);
  - let s=11, 14, 15, 17 (whose remaining natural work is each under 2400s)
    run to FULL natural completion this session;
  - let s=9, 10, 12 (whose remaining natural work each exceeds 2400s) make
    substantial further progress without reaching their natural ceiling --
    the remainder is recorded per-s in stop_reason/PROGRESS.md for next time,
    same convention 2026-08-03 established.

No change to the search algorithm (byte-for-byte copy of 2026-08-03's
mitm_streaming.py), the target (q=5, T_5 map, n1 = 4 mod 5), the
exhaustiveness guarantee, or MEM_ITEM_BUDGET (raising that further, per
2026-08-03's Part X / next-steps item #4, is deliberately left as a separate,
smaller, more cautious experiment -- see raise_budget_probe.py in this same
directory -- rather than being bundled into this main production run, since
this run's whole point is to bank on the ALREADY-validated 15,000,000 budget
without adding a second untested variable to a multi-hour compute job).
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 15_000_000     # unchanged from 2026-08-02/03; see docstring
EMPIRICAL_RATE = 1_000_000       # same conservative estimate used since 2026-08-02
PER_A_TIME_LIMIT = 900.0         # unchanged from 2026-08-02/03 (standard per-A ceiling)
PER_S_TIME_BUDGET = 2400.0       # doubled from 2026-08-03's 1200s; see docstring

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

with open("../2026-08-03/production_streaming_v5_results_merged.json") as f:
    prev = json.load(f)["results"]

# Resume s=9..18 from where 2026-08-03's run stopped (not 2026-07-29's much
# older baseline -- that gap has already been closed).
RESUME_PLAN = []
for s in [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
    rec = prev[str(s)]
    a_start = rec["A_max_reached"] + 1
    RESUME_PLAN.append((s, a_start))

# split across the two halves: alternate assignment (even index -> A, odd -> B)
# -- same convention as 2026-08-03, which keeps the two heaviest items (s=9
# and s=10) on separate cores automatically.
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

        if elapsed_s > PER_S_TIME_BUDGET:
            stop_reason = (f"stopping s={s}: cumulative ACTUAL time {elapsed_s:.1f}s > budget "
                            f"{PER_S_TIME_BUDGET}s (control-timed, NOT natural exhaustion -- "
                            f"remaining headroom to natural ceiling still exists, see PROGRESS.md)")
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

    with open(f"production_streaming_v6_results_{HALF}.json", "w") as f:
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
