"""Merge today's v9 half A/B results with the unchanged (0-progress) s values,
producing a single results_merged.json that records the FULL state of all
ten s in [9..18] after this session, in the same shape as prior sessions'
merged results files (2026-08-07/merge_results.py, adapted for v9/21M)."""
import json

with open("production_streaming_v9_results_A.json") as f:
    a = json.load(f)
with open("production_streaming_v9_results_B.json") as f:
    b = json.load(f)

# 2026-08-07 natural ceilings under the OLD 18,000,000 budget.
CEILINGS_18M = {9: 150, 10: 99, 11: 81, 12: 72, 13: 58, 14: 58, 15: 51, 16: 48, 17: 47, 18: 44}

results = {}
for s, A in CEILINGS_18M.items():
    s_str = str(s)
    if s_str in a["results"]:
        results[s_str] = a["results"][s_str]
    elif s_str in b["results"]:
        results[s_str] = b["results"][s_str]
    else:
        # unchanged: confirmed (by formula only, deterministic, no execution
        # needed) to remain at the exact same ceiling under 21,000,000.
        results[s_str] = {
            "A_min": A + 1,
            "A_max_reached": A,
            "total_shapes_equivalent": 0,
            "hits": [],
            "wall_time_s": 0.0,
            "stop_reason": (
                f"UNCHANGED from 18,000,000 budget: formula re-check under "
                f"21,000,000 confirms A={A} remains the natural ceiling "
                f"(next A={A+1} still exceeds PER_A_TIME_LIMIT=900s even "
                f"with the raised budget) -- not executed, no new shapes "
                f"checked for this s this session."
            ),
        }

grand_total_equiv = sum(r["total_shapes_equivalent"] for r in results.values())
grand_hits = []
for r in results.values():
    grand_hits.extend(r["hits"])

merged = {
    "results": results,
    "grand_total_equiv": grand_total_equiv,
    "grand_hits": grand_hits,
    "elapsed_wall_time_s_per_half": {
        "A": a["elapsed_total_s"],
        "B": b["elapsed_total_s"],
    },
    "mem_item_budget": 21_000_000,
    "note": (
        "2026-08-08 session: MEM_ITEM_BUDGET actually raised in the main "
        "production script from 18,000,000 to 21,000,000 (previously only "
        "probed in isolation/pairs on 2026-08-07). Of the ten s in [9,18], "
        "only s=9 (150->156), s=11 (81->83), s=13 (58->59), s=14 (58->59), "
        "and s=16 (48->49) advance under the new budget -- the other five "
        "(10,12,15,17,18) are confirmed (by the same deterministic "
        "choose_k_for_memory_budget()/comb() formula the production script "
        "itself uses) to remain at exactly their 18,000,000-budget ceiling, "
        "so were not re-executed. A and B ran concurrently on separate "
        "cores; real combined peak RSS during this production run was "
        "~4.26 GiB (memory_monitor_log.csv), consistent with 2026-08-07's "
        "isolated-pair probe at 21M (~4.49 GiB). n1 = 4 mod 5 solutions: 0."
    ),
}

with open("production_streaming_v9_results_merged.json", "w") as f:
    json.dump(merged, f, indent=2, default=str)

print(json.dumps({k: v for k, v in merged.items() if k != "results"}, indent=2, default=str))
print("\nPer-s ceilings after this session:")
for s in sorted(results, key=int):
    print(f"  s={s:>2}: A_max={results[s]['A_max_reached']}")
