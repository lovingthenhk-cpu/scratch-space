"""
2026-08-01: direct continuation of 2026-07-31's
`../2026-07-31/run_production_streaming_v2.py`.

Literature side-quest (Part R, see REPORT.md / PROGRESS.md): another attempt
to fetch John Simons (2008?), Acta Arithmetica 131?, "On the (non-)existence
of m-cycles for generalized Syracuse sequences" full text -- tried several
NEW routes today (Semantic Scholar API, IMPAN PDF direct link, ResearchGate,
CiteSeerX, arXiv/ar5iv for Lagarias's 2021 survey) beyond yesterday's 3 URLs.
Result: still blocked by the same PROVENANCE_REQUIRED wall for every
page/paper actually about this topic, while unrelated arXiv PDFs (e.g.
2201.00406, Hercher's "no Collatz-m-cycles with m<=90") and one unrelated
nntdm.net PDF fetched FINE. So it is not a blanket ban on all external
fetches, and not simply "PDF vs HTML" -- something about this specific
paper's hosting keeps triggering it, 2 automated sessions running now with
zero successes across ~8 distinct URLs. Re-confirmed Santos (2020) Remark 3
verbatim via ar5iv (matches what PROGRESS.md already had, no new info).
Detailed log in REPORT.md Part R. Not retrying again today -- back to the
computational track, as recommended by yesterday's note.

Computational side (Part S, this file): two real, additive changes from
v2, no new algorithm:

  1. PARALLELIZE ACROSS BOTH CPU CORES. Every MITM production run so far
     (2026-07-29 .. 2026-07-31) executed its per-s loop SERIALLY in one
     Python process, even though the sandbox has 2 cores (see
     PROGRESS.md environment notes) and each s-value's search is fully
     INDEPENDENT of every other s-value (different (s,A) shapes, disjoint
     work, no shared mutable state). That means every prior production run
     left one core idle the whole time. This script takes a list of s
     values and a `--half {A,B}` flag; the caller (see shell commands in
     REPORT.md) launches two OS processes concurrently, each pinned to a
     disjoint half of the s-list, so both cores actually get used. This is
     "use the hardware you already have", not an algorithmic change --
     flagged explicitly per PROGRESS.md's standing rule against overclaiming
     novelty.
  2. Raise time budgets again (PER_A_TIME_LIMIT 400s->700s, PER_S_TIME_BUDGET
     900s->1500s) since yesterday's stop reason was, again, always the
     self-imposed schedule limit and never a crash/OOM.

Same target as every session since 2026-07-27: q=5, T_5 map, does a
nontrivial cycle exist with n1 = 4 (mod 5)? Still zero hits
expected/hoped-for -- absence just extends the exhaustive lower bound.
"""
import json
import sys
import time
from math import comb

from mitm_streaming import mitm_search_one_A_streaming, choose_k_for_memory_budget

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

MEM_ITEM_BUDGET = 2_000_000
EMPIRICAL_RATE = 900_000  # measured today ~1.4-1.5e6/s on the streamed side alone; keep some margin
PER_A_TIME_LIMIT = 700.0
PER_S_TIME_BUDGET = 1500.0

HALF = sys.argv[1] if len(sys.argv) > 1 else "A"

with open("../2026-07-31/production_streaming_v2_results.json") as f:
    prev = json.load(f)["results"]

# Resume s=19..24 from where v2 stopped; s=20 has A_max_reached=null (never
# completed even A=39) so resume AT its stated A_min, not A_min+1.
RESUME_PLAN = []
for s in [19, 20, 21, 22, 23, 24]:
    rec = prev[str(s)]
    if rec["A_max_reached"] is None:
        a_start = rec["A_min"]
    else:
        a_start = rec["A_max_reached"] + 1
    RESUME_PLAN.append((s, a_start))
NEW_PLAN = [(s, s) for s in [25, 26]]
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

    with open(f"production_streaming_v3_results_{HALF}.json", "w") as f:
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
