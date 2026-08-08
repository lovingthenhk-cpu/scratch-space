"""
2026-08-09: direct continuation of 2026-08-08's top-priority "next step" --
re-examine the 21,000,000 -> 24,000,000 MEM_ITEM_BUDGET probe with the
"improved methodology" flagged in PROGRESS.md: list the SATURATION ratio
(materialized-side item count / budget) for ALL newly-unlocked candidates,
not just their absolute materialized item count, before picking which pair
to run concurrently.

IMPORTANT CORRECTION discovered while writing this script (see REPORT.md
"Part 9-1" for the full writeup): for a FIXED budget B, ranking candidates
by (mat_count) and ranking them by (mat_count / B) are the IDENTICAL
ordering, since B is a constant across all candidates being compared in the
same round. So "pick the largest materialized side" (2026-08-05/07/08's
method) and "pick the highest saturation ratio" (today's stated goal)
necessarily select the SAME pair when comparing candidates against the same
NEW_BUDGET. This script still computes and prints the saturation ratios
explicitly (useful documentation of *why* the jump happened -- see below --
and required to correctly identify the top-2), but do not expect the
selected pair to differ from 2026-08-08's.

What DOES explain 2026-08-08's "sudden 21M->24M jump [is not[ linear]"
finding is a genuine, separate phenomenon: the *saturation ratio itself*
varies wildly and unpredictably between candidates, and between successive
budget-increase rounds, because it depends on the fine combinatorial
structure of choose_k_for_memory_budget(s, A, budget) for that specific
(s, A) pair -- NOT on any flaw in "pick largest absolute count". At 18M->21M
the newly-unlocked candidates happened to have LOW saturation (12-18%); at
21M->24M they happened to have HIGH saturation (88-98%, see table below).
There was no selection methodology that would have caught this earlier
using only the 18M->21M data, because saturation is a property of the
(s, A, budget) triple, not of the selection RULE. The real lesson (correctly
stated in PROGRESS.md) is: report and watch the saturation ratio explicitly
every round (not just the raw item count) as an early-warning signal for
future rounds, since a round with many near-100%-saturated unlocked
candidates is closer to the theoretical worst case (2 processes both
saturating simultaneously) than a round where unlocked candidates all sit
at 15% of budget.

This script: (1) recomputes the unlocked set at 24,000,000 from the
confirmed 2026-08-08 21,000,000 ceilings (should reproduce the same 5:
s=9,11,13,16,18), (2) prints the full saturation table, (3) selects the
top-2 by saturation (== top-2 by raw count, see above) for a REPEAT
concurrent run (reproducibility check on 2026-08-08's 6.83 GiB combined
peak), and (4) also identifies the 3rd-highest-saturation candidate as a
substitute for a follow-up SWAP run (see swap_pair_probe_24M.py) to check
whether a different near-saturated pair also approaches the same peak, or
whether 2026-08-08's number was itself an outlier.
"""
from math import comb

from mitm_streaming import choose_k_for_memory_budget

OLD_BUDGET = 21_000_000
NEW_BUDGET = 24_000_000
PER_A_TIME_LIMIT = 900.0
EMPIRICAL_RATE = 1_000_000

# Confirmed natural ceilings after 2026-08-08's real v9 production run
# (production_streaming_v9_results_merged.json), i.e. today's starting point.
CEILINGS_21M = {9: 156, 10: 99, 11: 83, 12: 72, 13: 59, 14: 59, 15: 51, 16: 49, 17: 47, 18: 44}
STUCK = {s: A + 1 for s, A in CEILINGS_21M.items()}


def est(s, A, budget):
    k = choose_k_for_memory_budget(s, A, budget)
    max1 = A - (s - k)
    max2 = A - k
    c1 = comb(max1, k) if max1 >= k else 0
    c2 = comb(max2, s - k) if max2 >= (s - k) else 0
    mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
    return k, mn, mx, mx / EMPIRICAL_RATE


print("=== s, A (next step from 21M ceiling), unlocked-at-24M?, saturation ratio ===")
rows = []
for s, A in sorted(STUCK.items()):
    k_old, mn_old, mx_old, t_old = est(s, A, OLD_BUDGET)
    k_new, mn_new, mx_new, t_new = est(s, A, NEW_BUDGET)
    ok = t_new <= PER_A_TIME_LIMIT
    sat_old = mn_old / OLD_BUDGET
    sat_new = mn_new / NEW_BUDGET
    print(f"s={s:2d} A={A:3d}  21M(k={k_old}, mat={mn_old:.3e}, sat={sat_old:6.1%}, est={t_old:8.1f}s)  "
          f"24M(k={k_new}, mat={mn_new:.3e}, sat={sat_new:6.1%}, est={t_new:7.1f}s)  unlocked={ok}")
    if ok:
        rows.append({"s": s, "A": A, "k": k_new, "mat": mn_new, "sat": sat_new,
                      "streamed": mx_new, "est_time": t_new})

rows.sort(key=lambda r: -r["sat"])
print(f"\n=== unlocked candidates, ranked by SATURATION ratio (mat/{NEW_BUDGET:,}) ===")
for r in rows:
    print(f"  s={r['s']:2d} A={r['A']:3d}  sat={r['sat']:6.1%}  mat={r['mat']:.3e}  "
          f"streamed={r['streamed']:.3e}  est_time={r['est_time']:.1f}s")

top2 = rows[:2]
third = rows[2] if len(rows) > 2 else None
print(f"\n=== top-2 by saturation (repeat pair, expect same as 2026-08-08's raw-count pick): "
      f"{[(r['s'], r['A']) for r in top2]} ===")
if third:
    print(f"=== 3rd-highest saturation (swap candidate for follow-up run): "
          f"s={third['s']} A={third['A']} sat={third['sat']:.1%} ===")

import json
with open("saturation_analysis_24M_results.json", "w") as f:
    json.dump({
        "old_budget": OLD_BUDGET, "new_budget": NEW_BUDGET,
        "ceilings_21m": CEILINGS_21M,
        "unlocked_ranked_by_saturation": rows,
        "top2_pair": [(r["s"], r["A"]) for r in top2],
        "third_candidate": (third["s"], third["A"]) if third else None,
    }, f, indent=2, default=str)
print("\nWritten to saturation_analysis_24M_results.json")
