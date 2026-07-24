"""
Regression analysis of the Collatz "glide record" sequence: the n values
whose total stopping time exceeds every smaller n's stopping time.

Empirically, it's a long-observed pattern (see e.g. Lagarias's survey and
many "Collatz record" web pages) that the record-holders' step counts grow
roughly linearly in ln(n), i.e.

    steps(n) ~= c * ln(n) + b

for some constant c. This script fits that regression on our own
glide_records.csv (accumulated from 2026-07-24's [1, 1e9) run plus
2026-07-25's shard extension), reports the fitted c, b, R^2, and compares c
to two natural theoretical reference points:

  - c_theory_1 = 1 / log(2) ~= 1.4427 : if we (naively, incorrectly) assumed
    EVERY step were a halving step, steps ~ log2(n) = ln(n)/ln(2).
  - c_theory_2 = 1 / log(4/3) ~= 3.4761 : using the "equilibrium heuristic"
    net contraction factor of 3/4 per full odd-then-halvings cycle (see
    generalized_qn1.c header comment), a full cycle multiplies n by ~3/4 and
    corresponds to ~1 odd step + ~2 halving steps = ~3 steps on average, so
    if EVERY step behaved like the "average" cycle, we'd expect roughly
    steps ~= 3 * log_{4/3}(n) ... this is a much cruder approximation and
    mainly useful as an order-of-magnitude sanity check, not a tight
    theoretical prediction (record holders are, by definition, atypical /
    outlier trajectories, not "average" ones -- so we should NOT expect
    either theoretical constant to fit record data well; that mismatch is
    itself worth reporting).
"""
import numpy as np
import pandas as pd

df = pd.read_csv("glide_records.csv")
df = df[df["n"] > 1].reset_index(drop=True)  # drop the trivial n=1 warm-up row if present

x = np.log(df["n"].values.astype(np.float64))
y = df["steps"].values.astype(np.float64)

# ordinary least squares: y = c*x + b
A = np.vstack([x, np.ones_like(x)]).T
(c, b), residuals, rank, sv = np.linalg.lstsq(A, y, rcond=None)
y_pred = c * x + b
ss_res = np.sum((y - y_pred) ** 2)
ss_tot = np.sum((y - np.mean(y)) ** 2)
r2 = 1 - ss_res / ss_tot

c_theory_1 = 1.0 / np.log(2.0)
c_theory_2 = 1.0 / np.log(4.0 / 3.0)

print(f"n_records = {len(df)}")
print(f"fit: steps = {c:.4f} * ln(n) + {b:.4f}   (R^2 = {r2:.6f})")
print(f"reference c_1 = 1/ln(2)      = {c_theory_1:.4f}  (steps if every step were a halving)")
print(f"reference c_2 = 1/ln(4/3)    = {c_theory_2:.4f}  (steps if every cycle were 'average' 3/4-contracting)")
print(f"fitted c is {c/c_theory_1:.3f}x c_1 and {c/c_theory_2:.3f}x c_2")

# also report fit restricted to the "large" records (n > 1e6) since the
# small-n tail is dominated by short-run noise / small-number effects
big = df[df["n"] > 1e6]
if len(big) >= 5:
    xb = np.log(big["n"].values.astype(np.float64))
    yb = big["steps"].values.astype(np.float64)
    Ab = np.vstack([xb, np.ones_like(xb)]).T
    (cb, bb), *_ = np.linalg.lstsq(Ab, yb, rcond=None)
    yb_pred = cb * xb + bb
    r2b = 1 - np.sum((yb - yb_pred) ** 2) / np.sum((yb - np.mean(yb)) ** 2)
    print()
    print(f"restricted to n > 1e6 ({len(big)} records):")
    print(f"  fit: steps = {cb:.4f} * ln(n) + {bb:.4f}   (R^2 = {r2b:.6f})")

df.to_csv("glide_records_with_lnfit.csv", index=False)
with open("regression_summary.txt", "w") as f:
    f.write(f"n_records={len(df)}\n")
    f.write(f"fit_all: steps = {c:.6f} * ln(n) + {b:.6f}  R2={r2:.6f}\n")
    if len(big) >= 5:
        f.write(f"fit_n_gt_1e6: steps = {cb:.6f} * ln(n) + {bb:.6f}  R2={r2b:.6f}  (n_records={len(big)})\n")
    f.write(f"c_theory_1_1_over_ln2 = {c_theory_1:.6f}\n")
    f.write(f"c_theory_2_1_over_ln_4_3 = {c_theory_2:.6f}\n")
print("wrote regression_summary.txt")
