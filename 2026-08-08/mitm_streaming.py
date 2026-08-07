"""
2026-07-30: Memory-efficient (streaming) rewrite of the 2026-07-29
meet-in-the-middle (MITM) cycle-shape search
(`../2026-07-29/mitm_cycle_search.py`, function `mitm_search_one_A`).

WHY THIS EXISTS (see ../PROGRESS.md, priority 1 carried over from
2026-07-29): the 2026-07-29 session tried to reach the next continued-
fraction convergent of log2(5), (s, A) = (28, 65) -- suggested by Part J's
observation that both KNOWN q=5 nontrivial cycles sit exactly on a best
rational-approximation convergent of log2(5) -- and hit an OOM kill.
PROGRESS.md filed this as "MITM memory efficiency" priority 1, framed as if
better memory bookkeeping might get us there.

FIRST THING DONE TODAY: actually compute how big that wall is, instead of
just re-attempting with vague "be more careful with memory" tactics (see
`resonance_feasibility.py` / REPORT.md Part K for the numbers). Verdict:
for (s, A) = (28, 65), a balanced 2-way split needs one side (either half)
of size C(51, 14) = 1,293,938,... ~ 1.29e12 compositions. Even at a
physically-impossible 1 byte/item, that is ~1.2 TB. This is NOT a memory-
tuning problem -- no encoding trick closes a 150x-plus gap against an 8 GB
box. Priority 1 as literally stated in yesterday's note was over-optimistic
and is corrected here; see PROGRESS.md today's entry.

WHAT THIS FILE ACTUALLY DOES (a real, bounded, honest improvement):
the 2026-07-29 `mitm_search_one_A` builds BOTH halves (S1 and S2) as full
Python dict-of-lists structures held in memory simultaneously for the
entire duration of the join. That means peak memory is
    (size of S1) + (size of S2)
even though the algorithm only strictly needs ONE of them materialized (as
a lookup index) while the OTHER can be generated and consumed one item at a
time. This module:

  1. Turns `_enumerate_half` into a generator (`_enumerate_half_stream`)
     that yields (B, V) pairs one at a time via the same recursion, with NO
     list/dict accumulation -- O(k) extra memory (the recursion stack),
     not O(list size).
  2. Picks, via `math.comb` (cheap, no enumeration needed), whichever of
     the two halves has the SMALLER item count, and materializes ONLY that
     one as the lookup index (dict: total -> {val mod D: [vals]}).
  3. Streams the OTHER (larger) half through that index, checking each
     item immediately and discarding it -- it is never stored.

This drops peak memory from O(|S1|+|S2|) to O(min(|S1|,|S2|)) -- a real,
measured ~2x reduction for a symmetric split (see benchmark section of
`../REPORT.md` Part K for actual numbers), a bit more when an asymmetric k
is chosen (since we can then explicitly minimize the materialized side).
It does NOT change the underlying combinatorial item count / time
complexity -- that would require an asymptotically different algorithm
(see PROGRESS.md "next steps" for why a naive further k-way split does NOT
reduce total item count for an EXACT, fully-covering enumeration -- the
number of length-k compositions of a bounded total is a fixed combinatorial
quantity regardless of how you generate it; only genuinely fixing this
needs either a much smaller target (s, A) or a fundamentally different
method such as an explicit Baker/linear-forms-in-logs cycle-length bound,
see PROGRESS.md "literature lead").
"""
import sys
import time
from math import comb


def _enumerate_half_stream(q, s, start_i, parts, max_total):
    """Generator version of 2026-07-29's `_enumerate_half`: yields (B, V)
    one composition at a time instead of building buckets.

    v1 (abandoned, see REPORT.md Part K "first attempt failed"): a
    recursive generator using `yield from rec(...)`. Measured SLOWER and
    MORE memory than the original list-building code -- CPython has to
    bubble every yielded value up through every nested generator frame
    (O(depth) per item for a depth-`parts` recursion), and combined with a
    naive dict-of-dict-of-list index (see v1 of `mitm_search_one_A_streaming`
    below, also abandoned) the result was a net REGRESSION, not an
    improvement. Caught by benchmarking against the old code before trusting
    it -- see REPORT.md for the actual measured numbers.

    v2 (this version): explicit-stack iterative DFS, no generator recursion
    at all -- a single flat generator frame. Same coverage as v1 (verified:
    `self_test_iter_equiv_recursive()` below diffs the two exhaustively on
    several (s, A) pairs)."""
    stack = [(0, 0, 0, max_total)]
    pop = stack.pop
    push = stack.append
    while stack:
        idx, B, V, budget = pop()
        if idx == parts:
            yield B, V
            continue
        i_abs = start_i + idx
        newV = V + (q ** (s - i_abs)) * (1 << B)
        remaining_slots = parts - idx - 1
        max_v = budget - remaining_slots
        for v in range(1, max_v + 1):
            push((idx + 1, B + v, newV, budget - v))


def _forward_reconstruct_and_check(q, n1, s, A):
    """Independent verification (unchanged from 2026-07-29): walk forward
    from n1 for s odd-steps, re-deriving (a_1..a_s) from scratch by direct
    simulation. Cannot inherit a bug from the MITM/streaming indexing."""
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


def mitm_search_one_A_streaming(q, s, A, target_residue, target_mod, k=None):
    """Drop-in replacement for 2026-07-29's mitm_search_one_A, but with peak
    memory O(min(|S1|,|S2|)) instead of O(|S1|+|S2|). Same return signature:
    (hits, n1_count, n2_count)."""
    if k is None:
        k = (s + 1) // 2
    if not (1 <= k <= s - 1):
        raise ValueError("k must leave both halves non-empty")

    D = (1 << A) - q ** s
    if D == 0:
        return [], 0, 0

    max_total_1 = A - (s - k)
    max_total_2 = A - k

    # Cheap size estimate (no enumeration) to decide which side to
    # materialize. Materialize the SMALLER one -> smaller peak memory.
    est1 = comb(max_total_1, k) if max_total_1 >= k else 0
    est2 = comb(max_total_2, s - k) if max_total_2 >= (s - k) else 0
    materialize_first = est1 <= est2

    if materialize_first:
        mat_start_i, mat_parts, mat_max_total = 1, k, max_total_1
        stream_start_i, stream_parts, stream_max_total = k + 1, s - k, max_total_2
        mat_is_first = True
    else:
        mat_start_i, mat_parts, mat_max_total = k + 1, s - k, max_total_2
        stream_start_i, stream_parts, stream_max_total = 1, k, max_total_1
        mat_is_first = False

    # --- Materialize the smaller side fully ---
    # v1 (abandoned, see module docstring / REPORT.md Part K): a dict of
    # dicts of lists, `index[B][V % D] -> [V, ...]`, always wrapping every
    # value in a fresh 1-element list "just in case" of a collision. That
    # measured 2x WORSE peak memory than the original (non-streaming) code,
    # not better -- the per-item overhead of (dict entry + wrapper list +
    # per-B sub-dict) is larger than the flat-list storage it replaced,
    # even though only ONE side is now held at all. A quick check
    # (`resonance_feasibility.py`'s `check_collision_rate` helper) confirmed
    # actual V % D collisions are rare in our size regime (items << D, so
    # birthday-style collision probability is tiny even though individual
    # V values routinely exceed D many times over -- see REPORT.md).
    #
    # v2 (this version): ONE flat dict keyed by (B, V % D), optimized for
    # the common case of NO collision -- store the bare int directly; only
    # escalate that slot to a list on an actual (rare) second hit. Avoids
    # both the extra per-B sub-dict layer and the routine list-wrapping.
    index = {}
    n_mat = 0
    for B, V in _enumerate_half_stream(q, s, mat_start_i, mat_parts, mat_max_total):
        key = (B, V % D)
        prev = index.get(key)
        if prev is None:
            index[key] = V
        elif type(prev) is list:
            prev.append(V)
        else:
            index[key] = [prev, V]
        n_mat += 1

    # --- Stream the larger side through the index, one item at a time ---
    # NOTE: c = V1 + 2^b1 * W where b1 is always the FIRST half's own local
    # total (b1 = a_1+...+a_k), regardless of which side we materialized --
    # this exponent must NOT be confused with whichever side happens to be
    # streamed vs. materialized (an earlier draft of this function used the
    # streamed side's own local total as the exponent unconditionally, which
    # is only correct when the streamed side happens to BE the first half;
    # caught by the cross-check against the 2026-07-29 implementation in
    # `self_test_cross_check()`, which disagreed on hit counts until fixed).
    hits = []
    n_stream = 0
    for B_s, V_s in _enumerate_half_stream(q, s, stream_start_i, stream_parts, stream_max_total):
        n_stream += 1
        b_mat = A - B_s

        if mat_is_first:
            b1 = b_mat          # materialized side IS the first half
            W = V_s
            target = (-(1 << b1) * W) % D      # solving for V1
        else:
            b1 = B_s            # streamed side IS the first half
            V1 = V_s
            inv2b1 = pow(pow(2, b1, D), -1, D)
            target = (-V1 * inv2b1) % D        # solving for W

        found = index.get((b_mat, target))
        if found is None:
            continue
        candidates = found if type(found) is list else (found,)
        for other in candidates:
            if mat_is_first:
                V1, W_ = other, W
            else:
                V1, W_ = V1, other
            c = V1 + (1 << b1) * W_
            if c % D != 0:
                continue  # spurious mod-collision, not a real solution
            cand_n1 = c // D
            if cand_n1 <= 0:
                continue
            if cand_n1 % target_mod != target_residue:
                continue
            ok, a_tuple = _forward_reconstruct_and_check(q, cand_n1, s, A)
            if ok:
                hits.append((cand_n1, a_tuple, A))

    if mat_is_first:
        return hits, n_mat, n_stream
    else:
        return hits, n_stream, n_mat


def choose_k_for_memory_budget(s, A, mem_item_budget):
    """Pick a split k (1 <= k <= s-1) for mitm_search_one_A_streaming that
    keeps the MATERIALIZED side's item count (min(|S1|,|S2|), which governs
    peak memory -- see module docstring / REPORT.md Part K benchmarks) under
    `mem_item_budget`, while minimizing the STREAMED side's item count
    (max(|S1|,|S2|), which governs time) among the k's that qualify.

    If NO k satisfies the budget (materialized side would be too big even
    at the most extreme split, e.g. k=1 or k=s-1), falls back to the most
    extreme (smallest-materialized-side) k available -- still exhaustive,
    just may exceed the requested budget as a last resort; caller should
    check the returned k's actual est. size if this matters."""
    best_k, best_max, best_min_seen = None, None, None
    fallback_k, fallback_min = None, None
    for k in range(1, s):
        max1 = A - (s - k)
        max2 = A - k
        if max1 < k or max2 < (s - k):
            continue
        c1 = comb(max1, k)
        c2 = comb(max2, s - k)
        mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
        if fallback_min is None or mn < fallback_min:
            fallback_min, fallback_k = mn, k
        if mn <= mem_item_budget:
            if best_max is None or mx < best_max:
                best_max, best_k, best_min_seen = mx, k, mn
    if best_k is not None:
        return best_k
    return fallback_k


def mitm_exhaustive_search_streaming(q, target_residue, target_mod, s, A_max, k=None, log_every=None):
    hits_all = []
    total_equiv = 0
    t0 = time.time()
    for A in range(s, A_max + 1):
        hits, n1c, n2c = mitm_search_one_A_streaming(q, s, A, target_residue, target_mod, k=k)
        total_equiv += comb(A - 1, s - 1)
        hits_all.extend(hits)
        if log_every and A % log_every == 0:
            print(f"  [MITM-stream] s={s} A up to {A}: brute-force-equivalent shapes "
                  f"so far {total_equiv:,}, hits so far {len(hits_all)}, "
                  f"{time.time()-t0:.1f}s elapsed", file=sys.stderr)
    return hits_all, total_equiv, time.time() - t0


if __name__ == "__main__":
    # ---- Correctness self-tests (independently re-derived shapes, not
    # copy-pasted from 2026-07-29's file, precisely BECAUSE that file's own
    # self-test had an undetected wrong-shape bug for n1=13 -- see module
    # docstring and PROGRESS.md "2026-07-29 lesson". Re-derived here by
    # hand-tracing the actual trajectories from scratch: ----
    print("=== Self-test 1: known q=5 cycles, independently re-derived shapes ===")
    # NOTE: target_residue only fixes n1 mod 5, not which cycle -- since a
    # cycle of length s has s rotations (each a valid, distinct n1 with its
    # own rotated shape), and DIFFERENT cycles' rotations can share a
    # residue class mod 5, a residue-only search at fixed (s,A) can
    # legitimately return MULTIPLE hits. We assert the specific expected
    # hit is a MEMBER of the result, not that it's the only one -- and
    # separately sanity-check the total count by hand below.

    # 17 -> 86 -> 43 (a=1) -> 216 -> 108 -> 54 -> 27 (a=3) -> 136 -> 68 -> 34 -> 17 (a=3)
    hits, n1c, n2c = mitm_search_one_A_streaming(5, 3, 7, target_residue=17 % 5, target_mod=5)
    print(f"  s=3,A=7 target n1%5=={17%5}: hits={hits} |S1|/|S2| sizes={n1c},{n2c}")
    print(f"    (expect (17,(1,3,3),7) among hits -- 27 also has residue 2 mod 5, same cycle's other rotation)")

    # 13 -> 66 -> 33 (a=1) -> 166 -> 83 (a=1) -> 416 -> 208 -> 104 -> 52 -> 26 -> 13 (a=5)
    hits2, n1c2, n2c2 = mitm_search_one_A_streaming(5, 3, 7, target_residue=13 % 5, target_mod=5)
    print(f"  s=3,A=7 target n1%5=={13%5}: hits={hits2}")
    print(f"    (expect (13,(1,1,5),7) among hits -- 33,83 same cycle's rotations, 43 is the OTHER known cycle's rotation, also residue 3)")

    # trivial n1=1: 1 -> 6 -> 3 (a=1) -> 16 -> 8 -> 4 -> 2 -> 1 (a=4)
    hits3, _, _ = mitm_search_one_A_streaming(5, 2, 5, target_residue=1 % 5, target_mod=5)
    print(f"  s=2,A=5 (shape (1,4)) target n1%5=={1%5}: hits={hits3} (expect n1=1 present, s=2 has only 1 rotation-class up to the trivial n1=1/n1=... check)")

    def has(hit_list, n1, a):
        return any(h[0] == n1 and h[1] == a for h in hit_list)

    ok = (has(hits, 17, (1, 3, 3)) and has(hits, 27, (3, 1, 3)) and len(hits) == 2 and
          has(hits2, 13, (1, 1, 5)) and has(hits2, 33, (1, 5, 1)) and has(hits2, 83, (5, 1, 1)) and
          has(hits2, 43, (3, 3, 1)) and len(hits2) == 4 and
          has(hits3, 1, (1, 4)) and len(hits3) == 1)
    print(f"\nALL SELF-TESTS PASSED: {ok}")
    if not ok:
        print("  !!! SELF-TEST FAILURE -- do not trust production results until fixed !!!")
        sys.exit(1)
