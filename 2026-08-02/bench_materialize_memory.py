"""
2026-08-02: Empirical measurement of "how many bytes per item does the
materialized (index) side of mitm_search_one_A_streaming actually cost",
run once per config in a FRESH subprocess (2026-07-30 lesson: ru_maxrss is
monotonic non-decreasing within a process, so comparing configs in the same
process gives contaminated numbers -- see PROGRESS.md "environment notes").

Goal: PROGRESS.md's 2026-08-01 homework item (b) asks to sanity check
`choose_k_for_memory_budget`'s fixed MEM_ITEM_BUDGET=2,000,000 by hand. A
quick scan (see analysis below / REPORT.md Part ?) shows that for s=19..26
at A=40, MEM_ITEM_BUDGET=2e6 forces a k that leaves the STREAMED side an
order of magnitude bigger than necessary -- the balanced-ish k (materialized
side ~2e7) would cut the streamed side (and hence wall time) by ~10-15x, if
2e7 materialized items actually fits comfortably in the 8GB box. This script
measures actual bytes/item so we can pick a MEM_ITEM_BUDGET that is
empirically safe, not just guessed.
"""
import subprocess
import sys

CHILD_CODE = '''
import resource, sys
from mitm_streaming import _enumerate_half_stream

q, s, start_i, parts, max_total, D = {q}, {s}, {start_i}, {parts}, {max_total}, {D}
index = {{}}
n = 0
for B, V in _enumerate_half_stream(q, s, start_i, parts, max_total):
    key = (B, V % D)
    prev = index.get(key)
    if prev is None:
        index[key] = V
    elif type(prev) is list:
        prev.append(V)
    else:
        index[key] = [prev, V]
    n += 1
peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"n_items={{n}} peak_rss_kb={{peak_kb}} bytes_per_item={{peak_kb*1024/n if n else 0:.1f}}")
'''

def measure(q, s, k, A, side="first"):
    D = (1 << A) - q ** s
    if side == "first":
        start_i, parts, max_total = 1, k, A - (s - k)
    else:
        start_i, parts, max_total = k + 1, s - k, A - k
    code = CHILD_CODE.format(q=q, s=s, start_i=start_i, parts=parts, max_total=max_total, D=D)
    out = subprocess.run([sys.executable, "-c", code], cwd=".", capture_output=True, text=True, timeout=600)
    print(f"  s={s} A={A} k={k} side={side} max_total={max_total} parts={parts} -> {out.stdout.strip()} {out.stderr.strip()[-300:]}")

if __name__ == "__main__":
    # s=20, A=40 varying k -- pick materialized-side item counts spanning
    # ~1e5 to ~3e7 to fit a bytes/item vs size curve (small dicts sometimes
    # have different overhead than huge ones due to hash table resizing).
    print("=== bytes/item for the materialized index, s=20 A=40, various k ===")
    for k in [7, 8, 9, 10]:
        measure(5, 20, k, 40, side="first")
