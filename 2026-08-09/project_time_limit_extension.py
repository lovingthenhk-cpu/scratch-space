"""
2026-08-09: 2026-08-08 REPORT.md "次回やろうとしていたこと" item 2 (priority
2, previously unexamined because 2026-08-08 spent its whole session on the
MEM_ITEM_BUDGET question): for s=10,12,15,17,18, the last FIVE sessions
(2026-08-04 through 2026-08-08) have left these five s stuck at the exact
SAME (s, A) ceiling even as MEM_ITEM_BUDGET rose 15M -> 18M -> 21M, because
--as saturation_analysis_24M.py's "21M" column shows -- their NEXT A step's
materialized side is comfortably within budget (12.7%-60.1% saturation) but
its STREAMED side estimate exceeds PER_A_TIME_LIMIT=900s. I.e. these five
are TIME-limited, not MEMORY-limited, at the current budget. Raising
PER_A_TIME_LIMIT (a pure wall-clock knob, no OOM risk at all, unlike raising
MEM_ITEM_BUDGET) should let them advance using memory we've already proven
safe.

This script projects, for several candidate PER_A_TIME_LIMIT values, how
many additional A-steps each of the five reaches and the total single-core
CPU time required, WITHOUT running anything -- pure math.comb() projection,
same method as project_21M.py. Chooses a concrete limit for today's
production run based on what fits comfortably in one session.
"""
from math import comb

from mitm_streaming import choose_k_for_memory_budget

MEM_ITEM_BUDGET = 21_000_000
EMPIRICAL_RATE = 1_000_000
CEILINGS_21M = {9: 156, 10: 99, 11: 83, 12: 72, 13: 59, 14: 59, 15: 51, 16: 49, 17: 47, 18: 44}
TIME_LIMITED_S = [10, 12, 15, 17, 18]  # excludes the memory-limited/unmoved-by-time set

for PER_A_TIME_LIMIT in [1800.0, 3600.0, 7200.0, 14400.0]:
    print(f"\n########## PER_A_TIME_LIMIT = {PER_A_TIME_LIMIT:.0f}s ##########")
    grand_total_time = 0.0
    per_s_summary = {}
    for s in TIME_LIMITED_S:
        A = CEILINGS_21M[s] + 1
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
