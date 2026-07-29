import sys, time, resource
from mitm_streaming import mitm_search_one_A_streaming as new_search

q, s, A = 5, int(sys.argv[1]), int(sys.argv[2])
t0 = time.time()
hits, n1, n2 = new_search(q, s, A, 4, 5)
dt = time.time() - t0
peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"NEW  s={s} A={A}: n1={n1:,} n2={n2:,} total={n1+n2:,} hits={len(hits)} "
      f"time={dt:.2f}s peak_rss={peak_kb/1024:.1f} MB")
