"""
2026-08-04: small, cautious, ISOLATED probe toward next-steps item #4 from
2026-08-03's PROGRESS.md ("MEM_ITEM_BUDGET further raise, backed by real
measurement"). This is intentionally kept OUT of the main 2-core production
run (run_production_streaming_v6.py) so that a new, less-tested variable
(a higher MEM_ITEM_BUDGET) isn't bundled into a multi-hour job that also
needs to bank the s=9/10/12 catch-up progress reliably.

What this does: for a small set of (s, A) pairs that are CONFIRMED stuck at
their natural ceiling under the current MEM_ITEM_BUDGET=15,000,000 (see
run_production_streaming_v6.py's own s=13/16/18 "NATURAL ceiling" stop
messages this session), re-run choose_k_for_memory_budget() at a slightly
higher budget (18,000,000, a modest +20% over the validated 15,000,000 --
NOT the more aggressive 25,000,000+ 2026-08-03's memory data hinted might
also be safe) and check whether a better (more balanced) k becomes available
that brings the estimated streamed-side time back under the 900s per-A
limit. Where it does, actually RUN that single A step (single process, no
concurrent second process -- this script is not meant to run alongside
another heavy job) while sampling this process's own RSS every 2s, so the
memory claim is checked against a REAL measurement, not just the
158-183 bytes/item formula from 2026-08-02.

Why 18,000,000 and not higher: 2026-08-03 measured a real concurrent 2-process
peak of ~3.66 GiB at budget=15,000,000 (68% of the ~5.4 GiB theoretical
worst case for that budget); TODAY's main production run (see
memory_monitor_log.csv) measured an even lower real concurrent peak of only
~2.27 GiB at the SAME 15,000,000 budget for a different (s,A) mix. Both
real data points sit well under the 7.84 GiB actual sandbox total, but this
probe deliberately does not try to leap straight to the most aggressive
value those numbers could in principle support -- it takes one modest,
checkable step (roughly proportional: 5.4 GiB * 18/15 =~ 6.5 GiB theoretical
worst case, still with >1 GiB of headroom against 7.84 GiB even in a
single-process run) and records what actually happens, so a FUTURE session
can decide the next increment from two real data points instead of one.
"""
import json
import subprocess
import sys
import time
from math import comb

from mitm_streaming import choose_k_for_memory_budget

OLD_BUDGET = 15_000_000
NEW_BUDGET = 18_000_000
PER_A_TIME_LIMIT = 900.0
EMPIRICAL_RATE = 1_000_000

CANDIDATES = [(13, 59), (16, 48), (18, 45)]  # all confirmed stuck this session under OLD_BUDGET

print("=== checking which stuck (s,A) unlock at NEW_BUDGET ===", flush=True)
to_run = []
for s, A in CANDIDATES:
    k_old = choose_k_for_memory_budget(s, A, OLD_BUDGET)
    k_new = choose_k_for_memory_budget(s, A, NEW_BUDGET)

    def est(s, A, k):
        max1 = A - (s - k)
        max2 = A - k
        c1 = comb(max1, k) if max1 >= k else 0
        c2 = comb(max2, s - k) if max2 >= (s - k) else 0
        mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
        return mn, mx, mx / EMPIRICAL_RATE

    mn_old, mx_old, est_old = est(s, A, k_old)
    mn_new, mx_new, est_new = est(s, A, k_new)
    unlocked = est_new <= PER_A_TIME_LIMIT and est_old > PER_A_TIME_LIMIT
    print(f"s={s:2d} A={A:3d}  old(k={k_old}, mat={mn_old:.3e}, est={est_old:7.1f}s)  "
          f"new(k={k_new}, mat={mn_new:.3e}, est={est_new:7.1f}s)  unlocked={unlocked}", flush=True)
    if unlocked:
        to_run.append((s, A, k_new, mn_new, mx_new, est_new))

print(f"\n=== {len(to_run)} candidate(s) unlocked at budget={NEW_BUDGET:,}: "
      f"{[(s, A) for s, A, *_ in to_run]} ===", flush=True)

if not to_run:
    print("Nothing unlocked at this budget level -- probe ends here with no run needed.", flush=True)
    with open("raise_budget_probe_results.json", "w") as f:
        json.dump({"new_budget": NEW_BUDGET, "unlocked": [], "runs": []}, f, indent=2)
    sys.exit(0)

# Run each unlocked candidate in its OWN subprocess (isolated, single process,
# no concurrent second job) with a memory sampler polling its RSS.
runs = []
for s, A, k, mn, mx, est_time in to_run:
    print(f"\n=== running s={s} A={A} k={k} (isolated single process, real memory sample) ===", flush=True)
    worker_code = (
        "import json,time,sys\n"
        "from mitm_streaming import mitm_search_one_A_streaming\n"
        f"t0=time.time()\n"
        f"hits,n1c,n2c = mitm_search_one_A_streaming(5,{s},{A},4,5,k={k})\n"
        f"dt=time.time()-t0\n"
        "print(json.dumps({'hits':hits,'n1c':n1c,'n2c':n2c,'dt':dt}))\n"
    )
    with open(f"_worker_s{s}_A{A}.py", "w") as f:
        f.write(worker_code)

    proc = subprocess.Popen([sys.executable, f"_worker_s{s}_A{A}.py"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    max_rss_kb = 0
    t_probe0 = time.time()
    while proc.poll() is None:
        try:
            with open(f"/proc/{proc.pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                        max_rss_kb = max(max_rss_kb, rss_kb)
                        break
        except FileNotFoundError:
            pass
        time.sleep(2)
    out, err = proc.communicate()
    wall = time.time() - t_probe0
    try:
        result = json.loads(out.strip().splitlines()[-1])
    except Exception as e:
        result = {"error": str(e), "stdout": out, "stderr": err}
    print(f"  -> wall={wall:.1f}s  max_RSS={max_rss_kb:,}kB ({max_rss_kb/1024/1024:.3f} GiB)  "
          f"result={result}", flush=True)
    runs.append({
        "s": s, "A": A, "k": k,
        "materialized_items": mn, "streamed_items": mx, "estimated_time_s": est_time,
        "wall_time_s": wall, "max_rss_kb": max_rss_kb,
        "result": result,
    })

with open("raise_budget_probe_results.json", "w") as f:
    json.dump({"new_budget": NEW_BUDGET, "unlocked": [(s, A) for s, A, *_ in to_run], "runs": runs},
               f, indent=2, default=str)

print("\n=== probe done, results written to raise_budget_probe_results.json ===", flush=True)
