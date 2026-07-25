#!/usr/bin/env python3
"""
Priority-2 follow-up from 2026-07-25 (PROGRESS.md item 2): a lightweight
extreme-value-statistics look at the Collatz glide-record sequence
(2026-07-25/glide_records.csv, 71 records, n from 2 up to ~4.89e9),
using only data already collected -- no new heavy computation needed.

Background: for a sequence of i.i.d. continuous random variables
X_1, X_2, ..., X_N, classical record theory says the number of "records"
(left-to-right maxima) up to N has expectation H_N = sum_{i=1}^N 1/i ~ ln N
+ gamma, UNIVERSALLY (independent of the distribution of X_i, by an
exchangeability argument: X_i is a record iff it's the max of the first i,
which happens with probability 1/i regardless of F). This is one of the
most-quoted facts used informally in the Collatz literature to "explain"
why the number of step-count record-holders up to N grows like log N.

This script checks that heuristic quantitatively against our actual
71-record dataset, and also looks at the log-gaps between successive
records (ln(n_{k+1}) - ln(n_k)), which under a naive "records are like a
Poisson process in log-space" model should look roughly Exponential.
"""
import csv
import math
import statistics

def load_records(path):
    rows = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append((int(row['n']), int(row['steps'])))
    return rows

def main():
    recs = load_records('2026-07-25/glide_records.csv')
    recs.sort()
    ns = [n for n, s in recs]
    steps = [s for n, s in recs]
    K = len(recs)
    print(f"Loaded {K} glide records, n from {ns[0]} to {ns[-1]}")

    # --- 1. Records-vs-ln(N) universal heuristic check ---
    print("\n=== 1. Record count vs. ln(N) (universal i.i.d. record theory) ===")
    N_last = ns[-1]
    N_search = 7_000_000_000  # actual exhaustive-search upper bound from 2026-07-25 Part A'
    lnN_last = math.log(N_last)
    lnN_search = math.log(N_search)
    print(f"K={K} records found.")
    print(f"  ln(n_last={N_last}) = {lnN_last:.4f}  => K/ln(N) = {K/lnN_last:.4f}")
    print(f"  ln(N_search={N_search}) = {lnN_search:.4f}  => K/ln(N) = {K/lnN_search:.4f}")
    print("  Universal i.i.d. theory predicts K/ln(N) -> 1 (H_N ~ ln N + gamma).")
    print(f"  Observed ratio is ~{K/lnN_search:.2f}x the i.i.d. prediction of 1.")
    print("  Interpretation: Collatz step-counts are NOT behaving like an i.i.d.")
    print("  sequence indexed 1..N in the strict record-theory sense -- there are")
    print("  roughly 3x MORE record-breakers than the universal iid bound would give.")
    print("  Plausible reason: consecutive/nearby n have strongly CORRELATED")
    print("  trajectories (e.g. n and n's 2-adic neighbours often share long common")
    print("  tails), which is exactly the kind of dependence that breaks the")
    print("  exchangeability argument behind H_N -- positively-correlated 'nearby")
    print("  maxima' can each individually still count as a fresh record against the")
    print("  single running best-so-far, inflating the count above the iid rate.")

    # Fit K ~ c * ln(N) + b using just the two anchor points we trust (first
    # record n=2,steps=1 is a degenerate anchor; use a simple slope through
    # count vs ln(n_k) at a few points along the sequence instead):
    print("\n  K_k (running record index) vs ln(n_k), sampled every ~10th record:")
    for i in range(0, K, 10):
        print(f"    k={i+1:3d}  n={ns[i]:>12d}  ln(n)={math.log(ns[i]):.3f}  k/ln(n)={ (i+1)/math.log(ns[i]) if ns[i]>1 else float('nan'):.3f}")

    # --- 2. Log-gap (multiplicative gap) statistics between records ---
    print("\n=== 2. ln(n_{k+1}/n_k) gap statistics (excluding the first record) ===")
    log_gaps = [math.log(ns[i+1]) - math.log(ns[i]) for i in range(K-1)]
    mean_gap = statistics.mean(log_gaps)
    sd_gap = statistics.pstdev(log_gaps)
    print(f"  n_gaps = {len(log_gaps)}")
    print(f"  mean(ln gap)   = {mean_gap:.4f}")
    print(f"  stdev(ln gap)  = {sd_gap:.4f}   (ratio sd/mean = {sd_gap/mean_gap:.4f}; "
          f"Exponential(rate) has sd/mean = 1 exactly)")
    print(f"  min/max ln-gap = {min(log_gaps):.4f} / {max(log_gaps):.4f}")

    # quick exponential-fit goodness check via a simple KS-type statistic
    log_gaps_sorted = sorted(log_gaps)
    lam = 1.0 / mean_gap
    n_g = len(log_gaps_sorted)
    max_dev = 0.0
    for i, x in enumerate(log_gaps_sorted):
        F_emp = (i + 1) / n_g
        F_theory = 1 - math.exp(-lam * x)
        max_dev = max(max_dev, abs(F_emp - F_theory))
    print(f"  KS statistic vs Exponential(rate={lam:.4f}): D = {max_dev:.4f}")
    # rough KS critical value at alpha=0.05 for this n: 1.36/sqrt(n)
    crit = 1.36 / math.sqrt(n_g)
    print(f"  KS 5% critical value (asymptotic, n={n_g}): {crit:.4f}  "
          f"=> {'CANNOT reject Exponential' if max_dev < crit else 'REJECT Exponential'} at 5% level")

    # --- 3. steps increments between successive records ---
    print("\n=== 3. steps increment (Delta steps) between successive records ===")
    step_gaps = [steps[i+1] - steps[i] for i in range(K-1)]
    print(f"  mean(Delta steps) = {statistics.mean(step_gaps):.3f}")
    print(f"  stdev(Delta steps) = {statistics.pstdev(step_gaps):.3f}")
    print(f"  min/max = {min(step_gaps)}/{max(step_gaps)}")
    # correlate step_gaps with log_gaps: slope should be near the 53.72 from
    # 2026-07-25's regression (steps ~ 53.72 ln n - 175.33), since
    # Delta(steps) ~ 53.72 * Delta(ln n) if records tracked the fitted line
    # exactly (they don't, by construction records are noisy, but check).
    ratios = [step_gaps[i] / log_gaps[i] for i in range(len(step_gaps)) if log_gaps[i] > 0]
    print(f"  Delta(steps)/Delta(ln n) per-gap ratio: mean={statistics.mean(ratios):.2f}, "
          f"median={statistics.median(ratios):.2f}  (2026-07-25 regression slope was 53.72)")

    # --- 4. peak/n records ---
    print("\n=== 4. peak/n record growth ===")
    peak_recs = []
    with open('2026-07-25/peak_records.csv') as f:
        r = csv.DictReader(f)
        for row in r:
            peak_recs.append((int(row['n']), int(row['peak']), float(row['peak_over_n'])))
    peak_recs.sort()
    Kp = len(peak_recs)
    print(f"  {Kp} peak/n records, n from {peak_recs[0][0]} to {peak_recs[-1][0]}")
    print(f"  final peak/n = {peak_recs[-1][2]:.6f} at n={peak_recs[-1][0]}")
    # ln(peak/n) vs ln(n) slope (log-log), since peak/n records should grow
    # roughly like n^alpha for some small alpha>0 if the standard heuristic
    # (peak/n unbounded but very slowly, conjectured ~ n^o(1)) holds
    xs = [math.log(n) for n, p, r in peak_recs if n > 1]
    ys = [math.log(r) for n, p, r in peak_recs if n > 1]
    nx = len(xs)
    mx = sum(xs) / nx
    my = sum(ys) / nx
    sxy = sum((xs[i]-mx)*(ys[i]-my) for i in range(nx))
    sxx = sum((xs[i]-mx)**2 for i in range(nx))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_res = sum((ys[i] - (slope*xs[i]+intercept))**2 for i in range(nx))
    ss_tot = sum((ys[i]-my)**2 for i in range(nx))
    r2 = 1 - ss_res/ss_tot
    print(f"  log-log fit: ln(peak/n) ~ {slope:.4f} * ln(n) + {intercept:.4f}  (R2={r2:.4f})")
    print(f"  => peak/n grows roughly like n^{slope:.4f}; a genuinely unbounded")
    print(f"     peak/n consistent with the (unproven) folklore that sup peak/n = infinity")
    print(f"     would need alpha>0, however tiny; here alpha~{slope:.4f} but with only")
    print(f"     {Kp} points this is NOT strong evidence either way -- just descriptive.")

if __name__ == "__main__":
    main()
