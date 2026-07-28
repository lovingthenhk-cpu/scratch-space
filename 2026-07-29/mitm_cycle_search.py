"""
Meet-in-the-middle (MITM) exhaustive search over Collatz-type cycle *shapes*.

Builds directly on `cycle_equation.py` (2026-07-28): a hypothetical nontrivial
cycle of the generalized map T_q(n) = n/2 (even) / q*n+1 (odd), with s odd
terms and gap-composition (a_1,...,a_s) (a_i = halvings after odd term i,
A = sum(a_i)), closes iff

    n_1 = c_{s+1} / (2^A - q^s),      c_{s+1} = sum_{i=1}^{s} q^{s-i} * 2^{B_i}

where B_1 = 0 and B_{i+1} = B_i + a_i (B_i = halvings accumulated strictly
before odd term i).

The brute-force approach (2026-07-28, `exhaustive_search` in
cycle_equation.py) enumerates ALL compositions (a_1,...,a_s) of a given total
A jointly -- cost C(A-1, s-1) (stars and bars), which explodes combinatorially
for s >~ 9-10 (886 million shapes just for s=9, A<=45).

THIS MODULE splits the s terms into a first half (i=1..k) and second half
(i=k+1..s), and observes that c_{s+1} decomposes as

    c_{s+1} = V1(a_1..a_k)  +  2^b * W(a_{k+1}..a_s)

where b = B_{k+1} = a_1+...+a_k (the halving count at the split point),
V1 depends only on the first-half composition, and W depends only on the
second-half composition (computed with its own *relative* offsets, i.e. as
if it were an independent s-k-term cycle-shape starting at offset 0 -- the
2^b factor supplies the correct absolute offset).

Divisibility by D = 2^A - q^s is then a SUBSET-SUM-style matching condition:
for a fixed split value b, we need

    W == (-V1) * inverse(2^b, D)   (mod D)

Since D is odd (2^A even minus q^s odd, q odd), 2 is invertible mod D, so
this is a well-defined modular target. We therefore:

  1. Enumerate ALL first-half compositions (of every length-k total b from
     k up to A-(s-k)), bucket the resulting V1 values by b.               -- cost ~ C(A-(s-k), k)
  2. Enumerate ALL second-half compositions (of every length-(s-k) total
     A2 from s-k up to A-k), bucket the resulting W values by A2 (and,
     within a bucket, by W mod D for O(1) average lookup).                -- cost ~ C(A-k, s-k)
  3. For each b in the first-half buckets with A-b present in the second-
     half buckets, hash-join: for each V1 in bucket b, look up whether
     (-V1 * inv(2^b,D)) mod D appears among the (W mod D) keys of bucket
     A-b; every match is checked EXACTLY (integer arithmetic, no floats)
     for true divisibility, sign, and target residue, then independently
     re-verified by forward simulation (verify_cycle, unchanged from
     cycle_equation.py) before being reported as a hit.

Complexity: instead of O(C(A-1,s-1)) (the product-like blowup of jointly
choosing all s parts), this is O(C(A-(s-k),k) + C(A-k,s-k)) -- i.e. we pay
for the two *independent* half-enumerations plus a near-linear hash join,
not their cross product. For a balanced split (k ~ s/2) this is a dramatic
reduction: e.g. for s=9, A=45 the joint count is C(44,8) = 886,163,135,
while a k=4/k=5 split gives C(40,4) + C(41,5) = 91,390 + 749,398 = 840,788
-- roughly a 1000x reduction (see benchmark_and_verify.py for a measured
side-by-side confirmation against the brute-force result).

Caveat (stated honestly): this is exact and exhaustive for the *stated*
(s, A) range -- it is not a heuristic and does not skip any shape -- but it
does NOT change the fundamental limitation noted on 2026-07-28: coverage is
still confined to whatever (s, A_max) we choose to run, and s itself is
still bounded by what's computationally reachable (the first/second half
enumerration costs still grow combinatorially in k and s-k respectively,
just with a much smaller exponent than the unsplit approach). It lets us
reach substantially larger s and A within the same time budget, nothing
more.
"""
import sys
import time
from math import comb

from cycle_equation import verify_cycle


def _enumerate_half(q, s, start_i, parts, max_total):
    """Enumerate all compositions of length `parts` (each part >= 1), for
    every possible total from `parts` up to `max_total`.

    `start_i` is the 1-indexed position of the FIRST term in this half
    within the full s-term cycle (1 for the first half; k+1 for the second
    half). Contribution of the term at local position idx (0-indexed) is
    q^(s - (start_i+idx)) * 2^(running_halving_offset), with the running
    offset starting at 0 for this half (absolute alignment for the second
    half is handled by the caller via the 2^b factor).

    Returns dict: total -> list of accumulated value V (int, exact).
    """
    buckets = {}
    a = [0] * parts

    def rec(idx, B, V, budget):
        if idx == parts:
            buckets.setdefault(B, []).append(V)
            return
        i_abs = start_i + idx
        newV = V + (q ** (s - i_abs)) * (1 << B)
        remaining_slots = parts - idx - 1
        max_v = budget - remaining_slots
        for v in range(1, max_v + 1):
            rec(idx + 1, B + v, newV, budget - v)

    rec(0, 0, 0, max_total)
    return buckets


def mitm_search_one_A(q, s, A, target_residue, target_mod, k=None):
    """Exhaustively search ALL compositions of A into s parts (i.e. exactly
    what exhaustive_search(...) would do for this single A) via
    meet-in-the-middle. Returns (hits, first_half_count, second_half_count).
    hits: list of (n1, a_tuple, A).
    """
    if k is None:
        # NOTE (perf, found empirically 2026-07-29): give the FIRST half the
        # extra part when s is odd (k = ceil(s/2), not floor). The join loop
        # builds a fresh hash table from the SECOND half's bucket for every
        # value of b; repeatedly building many small hash tables (second
        # half smaller) beats repeatedly building fewer huge ones (second
        # half larger) by ~3.7x in measured wall time for the same total
        # item count -- pure hash-table-construction overhead, not a change
        # in asymptotic complexity. See benchmark_and_verify.py.
        k = (s + 1) // 2
    if not (1 <= k <= s - 1):
        raise ValueError("k must leave both halves non-empty")

    D = (1 << A) - q ** s
    if D == 0:
        return [], 0, 0

    max_total_1 = A - (s - k)   # leave room for >=1 per second-half slot
    max_total_2 = A - k        # leave room for >=1 per first-half slot

    S1 = _enumerate_half(q, s, 1, k, max_total_1)
    S2 = _enumerate_half(q, s, k + 1, s - k, max_total_2)

    n1 = sum(len(v) for v in S1.values())
    n2 = sum(len(v) for v in S2.values())

    hits = []
    for b, v1_list in S1.items():
        t = A - b
        if t not in S2:
            continue
        w_list = S2[t]
        # bucket second half by (W mod D) for O(1) avg lookup
        modD_index = {}
        for w in w_list:
            key = w % D
            modD_index.setdefault(key, []).append(w)

        inv2b = pow(pow(2, b, D), -1, D)
        for V1 in v1_list:
            target = (-V1 * inv2b) % D
            if target in modD_index:
                for w in modD_index[target]:
                    c = V1 + (1 << b) * w
                    if c % D != 0:
                        continue  # spurious mod-collision, not a real solution
                    cand_n1 = c // D
                    if cand_n1 <= 0:
                        continue
                    if cand_n1 % target_mod != target_residue:
                        continue
                    # reconstruct the actual (a_1..a_s) tuple is not directly
                    # available from V1/W alone without re-deriving; instead
                    # we verify by forward simulation using ONLY (q, cand_n1)
                    # and the *shape length* A -- verify_cycle needs the
                    # explicit a-tuple, so instead we do a direct forward walk
                    # here that reconstructs the a_i's from the trajectory.
                    ok, a_tuple = _forward_reconstruct_and_check(q, cand_n1, s, A)
                    if ok:
                        hits.append((cand_n1, a_tuple, A))
    return hits, n1, n2


def _forward_reconstruct_and_check(q, n1, s, A):
    """Independent verification: walk forward from n1 for s odd-steps,
    recording the actual halving counts, and confirm (a) all terms are
    positive odd integers, (b) it closes back to n1 after exactly s odd
    steps, (c) the total halving count equals A. This is fully independent
    of the V1/W bookkeeping above -- it re-derives (a_1..a_s) from scratch
    by direct simulation, so it cannot inherit a bug from the MITM indexing."""
    n = n1
    a = []
    for _ in range(s):
        if n <= 0 or n % 2 == 0:
            return False, None
        m = q * n + 1
        cnt = 0
        while m % 2 == 0:
            m //= 2
            cnt += 1
        a.append(cnt)
        n = m
    closes = (n == n1)
    total_A = sum(a)
    return (closes and total_A == A), tuple(a)


def mitm_exhaustive_search(q, target_residue, target_mod, s, A_max, k=None, log_every=None):
    """Drop-in replacement for cycle_equation.exhaustive_search, but using
    MITM per A value. Returns (hits, total_shapes_equivalent, elapsed)."""
    hits_all = []
    total_equiv = 0
    t0 = time.time()
    for A in range(s, A_max + 1):
        hits, n1c, n2c = mitm_search_one_A(q, s, A, target_residue, target_mod, k=k)
        total_equiv += comb(A - 1, s - 1)  # what brute force would have paid
        hits_all.extend(hits)
        if log_every and A % log_every == 0:
            print(f"  [MITM] s={s} A up to {A}: brute-force-equivalent shapes "
                  f"so far {total_equiv:,}, hits so far {len(hits_all)}, "
                  f"{time.time()-t0:.1f}s elapsed", file=sys.stderr)
    return hits_all, total_equiv, time.time() - t0


if __name__ == "__main__":
    # ---- Correctness self-tests ----
    print("=== Self-test 1: rediscover known q=5 cycles ===")
    # n1=17, shape (1,3,3), A=7, s=3
    hits, n1c, n2c = mitm_search_one_A(5, 3, 7, target_residue=17 % 5, target_mod=5)
    print(f"  s=3,A=7 target n1%5=={17%5}: hits={hits}  (expect n1=17 present)")

    # n1=13, shape (1,1,4), A=6, s=3
    hits2, _, _ = mitm_search_one_A(5, 3, 6, target_residue=13 % 5, target_mod=5)
    print(f"  s=3,A=6 target n1%5=={13%5}: hits={hits2}  (expect n1=13 present)")

    # trivial n1=1, shape (1,4), A=5, s=2
    hits3, _, _ = mitm_search_one_A(5, 2, 5, target_residue=1 % 5, target_mod=5)
    print(f"  s=2,A=5 target n1%5=={1%5}: hits={hits3}  (expect n1=1 present)")
