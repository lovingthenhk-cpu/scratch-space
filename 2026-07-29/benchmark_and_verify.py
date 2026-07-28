"""
Correctness + speed benchmark for the meet-in-the-middle (MITM) cycle-shape
search (mitm_cycle_search.py), run 2026-07-29.

Part 1 (correctness): re-derive the three known q=5 cycles (trivial n1=1,
nontrivial n1=17, nontrivial n1=13) via MITM and confirm they match the
values independently confirmed by brute force (cycle_equation.py, 2026-07-28).

NOTE: while doing this, we discovered that cycle_equation.py's OWN __main__
self-test for n1=13 was actually testing the WRONG shape: it asserted
shape (1,1,4) [A=6], which does not solve at all (solve_shape returns None),
even though 2026-07-28's REPORT.md claims all three known cycles were
"confirmed reproduced." Running cycle_equation.py directly today
reproduces this: the n1=13 self-test prints "solve_shape -> None" /
"verify -> False", i.e. it silently failed and the failure was not
caught before writing the "confirmed" claim in the report. The CORRECT
shape for n1=13 is (1,1,5), A=7 (verified below and by direct trajectory
simulation: 13 -[x5]-> 33 -[x1]-> wait, the correct forward trajectory is
13->66->33 (1 halving), 33->166->83 (1 halving), 83->416->208->104->52->26->13
(5 halvings), so a=(1,1,5), A=7 -- NOT (1,1,4), A=6 as previously written
in cycle_equation.py's self-test). This does not affect the validity of
2026-07-28's main exhaustive_search results (those call solve_shape/
compositions/verify_cycle directly and do not depend on the buggy
__main__ block), but the "all three known cycles confirmed" claim in
2026-07-28's REPORT.md was not actually true as stated -- only 2 of 3
self-tests in the code actually passed that day. Flagging and correcting
here per this project's rule to be honest about verification claims.

Part 2 (speed): reproduce the s=9, A<=45 brute-force sweep (886,163,135
shapes, 2026-07-28, 1926.6s/33.5s for A=9..45 across all 9 sub-sweeps
+ the s=1..8 sweep) via MITM and confirm (a) identical brute-force-
equivalent shape count, (b) identical result (zero hits), (c) the wall
time speedup.
"""
import time
from cycle_equation import solve_shape, verify_cycle
from mitm_cycle_search import mitm_search_one_A, mitm_exhaustive_search

print("=" * 70)
print("PART 1: correctness -- rediscover known q=5 cycles via MITM")
print("=" * 70)

print("\n-- trivial cycle n1=1, shape (1,4), s=2, A=5 --")
hits, _, _ = mitm_search_one_A(5, 2, 5, target_residue=1 % 5, target_mod=5)
print("MITM hits (target n1%5==1):", hits)
assert any(h[0] == 1 for h in hits), "FAILED to rediscover n1=1"
print("solve_shape/verify_cycle cross-check:", solve_shape(5, (1, 4)), verify_cycle(5, 1, (1, 4)))

print("\n-- nontrivial cycle n1=17, shape (1,3,3), s=3, A=7 --")
hits, _, _ = mitm_search_one_A(5, 3, 7, target_residue=17 % 5, target_mod=5)
print("MITM hits (target n1%5==2):", hits)
assert any(h[0] == 17 for h in hits), "FAILED to rediscover n1=17"
print("solve_shape/verify_cycle cross-check:", solve_shape(5, (1, 3, 3)), verify_cycle(5, 17, (1, 3, 3)))

print("\n-- nontrivial cycle n1=13 -- CORRECTED shape (1,1,5) [not (1,1,4) as")
print("   mistakenly self-tested in 2026-07-28's cycle_equation.py], s=3, A=7 --")
hits, _, _ = mitm_search_one_A(5, 3, 7, target_residue=13 % 5, target_mod=5)
print("MITM hits (target n1%5==3):", hits)
assert any(h[0] == 13 for h in hits), "FAILED to rediscover n1=13"
print("solve_shape/verify_cycle cross-check (CORRECT shape (1,1,5)):",
      solve_shape(5, (1, 1, 5)), verify_cycle(5, 13, (1, 1, 5)))
print("solve_shape cross-check (WRONG shape (1,1,4), as previously self-tested):",
      solve_shape(5, (1, 1, 4)), "<- None/False confirms yesterday's self-test typo")

print("\nAll three known q=5 cycles correctly rediscovered by MITM. PASS.")

print()
print("=" * 70)
print("PART 2: speed -- reproduce s=9, A in [9,45] (2026-07-28 brute force)")
print("=" * 70)
t0 = time.time()
hits, total_equiv, dt = mitm_exhaustive_search(5, 4, 5, 9, 45)
print(f"MITM: {total_equiv:,} shapes-equivalent, {dt:.2f}s, hits={hits}")
print("2026-07-28 brute force (run_s9.py, from repo log): 886,163,135 shapes, 1926.6s, hits=[]")
assert total_equiv == 886163135, "shape count mismatch vs 2026-07-28 brute force!"
assert hits == [], "hit count mismatch vs 2026-07-28 brute force (expected zero hits)!"
speedup = 1926.6 / dt
print(f"Speedup: {speedup:.0f}x (same exact result: 0 hits, same 886,163,135 shapes covered)")
