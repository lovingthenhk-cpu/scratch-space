"""
2026-08-05: real CONCURRENT 2-process memory verification for raising
MEM_ITEM_BUDGET 15,000,000 -> 18,000,000 in the actual 2-core production
pattern (next-steps item #2 from 2026-08-04's PROGRESS.md: "`MEM_ITEM_
BUDGET`の本番2コア並列実行そのものでの引き上げ検証...2プロセス同時の実測
が次の課題").

CONTEXT: 2026-08-04's raise_budget_probe.py already showed budget=18,000,000
unlocks (16,48) in an ISOLATED single-process run (peak RSS ~2.04 GiB,
1 process only). That answered "is 18M safe for one process at a time" but
NOT "is 18M safe when BOTH cores are running their own 18M-budget job
simultaneously", which is what the real production script
(run_production_streaming_vN.py, half A / half B) actually does.

Today's run_production_streaming_v7.py (see log_v7_A.txt/log_v7_B.txt)
finished with ALL TEN s in [9..18] now stuck at their natural ceiling under
the CURRENT 15,000,000 budget (first time this has happened for all ten
simultaneously). This makes "is it safe to raise MEM_ITEM_BUDGET in
production" the single highest-leverage open question for next steps, so
this session spends its remaining budget answering it properly instead of
just repeating another isolated-process probe.

METHOD: recompute (same choose_k_for_memory_budget()/comb() formulas,
no new estimation logic) which of the ten now-stuck (s,A) pairs unlock at
NEW_BUDGET=18,000,000 (i.e. estimated time drops back under
PER_A_TIME_LIMIT=900s). Among the unlocked set, this probe deliberately
picks the TWO cases with the LARGEST materialized-side item count (i.e.
the two closest to actually saturating an 18,000,000-item budget) --
(14, 58) and (9, 145) -- and runs them in two separate subprocesses AT THE
SAME TIME (mirroring exactly how half A / half B run concurrently in
production), sampling BOTH processes' real RSS every 2s for the combined
peak. This is the worst-case-realistic pairing available from the actual
unlocked set today, not a hypothetical stress test.

Why not just trust 2x the isolated-process peak: RSS growth is not
perfectly linear/independent between concurrent Python processes (shared
libc/interpreter pages, allocator behavior under system memory pressure,
etc.) -- 2026-08-03's PROGRESS.md already found the REAL concurrent 15M
peak (~3.66 GiB) was well under a naive 2x single-process estimate, so a
naive 2x extrapolation from yesterday's ~2.04 GiB isolated (16,48) run
would UNDERSTATE real risk if concurrency behaves differently at 18M, and
an actual measurement is cheap (a few minutes) relative to the risk of
raising a budget used for hours of future production runs on bad data.
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

# all ten s in [9..18], each at the first A its OWN natural ceiling under
# 15,000,000 blocked this session (run_production_streaming_v7 for 9/10/12,
# run_production_streaming_v6 for the rest) -- i.e. A_max_reached + 1.
STUCK = {9: 145, 10: 100, 11: 79, 12: 73, 13: 59, 14: 58, 15: 52, 16: 48, 17: 48, 18: 45}


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

# pick the two with the LARGEST materialized-side item count (closest to
# actually saturating an 18,000,000-item budget) for the worst-case-
# realistic concurrent pairing.
unlocked.sort(key=lambda r: -r[3])
pair = unlocked[:2]
print(f"\n=== concurrent pair chosen (largest materialized side): "
      f"{[(s, A) for s, A, *_ in pair]} ===", flush=True)

if len(pair) < 2:
    print("Fewer than 2 candidates unlocked -- cannot run the concurrent pair test.", flush=True)
    with open("concurrent_budget_probe_results.json", "w") as f:
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

with open("concurrent_budget_probe_results.json", "w") as f:
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

# keep only every 5th sample in a companion CSV for a lighter-weight timeline
with open("concurrent_budget_probe_timeline.csv", "w") as f:
    keys = ["t", "combined_kb"] + [f"{s}_{A}" for s, A, _ in worker_paths]
    f.write(",".join(keys) + "\n")
    for row in samples:
        f.write(",".join(str(row.get(k, "")) for k in keys) + "\n")

print("\n=== results written to concurrent_budget_probe_results.json / _timeline.csv ===", flush=True)
