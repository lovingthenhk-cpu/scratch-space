"""
2026-07-30 Part K: precise feasibility numbers for the log2(5) continued-
fraction convergents flagged by 2026-07-29 Part J as candidate targets for
the MITM cycle-shape search, BEFORE spending any more compute trying to
reach them. See REPORT.md Part K for the narrative; this script just
produces the numbers referenced there.
"""
from math import comb, log2

print("log2(5) =", log2(5))
print()

# (s, A) pairs: known cycles' shape length, then the next few convergents
# of log2(5) from 2026-07-29's log2_5_continued_fraction.py output.
targets = [
    (3, 7, "known nontrivial q=5 cycles (already found, 2026-07-25/27)"),
    (28, 65, "next convergent -- 2026-07-29's attempted target, OOM'd"),
    (59, 137, "next convergent"),
    (146, 339, "next convergent"),
]

RATE = 1e6  # conservative measured streaming rate, items/s (see REPORT.md Part M)

for s, A, note in targets:
    k = (s + 1) // 2
    max1, max2 = A - (s - k), A - k
    c1 = comb(max1, k) if max1 >= k else 0
    c2 = comb(max2, s - k) if max2 >= (s - k) else 0
    mn = min(c1, c2) if (c1 and c2) else max(c1, c2)
    print(f"s={s:4d} A={A:4d}  ({note})")
    print(f"    balanced-split smaller side: {mn:.4e} items")
    print(f"    @ 1 byte/item (impossible lower bound):        {mn/1e9:12.4e} GB")
    print(f"    @ ~150 bytes/item (measured, dict-indexed):    {mn*150/1e9:12.4e} GB")
    gen_seconds = mn / RATE
    print(f"    time to GENERATE (not join) smaller side @ {RATE:.0e}/s: "
          f"{gen_seconds:.3e} s = {gen_seconds/86400:.3e} days")
    print()

print("=== Comparison: brute force vs. best-case 2-way MITM total work, s=28,A=65 ===")
brute = comb(64, 27)
mitm_total = 2 * comb(51, 14)
print(f"brute force C(64,27)          = {brute:,}")
print(f"2-way MITM total 2*C(51,14)   = {mitm_total:,}")
print(f"speedup factor                = {brute/mitm_total:,.0f}x")
print(f"time for MITM total @ {RATE:.0e} items/s (generation only): "
      f"{mitm_total/RATE:.3e} s = {mitm_total/RATE/86400:.1f} days")
