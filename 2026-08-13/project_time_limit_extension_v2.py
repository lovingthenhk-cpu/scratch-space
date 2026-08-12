"""
2026-08-13: direct continuation of 2026-08-09 REPORT.md "次回やろうとしていたこと"
priority 1: extend PER_A_TIME_LIMIT further (1200s -> ~1300s) so that
s=18 (and any further steps for s=10,12,15,17) can advance too. 2026-08-09
raised PER_A_TIME_LIMIT 900s->1200s and advanced s=10 (99->104), s=12
(72->75), s=15 (51->52), s=17 (47->48), but s=18 gained NOTHING at 1200s
(its next step needs an estimated ~1203.3s, just barely over the limit).

This script re-runs the SAME projection methodology as
../2026-08-09/project_time_limit_extension.py, but starting from the
UPDATED ceilings actually reached on 2026-08-09 (not the stale 2026-08-08
ceilings), and scans a tighter range of PER_A_TIME_LIMIT candidates
(1250/1300/1350/1400/1500s) since 2026-08-09 REPORT.md already recommended
~1300s specifically (not the coarser 1800/3600/7200/14400s grid used when
this technique was first explored on 2026-08-09 for a different question).
MEM_ITEM_BUDGET stays fixed at 21,000,000 (proven safe; 24,000,000 is
confirmed dangerous per 2026-08-08/08-09, see PROGRESS.md) -- this is a
PURE wall-clock knob change, no new OOM risk in principle. As always,
project first (this script, cheap math.comb() arithmetic, no enumeration),
then verify empirically with monitor_memory.py running alongside the real
production run (per the 2026-08-02/08-09 lessons: never trust a projection
alone).
"""
from math import comb

from mitm_streaming import choose_k_for_memory_budget

MEM_ITEM_BUDGET = 21_000_000
EMPIRICAL_RATE = 1_000_000
# Actual ceilings reached as of 2026-08-09 (production_streaming_v10_results_merged.json
# for s=10,12,15,17; s=18 unchanged since it gained 0 steps at 1200s; s=9,11,13,14,16
# are the "memory-limited, already at natural ceiling under 21M budget" set from
# 2026-08-08 and are NOT part of this time-limit investigation).
CEILINGS_AFTER_0809 = {9: 156, 10: 104, 11: 83, 12: 75, 13: 59, 14: 59, 15: 52, 16: 49, 17: 48, 18: 44}
TIME_LIMITED_S = [10, 12, 15, 17, 18]

for PER_A_TIME_LIMIT in [1250.0, 1300.0, 1350.0, 1400.0, 1500.0]:
    print(f"\n########## PER_A_TIME_LIMIT = {PER_A_TIME_LIMIT:.0f}s ##########")
    grand_total_time = 0.0
    per_s_summary = {}
    for s in TIME_LIMITED_S:
        A = CEILINGS_AFTER_0809[s] + 1
        total_time_this_s = 0.0
        steps = 0
        max_sat_seen = 0.0
        while True:
            k = choose_k_for_memory_budget(s, A, MEM_ITEM_BUDGET)
            max1 = A - (s - k)
            max2 = A - k
            c1 = comb(max1, k) if max1 >= k else 0
            c2 = comb(max2, s - k) if max2 >= (s - k) else 0
            mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
            est_time = mx / EMPIRICAL_RATE
            sat = mn / MEM_ITEM_BUDGET
            if est_time > PER_A_TIME_LIMIT:
                print(f"  s={s:2d}: ceiling A={A-1} (next A={A} needs k={k}, mat={mn:.3e} "
                      f"(sat={sat:.1%}), streamed={mx:.3e} -> est {est_time:.1f}s > limit), "
                      f"steps_gained={steps}, projected_time={total_time_this_s:.1f}s, "
                      f"max_saturation_seen={max_sat_seen:.1%}")
                break
            max_sat_seen = max(max_sat_seen, sat)
            total_time_this_s += est_time
            steps += 1
            A += 1
        per_s_summary[s] = (steps, total_time_this_s, max_sat_seen)
        grand_total_time += total_time_this_s
    print(f"  grand total projected CPU time (single core, sequential): "
          f"{grand_total_time:.1f}s ({grand_total_time/60:.1f} min)")
