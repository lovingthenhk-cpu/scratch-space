"""
2026-08-09: generic, reusable version of 2026-08-05/07/08's
concurrent_budget_probe_*.py concurrent-pair RSS measurement, parametrized
by (s, A, k) pairs on the command line so the SAME measurement code can be
reused for both today's reproducibility check (repeat 2026-08-08's
(18,45)+(13,60) pair) and the swap-candidate follow-up (substitute (16,50)
for one of them) -- see PROGRESS.md / saturation_analysis_24M.py.

Usage: python3 concurrent_probe_generic.py <tag> s1 A1 k1 s2 A2 k2
Writes concurrent_probe_<tag>_results.json and _timeline.csv.
"""
import json
import subprocess
import sys
import time

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

tag = sys.argv[1]
s1, A1, k1, s2, A2, k2 = (int(x) for x in sys.argv[2:8])
pair = [(s1, A1, k1), (s2, A2, k2)]

print(f"=== concurrent_probe tag={tag} pair={[(s,A) for s,A,_ in pair]} ===", flush=True)

worker_paths = []
for s, A, k in pair:
    worker_code = (
        "import json,time\n"
        "from mitm_streaming import mitm_search_one_A_streaming\n"
        f"t0=time.time()\n"
        f"hits,n1c,n2c = mitm_search_one_A_streaming({Q},{s},{A},{TARGET_RESIDUE},{TARGET_MOD},k={k})\n"
        f"dt=time.time()-t0\n"
        f"with open('_worker_out_{tag}_s{s}_A{A}.json','w') as f:\n"
        "    json.dump({'hits':hits,'n1c':n1c,'n2c':n2c,'dt':dt}, f)\n"
    )
    path = f"_worker_{tag}_s{s}_A{A}.py"
    with open(path, "w") as f:
        f.write(worker_code)
    worker_paths.append((s, A, path))

procs = []
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
        with open(f"_worker_out_{tag}_s{s}_A{A}.json") as f:
            result = json.load(f)
    except Exception as e:
        result = {"error": str(e), "stderr": err[-2000:]}
    results.append({"s": s, "A": A, "result": result, "max_rss_kb": max_per_proc_rss_kb[f"{s}_{A}"]})

wall = time.time() - t0
print(f"=== tag={tag} done. wall={wall:.1f}s  max_combined_RSS={max_combined_rss_kb:,}kB "
      f"({max_combined_rss_kb/1024/1024:.3f} GiB) ===", flush=True)
for r in results:
    print(f"  s={r['s']} A={r['A']}  max_own_RSS={r['max_rss_kb']:,}kB "
          f"({r['max_rss_kb']/1024/1024:.3f} GiB)  hits={r['result'].get('hits')}", flush=True)

with open(f"concurrent_probe_{tag}_results.json", "w") as f:
    json.dump({
        "tag": tag,
        "pair_tested": [(s, A) for s, A, _ in pair],
        "wall_time_s": wall,
        "max_combined_rss_kb": max_combined_rss_kb,
        "max_combined_rss_gib": max_combined_rss_kb / 1024 / 1024,
        "per_process_results": results,
        "n_samples": len(samples),
    }, f, indent=2, default=str)

with open(f"concurrent_probe_{tag}_timeline.csv", "w") as f:
    keys = ["t", "combined_kb"] + [f"{s}_{A}" for s, A, _ in worker_paths]
    f.write(",".join(keys) + "\n")
    for row in samples:
        f.write(",".join(str(row.get(k, "")) for k in keys) + "\n")

print(f"Written to concurrent_probe_{tag}_results.json / _timeline.csv", flush=True)
