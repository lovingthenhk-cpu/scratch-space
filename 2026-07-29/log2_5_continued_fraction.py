"""
Continued-fraction / Diophantine-approximation exploration for q=5, 2026-07-29.

Background: the classical q=3 (3x+1) literature (Steiner 1977; Eliahou 1993;
Halbeisen & Hungerbuehler 1997; Simons & de Weger 2005; Hercher 2021/22) uses
continued-fraction convergents of delta = log(3)/log(2) = log2(3) to bound how
close 2^A can get to 3^s for given (A,s), which in turn lower-bounds the
possible length of any nontrivial cycle. A literature search done today
(see REPORT.md) found NO paper applying this specific machinery to q=5's
log2(5); this script is accordingly a first, exploratory (NOT rigorous-proof)
look at what the analogous picture looks like for log2(5), to inform where
a MITM/brute-force shape search is most likely to be worth extra depth.

For a hypothetical cycle with s odd terms and A total halvings to exist,
we need n1 = c/(2^A - 5^s) to be a positive integer. The size of the
denominator D = 2^A - 5^s matters: D is forced towards 0 (a "near miss")
exactly when A/s is close to log2(5) = 2.32192... -- i.e. at continued
fraction convergents of log2(5). This does NOT by itself prove existence
or non-existence (that requires D | c, a much stronger integer condition),
but it identifies which (s,A) pairs are "resonant" and hence the natural
places to look first / look deepest, by analogy with how q=3's theory
works (there, ALL 1-cycles and 2-cycles were ruled out in part by showing
the *best* rational approximations of log2(3) still aren't good enough to
allow small cycles -- see Eliahou 1993, Halbeisen-Hungerbuehler 1997).

Observation worth recording: the convergent (s=3, A=7) is *exactly* the
shape-length of BOTH known nontrivial q=5 cycles (n1=17: shape (1,3,3),
A=7; n1=13: shape (1,1,5), A=7) -- i.e. the two known cycles sit exactly
at the best small rational approximation of log2(5). This is a nice
consistency check on the general philosophy (cycles cluster near CF
convergents) but is NOT itself new mathematics -- it's the expected
qualitative picture, now confirmed by direct computation for q=5's own
convergents specifically.

Practical implication for search strategy: the NEXT convergent after
(3,7) is (28,65), then (59,137), then (146,339), etc. (see output below).
These are natural "prime suspects" for where the s=4 open cycle (if it
exists) is most likely to have its total halving-count A close to (in
the same sense that q=3's non-existence results are strongest near/at
CF convergents). We attempted a direct MITM shape search AT s=28,A=65
today; it hit an 8GB RAM ceiling (see REPORT.md) before completing --
a genuine, practically-important limitation of the current pure-Python
implementation for this specific point (memory-bound, not compute-bound),
left as an explicit next step (a C reimplementation, or replacing full
value storage with a more memory-frugal encoding, would likely make this
point reachable).
"""
import mpmath as mp

mp.mp.dps = 80


def cf_expansion(x, n_terms=25):
    x = mp.mpf(x)
    terms = []
    for _ in range(n_terms):
        a = mp.floor(x)
        terms.append(int(a))
        frac = x - a
        if frac == 0:
            break
        x = 1 / frac
    return terms


def convergents(terms):
    convs = []
    h_prev2, h_prev1 = 0, 1
    k_prev2, k_prev1 = 1, 0
    for a in terms:
        h = a * h_prev1 + h_prev2
        k = a * k_prev1 + k_prev2
        convs.append((h, k))
        h_prev2, h_prev1 = h_prev1, h
        k_prev2, k_prev1 = k_prev1, k
    return convs


if __name__ == "__main__":
    log2_5 = mp.log(5) / mp.log(2)
    print("log2(5) =", log2_5)

    terms = cf_expansion(log2_5, 25)
    print("Continued fraction terms of log2(5):", terms)
    print()

    convs = convergents(terms)
    print(f"{'s (denom)':>14} {'A (numer)':>14} {'A - s*log2(5)':>16} {'(2^A-5^s)/5^s (approx)':>24}")
    for (h, k) in convs:
        if k == 0:
            continue
        diff = mp.mpf(h) - k * log2_5
        rel = mp.expm1(diff * mp.log(2))
        print(f"{k:>14} {h:>14} {float(diff):>16.3e} {float(rel):>24.3e}")

    print()
    print("Known q=5 nontrivial cycles both have s=3, A=7 -- matches the")
    print("(s=3, A=7) convergent exactly (see docstring for discussion).")
    print()
    print("Next convergents above (3,7): (28,65), (59,137), (146,339), ...")
    print("-- natural priority targets for deeper shape search, memory")
    print("permitting (see REPORT.md, 's=28,A=65 hit an 8GB RAM ceiling').")
