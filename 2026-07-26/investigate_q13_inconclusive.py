#!/usr/bin/env python3
"""
Follow-up on a curiosity noticed while re-verifying 2026-07-25's sweep_cycles.c
results with the new epoch-based sweep_cycles_v2.c: for q=13, sweeping odd
n in [1, 3*10^6] finds exactly 32 values that are "inconclusive" (neither
reach 1, nor close a cycle, nor exceed the divergence threshold within
MAX_STEPS=20000 steps) -- and BOTH the old and new (totally different hash
table implementation) code agree on the exact same 32 witnesses, evenly
spaced 65536 apart:
    947293, 1012829, 1078365, ..., 2978909   (32 values, step 65536)

Two independent implementations agreeing rules out a hash-table bug in
either one. So this is a real dynamical phenomenon: these particular n
take unusually long (>20000 steps) to resolve under T_13. This script
uses Python bignums (no overflow, no threshold silently truncating) to
just let them run much longer and see what actually happens.
"""
import sys

def walk_unbounded(n0, q, max_steps=2_000_000, diverge_threshold=10**60):
    n = n0
    seen = {}
    for step in range(max_steps):
        if n == 1:
            return ("REACHED_ONE", step)
        if n in seen:
            return ("CYCLE", step - seen[n], seen[n])
        seen[n] = step
        if n % 2 == 0:
            n //= 2
        else:
            n = q * n + 1
        if n > diverge_threshold and step > 30:
            return ("DIVERGED", step + 1, n)
    return ("STILL_GOING", max_steps, n)

if __name__ == "__main__":
    q = 13
    witnesses = list(range(947293, 3_000_000, 65536))
    print(f"q={q}, checking {len(witnesses)} witnesses with max_steps=2,000,000 and threshold=1e60")
    for n0 in witnesses:
        result = walk_unbounded(n0, q)
        print(n0, result)
        sys.stdout.flush()
