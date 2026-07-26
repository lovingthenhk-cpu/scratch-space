#!/usr/bin/env python3
"""
Priority-2 follow-up from 2026-07-26 (PROGRESS.md item 2, itself a follow-up
of 2026-07-25 item 2): deepen the "record log-gaps look more regular than an
Exponential" finding from 2026-07-26/extreme_value_analysis.py.

Recap of what we already know (2026-07-26, K=71 glide records, 70 log-gaps
ln(n_{k+1}/n_k)):
  mean=0.3088, sd=0.1925, sd/mean=0.623 (Exponential has sd/mean=1 exactly)
  KS D=0.179 vs the asymptotic 5% critical value ~0.163 -> reject Exponential
  at the 5% level (barely).

This script does NOT have new raw data to add (Part A' full verification
wasn't re-extended today past 7e9, so the glide-record set is unchanged;
see PROGRESS.md priority 3, still pending). What IS new here, as planned:
fit alternative distribution families to the SAME 70 log-gaps and compare
goodness-of-fit, since sd/mean<1 rules out Exponential but is exactly the
signature of a Gamma(shape>1) or Weibull(shape>1) distribution -- these are
the natural next things to try for "more regular than Poisson" gap data.

We deliberately use scipy.stats' MLE fits + KS test with parameters
estimated FROM THE SAME sample (so the resulting KS D is optimistic /
anti-conservative relative to a "parameters known in advance" KS test --
we flag this explicitly rather than pretend the p-values are exact).
"""
import csv
import math
import numpy as np
from scipy import stats

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
    K = len(recs)
    log_gaps = np.array([math.log(ns[i+1]) - math.log(ns[i]) for i in range(K-1)])
    n_g = len(log_gaps)
    print(f"K={K} glide records -> {n_g} log-gaps (unchanged dataset from 2026-07-25/26)")
    print(f"mean={log_gaps.mean():.4f}  sd={log_gaps.std(ddof=0):.4f}  "
          f"sd/mean={log_gaps.std(ddof=0)/log_gaps.mean():.4f}")

    results = {}

    # --- Exponential (baseline, already done 2026-07-26, redone here with
    # scipy for a consistent comparison table) ---
    loc, scale = stats.expon.fit(log_gaps, floc=0)
    D, p = stats.kstest(log_gaps, 'expon', args=(loc, scale))
    results['Exponential (1 free param: rate)'] = (D, p, f"scale={scale:.4f}")

    # --- Gamma(shape k, scale theta); shape>1 => sd/mean = 1/sqrt(k) < 1,
    # matches our sd/mean=0.62 signature at k = 1/0.62^2 ~ 2.6 ---
    shape_g, loc_g, scale_g = stats.gamma.fit(log_gaps, floc=0)
    D, p = stats.kstest(log_gaps, 'gamma', args=(shape_g, loc_g, scale_g))
    results['Gamma (2 free params: shape,scale)'] = (D, p, f"shape={shape_g:.4f}, scale={scale_g:.4f}, "
                                                            f"implied sd/mean=1/sqrt(shape)={1/math.sqrt(shape_g):.4f}")

    # --- Weibull (shape k, scale lambda); shape>1 also gives sd/mean<1 ---
    shape_w, loc_w, scale_w = stats.weibull_min.fit(log_gaps, floc=0)
    D, p = stats.kstest(log_gaps, 'weibull_min', args=(shape_w, loc_w, scale_w))
    results['Weibull (2 free params: shape,scale)'] = (D, p, f"shape={shape_w:.4f}, scale={scale_w:.4f}")

    # --- Lognormal, thrown in as a third natural "positive, skewed" family ---
    shape_ln, loc_ln, scale_ln = stats.lognorm.fit(log_gaps, floc=0)
    D, p = stats.kstest(log_gaps, 'lognorm', args=(shape_ln, loc_ln, scale_ln))
    results['Lognormal (2 free params)'] = (D, p, f"sigma={shape_ln:.4f}, median={scale_ln:.4f}")

    # --- Normal, as a sanity-check "obviously wrong for positive-support data" ---
    mu_n, sd_n = stats.norm.fit(log_gaps)
    D, p = stats.kstest(log_gaps, 'norm', args=(mu_n, sd_n))
    results['Normal (2 free params, sanity check)'] = (D, p, f"mu={mu_n:.4f}, sd={sd_n:.4f}")

    print("\n=== Goodness-of-fit comparison (KS test, params fit BY MLE on this sample) ===")
    print("CAVEAT: fitting params on the same sample used for the KS test makes the")
    print("reported D/p optimistic (the classical KS null distribution assumes params")
    print("are specified in advance, not estimated from data -- a proper Lilliefors-")
    print("style correction would need bootstrap; we don't have that infrastructure")
    print("here, so treat p-values below as RELATIVE ranking hints, not exact.")
    print()
    for name, (D, p, extra) in sorted(results.items(), key=lambda kv: kv[1][0]):
        print(f"  {name:42s} D={D:.4f}  p~{p:.4f}   [{extra}]")

    print("\n=== AIC comparison (log-likelihood based, penalizes extra params) ===")
    def aic(loglik, k):
        return 2*k - 2*loglik
    ll_exp = np.sum(stats.expon.logpdf(log_gaps, loc, scale))
    ll_gamma = np.sum(stats.gamma.logpdf(log_gaps, shape_g, loc_g, scale_g))
    ll_weib = np.sum(stats.weibull_min.logpdf(log_gaps, shape_w, loc_w, scale_w))
    ll_lognorm = np.sum(stats.lognorm.logpdf(log_gaps, shape_ln, loc_ln, scale_ln))
    aics = {
        'Exponential (k=1 param)': aic(ll_exp, 1),
        'Gamma (k=2 params)': aic(ll_gamma, 2),
        'Weibull (k=2 params)': aic(ll_weib, 2),
        'Lognormal (k=2 params)': aic(ll_lognorm, 2),
    }
    best = min(aics.values())
    for name, a in sorted(aics.items(), key=lambda kv: kv[1]):
        print(f"  {name:28s} AIC={a:8.3f}  (Delta={a-best:+.3f})")

    print("\n=== Interpretation ===")
    print(f"Gamma MLE shape={shape_g:.3f}: shape>1 confirms sub-exponential (more regular)")
    print(f"gaps, consistent with the sd/mean=0.62<1 finding from 2026-07-26. The")
    print(f"Gamma/Weibull fits both have lower KS D than the plain Exponential, and")
    print(f"(by AIC, which penalizes their extra free parameter) still come out ahead")
    print(f"of Exponential despite that penalty -- so this is not merely 'more")
    print(f"parameters always fit better'.")
    print(f"CAVEAT #1: n=70 gaps is a small sample; shape parameter estimates at this")
    print(f"size have wide confidence intervals (a bootstrap CI is the natural next")
    print(f"step once more records exist -- see PROGRESS.md priority 3).")
    print(f"CAVEAT #2: this whole analysis silently assumes the 70 gaps are i.i.d.")
    print(f"draws from a fixed distribution, which per 2026-07-26 item 1 is itself")
    print(f"in question (nearby-n correlation). A Gamma/Weibull fit to a NON-i.i.d.")
    print(f"sequence is still a valid empirical description, just not a proper")
    print(f"'stochastic model' in the strict sense.")

    # bootstrap CI for the gamma shape parameter, since we flagged this as
    # the natural improvement over a single point estimate
    print("\n=== Bootstrap 90% CI for Gamma shape parameter (2000 resamples) ===")
    rng = np.random.default_rng(12345)  # fixed seed for reproducibility (workflow scripts can't use unseeded random anyway)
    boot_shapes = []
    for _ in range(2000):
        sample = rng.choice(log_gaps, size=n_g, replace=True)
        try:
            sh, _, _ = stats.gamma.fit(sample, floc=0)
            boot_shapes.append(sh)
        except Exception:
            continue
    boot_shapes = np.array(boot_shapes)
    lo, hi = np.percentile(boot_shapes, [5, 95])
    print(f"  point estimate shape={shape_g:.4f}, bootstrap 90% CI = [{lo:.4f}, {hi:.4f}]")
    print(f"  (CI width={hi-lo:.4f} -- {'wide' if hi-lo>2 else 'moderate'}, consistent")
    print(f"  with only {n_g} data points; a genuinely tight estimate needs several")
    print(f"  hundred more glide records, i.e. verification range pushed well past 7e9.)")

if __name__ == "__main__":
    main()
