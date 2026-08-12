"""
2026-08-03: real concurrent-memory monitor, added to finally answer
candidate follow-up item (a) from 2026-08-02's PROGRESS.md "next steps":

    "2プロセス同時実行時の実際のピークメモリを`free -h`等で継続監視し、
    `MEM_ITEM_BUDGET`をさらに...引き上げられるか検証する(今回は理論上の
    最悪ケース見積もりで安全側に倒しただけで、実際のピーク同時メモリは
    継続監視していない)"

All memory reasoning so far (2026-07-30 Part K/M, 2026-08-02 Part T) has
been from theoretical worst case (materialized-side item count x measured
bytes/item), never from an actual live sample while two production
processes run concurrently. This script closes that gap: it samples
/proc/meminfo (system-wide MemAvailable) and the RSS of every process
matching a given substring (here, run_production_streaming_v5.py) every
INTERVAL seconds for the lifetime of the production run, and writes a CSV.
After the run, the max observed combined RSS and min observed MemAvailable
tell us the TRUE headroom, which either confirms MEM_ITEM_BUDGET=15,000,000
already has adequate margin, or -- if the true peak is well below the
theoretical worst case (likely, since not every s hits its per-process max
mat-side size at the same instant) -- gives real evidence to raise it in a
future session.

Usage: python3 monitor_memory.py <output_csv> <match_substring> [interval_s]
Runs until killed (SIGTERM/SIGINT), so launch with `nohup ... &` alongside
the production run and `kill` it once both halves finish.
"""
import subprocess
import sys
import time

OUT = sys.argv[1] if len(sys.argv) > 1 else "memory_monitor_log.csv"
MATCH = sys.argv[2] if len(sys.argv) > 2 else "run_production_streaming_v5.py"
INTERVAL = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0


def read_meminfo():
    d = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, v = line.split(':', 1)
            d[k.strip()] = int(v.strip().split()[0])  # kB
    return d


def get_matching_rss_kb(match):
    out = subprocess.run(['ps', '-eo', 'pid,rss,cmd', '--no-headers'],
                          capture_output=True, text=True).stdout
    total = 0
    per_proc = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, rss, cmd = parts
        if match in cmd:
            total += int(rss)
            per_proc.append(f"{pid}:{rss}kB")
    return total, per_proc


def main():
    t0 = time.time()
    max_total_rss = 0
    min_available = None
    with open(OUT, 'w') as f:
        f.write("t_s,mem_available_kb,mem_total_kb,matching_rss_kb,n_matching,detail\n")
        f.flush()
        while True:
            mi = read_meminfo()
            total_rss, procs = get_matching_rss_kb(MATCH)
            avail = mi.get('MemAvailable', -1)
            if total_rss > max_total_rss:
                max_total_rss = total_rss
            if avail >= 0 and (min_available is None or avail < min_available):
                min_available = avail
            f.write(f"{time.time()-t0:.1f},{avail},{mi.get('MemTotal', -1)},"
                     f"{total_rss},{len(procs)},\"{';'.join(procs)}\"\n")
            f.flush()
            time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
