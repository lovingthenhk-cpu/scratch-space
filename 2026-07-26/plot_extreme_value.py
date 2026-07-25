#!/usr/bin/env python3
import csv, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

recs = []
with open('2026-07-25/glide_records.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        recs.append((int(row['n']), int(row['steps'])))
recs.sort()
ns = np.array([n for n, s in recs], dtype=float)
steps = np.array([s for n, s in recs], dtype=float)
K = len(recs)
k_idx = np.arange(1, K+1)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: record index k vs ln(n_k), with iid-theory line k=ln(n) and fitted line
ax = axes[0]
lns = np.log(ns)
ax.plot(lns, k_idx, 'o-', color='#2563eb', markersize=4, linewidth=1, label='observed records (k vs ln $n_k$)')
ax.plot(lns, lns, '--', color='#9ca3af', linewidth=1.5, label='universal i.i.d. prediction ($k = \\ln N$)')
# linear fit through origin-ish
slope = np.sum(k_idx * lns) / np.sum(lns * lns)
ax.plot(lns, slope * lns, ':', color='#dc2626', linewidth=1.5, label=f'fitted $k \\approx {slope:.2f}\\ln N$')
ax.set_xlabel('ln(n) of the k-th glide record')
ax.set_ylabel('record index k')
ax.set_title('Glide-record count vs. ln(N)\n(observed rate ~3.1x the universal i.i.d. rate of 1)')
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# Panel 2: histogram of ln-gaps vs fitted exponential
ax = axes[1]
log_gaps = np.diff(lns)
mean_gap = log_gaps.mean()
ax.hist(log_gaps, bins=14, density=True, color='#2563eb', alpha=0.65, label='observed ln-gaps (n=70)')
xs = np.linspace(0, log_gaps.max()*1.1, 200)
lam = 1/mean_gap
ax.plot(xs, lam*np.exp(-lam*xs), color='#dc2626', linewidth=2, label=f'Exponential(rate={lam:.2f}) fit')
ax.set_xlabel('$\\ln(n_{k+1}/n_k)$')
ax.set_ylabel('density')
ax.set_title('Log-gaps between successive glide records\n(KS test rejects Exponential at 5%: too regular/sub-exponential)')
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('2026-07-26/extreme_value_analysis.png', dpi=130)
print("saved 2026-07-26/extreme_value_analysis.png")
