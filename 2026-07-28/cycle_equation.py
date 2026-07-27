"""
Cycle-equation (shape-based) search for nontrivial cycles of the generalized
Collatz map T_q(n) = n/2 (n even), q*n+1 (n odd).

Background / why this is a DIFFERENT method from the trajectory sweep
(sweep_cycles_v2.c) used on 2026-07-25/26/27:

  The trajectory sweep picks a starting value n0, walks forward, and asks
  "does this walk hit a cycle we haven't seen, within n0 <= LIMIT?". It can
  only ever find cycles that have SOME element <= LIMIT (since we sweep all
  odd starting points up to LIMIT, and a cycle is a fixed set of numbers, if
  any element of the cycle is <= LIMIT the sweep's walk starting exactly at
  that element will re-discover it immediately). So each day we can only
  push the LIMIT higher and higher, forever narrowing but never closing the
  literature's open question (Sultan 2020, Remark 3): "does an n=4 mod 5
  nontrivial cycle exist at all?" -- a trajectory sweep can never answer
  "no" for certain, only "not below X".

  The cycle-equation method instead parametrizes cycles by their SHAPE:
  the number of odd terms s, and the multiset of "gap" values a_1..a_s
  (number of halvings after each odd term before the next odd term). Given
  a shape (a_1,...,a_s), there is EXACTLY ONE real number n_1 that would
  close a cycle with that shape (derived below), and it's rational with a
  denominator (2^A - q^s) where A = a_1+...+a_s. So instead of guessing
  starting values, we enumerate shapes directly and solve for n_1 exactly
  (arbitrary-precision rational arithmetic -- no floating point, so no
  wrong answers from rounding). This lets us rule out ALL cycles of a given
  "total length" L = s + A in one pass, regardless of how large n_1 would
  have been -- a genuinely different axis of exhaustiveness than "n0 up to
  10^10", and directly attacks the open question rather than just growing
  a lower bound on it.

  Caveat (stated honestly, not to be glossed over): full enumeration of all
  compositions (a_1,...,a_s) of A is exponential in s (C(A-1,s-1)
  compositions for fixed s,A), so this method is only exhaustive up to
  modest s. For larger s we fall back to a bounded window around the
  "near-optimal ratio" region A/s ~ log2(q) (justified below), which is a
  heuristic restriction, NOT a proof -- documented as such throughout.

Derivation of the closed form
------------------------------
Let n_1 be an odd term of a hypothetical cycle, and (a_1,...,a_s) the
number of halving-steps following each of the s odd terms before the next
odd term (a_i >= 1), with A = sum(a_i) (so total trajectory length,
counting every individual step, is L = s + A).

Track n_i as an affine function of the unknown n_1:
    n_i = (q^(i-1) * n_1 + c_i) / 2^(b_i)
with c_1 = 0, b_1 = 0, and recurrence (derived by substituting n_i into
q*n_i + 1, dividing by 2^(a_i) to reach n_{i+1}):
    c_{i+1} = q*c_i + 2^(b_i)
    b_{i+1} = b_i + a_i

After s steps the cycle must close: n_{s+1} = n_1, i.e.
    n_1 = (q^s * n_1 + c_{s+1}) / 2^A         (A = b_{s+1})
 => n_1 * (2^A - q^s) = c_{s+1}
 => n_1 = c_{s+1} / (2^A - q^s)

This is exact integer/rational arithmetic throughout (no floats), so the
final integrality check (does the denominator divide c_{s+1} exactly?) is
airtight.

Verification: every candidate n_1 that passes the integrality + positivity
+ residue checks is ADDITIONALLY verified by literally simulating the walk
forward for s odd-steps using ordinary Python big integers, confirming (a)
every n_i visited is a positive odd integer, (b) the number of halving
steps after each n_i exactly matches the assumed a_i (not more, not
fewer -- this is essential: if the true 2-adic valuation of q*n_i+1 were
larger than the assumed a_i, dividing by only 2^(a_i) would leave an EVEN
number, which cannot be an "odd term" of the cycle, so that candidate must
be rejected), and (c) the walk actually returns to n_1 after s odd steps.
Only candidates surviving this independent simulation are reported.
"""
import sys
import time

def solve_shape(q, a):
    """a = (a_1, ..., a_s) tuple of positive ints. Returns (n1, A) or None."""
    s = len(a)
    c = 0
    b = 0
    for i in range(s):
        c = q * c + (1 << b)
        b = b + a[i]
    A = b
    denom = (1 << A) - q ** s
    if denom == 0:
        return None
    if c % denom != 0:
        return None
    n1 = c // denom
    if n1 <= 0:
        return None
    return (n1, A)

def verify_cycle(q, n1, a):
    """Simulate forward and check the shape (a_1..a_s) is EXACTLY reproduced,
    all terms positive odd integers, and it closes back to n1."""
    s = len(a)
    n = n1
    visited = [n1]
    for i in range(s):
        if n <= 0 or n % 2 == 0:
            return False
        m = q * n + 1
        cnt = 0
        while m % 2 == 0:
            m //= 2
            cnt += 1
        if cnt != a[i]:
            return False
        n = m
        if i < s - 1:
            visited.append(n)
    return n == n1

def compositions(total, parts):
    """Yield all compositions (ordered tuples of positive ints) of `total`
    into exactly `parts` parts. Standard stars-and-bars recursive generator."""
    if parts == 1:
        if total >= 1:
            yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in compositions(total - first, parts - 1):
            yield (first,) + rest

def exhaustive_search(q, target_residue, target_mod, s, A_max, log_every=None):
    """Exhaustively enumerate ALL compositions (a_1..a_s) with A = sum(a)
    ranging from s to A_max. Returns list of (n1, a, A) hits."""
    hits = []
    count = 0
    t0 = time.time()
    for A in range(s, A_max + 1):
        for a in compositions(A, s):
            count += 1
            res = solve_shape(q, a)
            if res is None:
                continue
            n1, Areturned = res
            if n1 % target_mod == target_residue:
                if verify_cycle(q, n1, a):
                    hits.append((n1, a, Areturned))
        if log_every and A % log_every == 0:
            print(f"  s={s} A up to {A}: {count} compositions checked so far, "
                  f"{len(hits)} hits, {time.time()-t0:.1f}s elapsed", file=sys.stderr)
    return hits, count, time.time() - t0

if __name__ == "__main__":
    # Sanity check 1: rediscover the two KNOWN q=5 nontrivial cycles
    # (h=2 mod 5 rep: n1=17, and h=3 mod 5 rep: n1=13) using their actual
    # shapes, to confirm the formula + verifier are correct.
    # From the trajectory: 17 -> 86 -> 43 -> 216 -> 108 -> 54 -> 27 -> 136 -> 68 -> 34 -> 17
    # odd terms: 17, 43, 27  (s=3)
    # gaps: 17->86->43 (1 halving, a1=1); 43->216->108->54->27 (3 halvings, a2=3);
    #       27->136->68->34->17 (3 halvings, a3=3)
    print("Sanity check: known cycle from n1=17, shape s=3, a=(1,3,3)")
    res = solve_shape(5, (1, 3, 3))
    print("  solve_shape ->", res, " (expect n1=17, A=7)")
    print("  verify ->", verify_cycle(5, 17, (1, 3, 3)))

    print("Sanity check: known cycle from n1=13, shape a=(?,?,?) -- searching")
    # 13 -> 66 -> 33 -> 166 -> 83 -> 416 -> 208 -> 104 -> 52 -> 26 -> 13
    # odd terms: 13, 33, 83 (s=3)
    # gaps: 13->66->33 (1 halving, a1=1); 33->166->83 (1 halving, a2=1);
    #       83->416->208->104->52->26->13 (4 halvings, a3=4)
    res2 = solve_shape(5, (1, 1, 4))
    print("  solve_shape ->", res2, " (expect n1=13, A=6)")
    print("  verify ->", verify_cycle(5, 13, (1, 1, 4)))

    # Sanity check 2: trivial cycle n1=1 (h=1 mod 5), shape (1,4) found earlier by hand
    print("Sanity check: trivial cycle n1=1, shape s=2, a=(1,4)")
    res3 = solve_shape(5, (1, 4))
    print("  solve_shape ->", res3, " (expect n1=1, A=5)")
    print("  verify ->", verify_cycle(5, 1, (1, 4)))

    # Sanity check 3: s=1 has NO solution for q=5 (no length-1 cycle for q=5,
    # since 2^a - 5 = 1 has no integer solution a)
    print("Sanity check: s=1 exhaustive up to A=64 should find nothing")
    hits, cnt, dt = exhaustive_search(5, 4, 5, 1, 64)
    print(f"  {cnt} shapes checked in {dt:.3f}s, hits={hits}")
