import json

with open("production_streaming_v6_results_A.json") as f:
    a = json.load(f)
with open("production_streaming_v6_results_B.json") as f:
    b = json.load(f)

merged = {}
merged.update(a["results"])
merged.update(b["results"])

grand_total_equiv = a["grand_total_equiv"] + b["grand_total_equiv"]
grand_hits = a["grand_hits"] + b["grand_hits"]

out = {
    "results": merged,
    "grand_total_equiv": grand_total_equiv,
    "grand_hits": grand_hits,
    "elapsed_wall_time_s_per_half": {"A": a["elapsed_total_s"], "B": b["elapsed_total_s"]},
    "note": (
        "A and B ran concurrently on separate cores; wall-clock for the whole "
        "run is max(A,B), not sum. This session (2026-08-04) is a direct "
        "continuation of 2026-08-03's s=9..18 catch-up, resuming from "
        "../2026-08-03/production_streaming_v5_results_merged.json instead of "
        "the older 2026-07-29 baseline. Same MEM_ITEM_BUDGET=15,000,000 "
        "(unchanged), PER_A_TIME_LIMIT=900s (unchanged), but "
        "PER_S_TIME_BUDGET doubled from 1200s to 2400s. Result: s=11, 13, 14, "
        "15, 16, 17, 18 all confirmed at their NATURAL ceiling under the "
        "current budget (no further A reachable without raising "
        "MEM_ITEM_BUDGET or PER_A_TIME_LIMIT); s=9, 10, 12 made substantial "
        "further progress but were still control-timed by PER_S_TIME_BUDGET, "
        "so headroom remains there for a future session."
    ),
}

with open("production_streaming_v6_results_merged.json", "w") as f:
    json.dump(out, f, indent=2, default=str)

print(json.dumps(out, indent=2, default=str)[:3000])
print("\ngrand_total_equiv:", grand_total_equiv)
print("grand_hits:", grand_hits)
