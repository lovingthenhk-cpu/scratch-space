import time
from cycle_equation import exhaustive_search

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

s, Amax = 9, 45
t0 = time.time()
hits, cnt, dt = exhaustive_search(Q, TARGET_RESIDUE, TARGET_MOD, s, Amax, log_every=5)
print(f"s={s} A in [{s},{Amax}]: {cnt:,} compositions checked, {dt:.1f}s, hits={hits}", flush=True)
