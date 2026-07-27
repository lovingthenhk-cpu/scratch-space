import time
from cycle_equation import exhaustive_search

Q = 5
TARGET_RESIDUE = 4
TARGET_MOD = 5

plan = [(1,5000),(2,10000),(3,600),(4,160),(5,100),(6,75),(7,60),(8,50)]

all_hits = []
grand_total_shapes = 0
t_start = time.time()
for s, Amax in plan:
    t0 = time.time()
    hits, cnt, dt = exhaustive_search(Q, TARGET_RESIDUE, TARGET_MOD, s, Amax)
    grand_total_shapes += cnt
    all_hits.extend(hits)
    print(f"s={s:2d} A in [{s},{Amax}]: {cnt:,} compositions checked, "
          f"{dt:.1f}s, hits so far this s: {hits}", flush=True)

print()
print(f"GRAND TOTAL: {grand_total_shapes:,} shapes checked "
      f"(s=1..8, exhaustive over stated A ranges) in {time.time()-t_start:.1f}s")
print(f"ALL HITS (n1 ≡ {TARGET_RESIDUE} mod {TARGET_MOD}): {all_hits}")
