import json

with open("production_streaming_v7_results_A.json") as f:
    a = json.load(f)
with open("production_streaming_v7_results_B.json") as f:
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
        "run is max(A,B), not sum. This session (2026-08-05) is a direct "
        "continuation of 2026-08-04's s=9,10,12 catch-up, resuming from "
        "../2026-08-04/production_streaming_v6_results_merged.json. Same "
        "MEM_ITEM_BUDGET=15,000,000 (unchanged), PER_A_TIME_LIMIT=900s "
        "(unchanged). Unlike prior sessions, this run had NO control-timed "
        "PER_S_TIME_BUDGET cutoff -- a projection showed all three could "
        "reach their natural ceiling within a feasible session, so the run "
        "targeted (and reached) FULL natural completion for all three. "
        "Result: s=9 (A max 129->144), s=10 (A max 92->99), s=12 "
        "(A max 70->72) ALL now confirmed at their NATURAL ceiling under the "
        "current 15,000,000 budget, same as s=11,13,14,15,16,17,18 already "
        "were as of 2026-08-04. This means ALL TEN s values in [9,18] are "
        "now simultaneously at their natural ceiling under the current "
        "budget -- no further A is reachable for ANY of them without "
        "raising MEM_ITEM_BUDGET and/or PER_A_TIME_LIMIT."
    ),
}

with open("production_streaming_v7_results_merged.json", "w") as f:
    json.dump(out, f, indent=2, default=str)

print(json.dumps(out, indent=2, default=str)[:4000])
print("\ngrand_total_equiv:", grand_total_equiv)
print("grand_hits:", grand_hits)
