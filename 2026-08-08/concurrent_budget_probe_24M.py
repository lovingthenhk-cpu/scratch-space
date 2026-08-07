"""
2026-08-08: real CONCURRENT 2-process memory verification for a further
MEM_ITEM_BUDGET 21,000,000 -> 24,000,000 raise, following the exact same
incremental-probe methodology as 2026-08-05/2026-08-07's
concurrent_budget_probe*.py (one step at a time, always with a real
2-process measurement before trusting extrapolation).

CONTEXT: today's run_production_streaming_v9.py already raised the actual
production MEM_ITEM_BUDGET to 21,000,000 for real (not just a probe) and
confirmed s=9 (->156), s=11 (->83), s=13 (->59), s=14 (->59), s=16 (->49)
all reach their new natural ceiling with 0 hits, real combined peak RSS
~4.26 GiB (see memory_monitor_log.csv). This probe checks whether ANOTHER
step, to 24,000,000, stays within a safe memory margin -- exploratory
groundwork for a *future* session's production run, not something this
session commits to a full sweep for.

METHOD: identical structure to 2026-08-07's probe -- recompute which of the
ten s in [9..18] (at THEIR ceiling as of TODAY's v9 run) would advance
further under NEW_BUDGET=24,000,000, then run the two candidates with the
LARGEST materialized-side item count concurrently, sampling real RSS.
"""
import json
import subprocess
import sys
import time
from math import comb

from mitm_streaming import choose_k_for_memory_budget

OLD_BUDGET = 21_000_000
NEW_BUDGET = 24_000_000
PER_A_TIME_LIMIT = 900.0
EMPIRICAL_RATE = 1_000_000

# ceilings as of TODAY's (2026-08-08) v9 production run.
CEILINGS_21M = {9: 156, 10: 99, 11: 83, 12: 72, 13: 59, 14: 59, 15: 51, 16: 49, 17: 47, 18: 44}
STUCK = {s: A + 1 for s, A in CEILINGS_21M.items()}


def est(s, A, budget):
    k = choose_k_for_memory_budget(s, A, budget)
    max1 = A - (s - k)
    max2 = A - k
    c1 = comb(max1, k) if max1 >= k else 0
    c2 = comb(max2, s - k) if max2 >= (s - k) else 0
    mn, mx = (c1, c2) if c1 <= c2 else (c2, c1)
    return k, mn, mx, mx / EMPIRICAL_RATE


print("=== recomputing which stuck (s,A) unlock at NEW_BUDGET ===", flush=True)
unlocked = []
for s, A in STUCK.items():
    k_old, mn_old, mx_old, t_old = est(s, A, OLD_BUDGET)
    k_new, mn_new, mx_new, t_new = est(s, A, NEW_BUDGET)
    ok = t_new <= PER_A_TIME_LIMIT
    print(f"s={s:2d} A={A:3d}  old(k={k_old}, mat={mn_old:.3e}, est={t_old:8.1f}s)  "
          f"new(k={k_new}, mat={mn_new:.3e}, est={t_new:7.1f}s)  unlocked={ok}", flush=True)
    if ok:
        unlocked.append((s, A, k_new, mn_new, mx_new, t_new))

unlocked.sort(key=lambda r: -r[3])
pair = unlocked[:2]
print(f"\n=== concurrent pair chosen (largest materialized side): "
      f"{[(s, A) for s, A, *_ in pair]} ===", flush=True)

if len(pair) < 2:
    print("Fewer than 2 candidates unlocked -- cannot run the concurrent pair test.", flush=True)
    with open("concurrent_budget_probe_24M_results.json", "w") as f:
        json.dump({"new_budget": NEW_BUDGET, "unlocked": [(s, A) for s, A, *_ in unlocked],
                   "pair_tested": None, "runs": []}, f, indent=2, default=str)
    sys.exit(0)

worker_paths = []
procs = []
for s, A, k, mn, mx, est_time in pair:
    worker_code = (
        "import json,time\n"
        "from mitm_streaming import mitm_search_one_A_streaming\n"
        f"t0=time.time()\n"
        f"hits,n1c,n2c = mitm_search_one_A_streaming(5,{s},{A},4,5,k={k})\n"
        f"dt=time.time()-t0\n"
        f"with open('_worker_out_s{s}_A{A}.json','w') as f:\n"
        "    json.dump({'hits':hits,'n1c':n1c,'n2c':n2c,'dt':dt}, f)\n"
    )
    path = f"_worker_s{s}_A{A}.py"
    with open(path, "w") as f:
        f.write(worker_code)
    worker_paths.append((s, A, path))

print(f"\n=== launching both workers CONCURRENTLY, sampling combined RSS every 2s ===", flush=True)
t0 = time.time()
for s, A, path in worker_paths:
    proc = subprocess.Popen([sys.executable, path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    procs.append((s, A, proc))

max_combined_rss_kb = 0
max_per_proc_rss_kb = {f"{s}_{A}": 0 for s, A, _ in procs}
samples = []

def read_rss(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except FileNotFoundError:
        return None
    return None

while any(proc.poll() is None for _, _, proc in procs):
    combined = 0
    row = {"t": time.time() - t0}
    for s, A, proc in procs:
        rss = read_rss(proc.pid)
        if rss is not None:
            combined += rss
            key = f"{s}_{A}"
            max_per_proc_rss_kb[key] = max(max_per_proc_rss_kb[key], rss)
            row[key] = rss
    if combined > max_combined_rss_kb:
        max_combined_rss_kb = combined
    row["combined_kb"] = combined
    samples.append(row)
    time.sleep(2)

results = []
for s, A, proc in procs:
    out, err = proc.communicate()
    try:
        with open(f"_worker_out_s{s}_A{A}.json") as f:
            result = json.load(f)
    except Exception as e:
        result = {"error": str(e), "stderr": err[-2000:]}
    results.append({"s": s, "A": A, "result": result, "max_rss_kb": max_per_proc_rss_kb[f"{s}_{A}"]})

wall = time.time() - t0
print(f"\n=== done. wall={wall:.1f}s  max_combined_RSS={max_combined_rss_kb:,}kB "
      f"({max_combined_rss_kb/1024/1024:.3f} GiB) ===", flush=True)
for r in results:
    print(f"  s={r['s']} A={r['A']}  max_own_RSS={r['max_rss_kb']:,}kB "
          f"({r['max_rss_kb']/1024/1024:.3f} GiB)  result={r['result']}", flush=True)

with open("concurrent_budget_probe_24M_results.json", "w") as f:
    json.dump({
        "new_budget": NEW_BUDGET,
        "unlocked_full_list": [(s, A) for s, A, *_ in unlocked],
        "pair_tested": [(s, A) for s, A, *_ in pair],
        "wall_time_s": wall,
        "max_combined_rss_kb": max_combined_rss_kb,
        "max_combined_rss_gib": max_combined_rss_kb / 1024 / 1024,
        "per_process_results": results,
        "n_samples": len(samples),
    }, f, indent=2, default=str)

with open("concurrent_budget_probe_24M_timeline.csv", "w") as f:
    keys = ["t", "combined_kb"] + [f"{s}_{A}" for s, A, _ in worker_paths]
    f.write(",".join(keys) + "\n")
    for row in samples:
        f.write(",".join(str(row.get(k, "")) for k in keys) + "\n")

print("\n=== results written to concurrent_budget_probe_24M_results.json / _timeline.csv ===", flush=True)
