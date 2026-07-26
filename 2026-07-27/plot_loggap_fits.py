#!/usr/bin/env python3
"""Visualize the log-gap histogram against the fitted Exponential / Gamma /
Weibull curves from loggap_distribution_fit.py (2026-07-27, priority-2
deepening of the 2026-07-26 record-log-gap finding)."""
import csv
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats

def load_records(path):
    rows = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append((int(row['n']), int(row['steps'])))
    return rows

recs = load_records('2026-07-25/glide_records.csv')
recs.sort()
ns = [n for n, s in recs]
K = len(recs)
log_gaps = np.array([math.log(ns[i+1]) - math.log(ns[i]) for i in range(K-1)])

loc, scale = stats.expon.fit(log_gaps, floc=0)
shape_g, loc_g, scale_g = stats.gamma.fit(log_gaps, floc=0)
shape_w, loc_w, scale_w = stats.weibull_min.fit(log_gaps, floc=0)

x = np.linspace(0.001, log_gaps.max()*1.1, 400)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

ax = axes[0]
ax.hist(log_gaps, bins=14, density=True, alpha=0.35, color='#4C72B0', edgecolor='white', label='observed log-gaps (n=70)')
ax.plot(x, stats.expon.pdf(x, loc, scale), color='#DD8452', lw=2, label=f'Exponential (D=0.193)')
ax.plot(x, stats.gamma.pdf(x, shape_g, loc_g, scale_g), color='#55A868', lw=2, label=f'Gamma, shape={shape_g:.2f} (D=0.120, best AIC-2nd)')
ax.plot(x, stats.weibull_min.pdf(x, shape_w, loc_w, scale_w), color='#8172B2', lw=2, ls='--', label=f'Weibull, shape={shape_w:.2f} (D=0.133, best AIC)')
ax.set_xlabel('ln(n_{k+1} / n_k)  [log-gap between successive glide records]')
ax.set_ylabel('density')
ax.set_title('Glide-record log-gaps vs. fitted distributions')
ax.legend(fontsize=8, loc='upper right')

ax2 = axes[1]
sorted_gaps = np.sort(log_gaps)
ecdf = np.arange(1, len(sorted_gaps)+1) / len(sorted_gaps)
ax2.step(sorted_gaps, ecdf, where='post', color='#4C72B0', lw=2, label='empirical CDF')
ax2.plot(x, stats.expon.cdf(x, loc, scale), color='#DD8452', lw=1.5, label='Exponential CDF')
ax2.plot(x, stats.gamma.cdf(x, shape_g, loc_g, scale_g), color='#55A868', lw=1.5, label='Gamma CDF')
ax2.plot(x, stats.weibull_min.cdf(x, shape_w, loc_w, scale_w), color='#8172B2', lw=1.5, ls='--', label='Weibull CDF')
ax2.set_xlabel('ln(n_{k+1} / n_k)')
ax2.set_ylabel('cumulative probability')
ax2.set_title('ECDF vs fitted CDFs (KS test compares these curves)')
ax2.legend(fontsize=8, loc='lower right')

plt.tight_layout()
plt.savefig('2026-07-27/loggap_distribution_fit.png', dpi=130)
print("wrote 2026-07-27/loggap_distribution_fit.png")
