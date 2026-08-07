from math import comb
from mitm_streaming import choose_k_for_memory_budget

for MEM_ITEM_BUDGET in [21_000_000]:
    EMPIRICAL_RATE = 1_000_000
    PER_A_TIME_LIMIT = 900.0

    # current ceilings after the 18M production run (2026-08-07)
    starts = {9:150, 10:99, 11:81, 12:72, 13:58, 14:58, 15:51, 16:48, 17:47, 18:44}

    grand_total_time = 0.0
    for s in sorted(starts):
        A = starts[s] + 1
        total_time_this_s = 0.0
        steps = 0
        while True:
            k = choose_k_for_memory_budget(s, A, MEM_ITEM_BUDGET)
            max1 = A - (s - k)
            max2 = A - k
            c1 = comb(max1, k) if max1 >= k else 0
            c2 = comb(max2, s - k) if max2 >= (s - k) else 0
            mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
            est_time = mx / EMPIRICAL_RATE
            if est_time > PER_A_TIME_LIMIT:
                print(f"[budget={MEM_ITEM_BUDGET:,}] s={s:2d}: ceiling A={A-1} (next A={A} needs k={k}, mat={mn:.3e}, "
                      f"streamed={mx:.3e} -> est {est_time:.1f}s > {PER_A_TIME_LIMIT}s), "
                      f"steps_gained={steps}, projected_time={total_time_this_s:.1f}s")
                break
            total_time_this_s += est_time
            steps += 1
            A += 1
        grand_total_time += total_time_this_s
    print(f"\n[budget={MEM_ITEM_BUDGET:,}] grand total projected CPU time (single core, sequential): {grand_total_time:.1f}s ({grand_total_time/60:.1f} min)")
