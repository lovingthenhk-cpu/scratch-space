import pandas as pd
import numpy as np

df = pd.read_csv("ratio_samples.csv")
theory = 1.0 / (1.0 + np.log2(3.0))
print(f"Theoretical odd-step fraction (heuristic): {theory:.6f}")
print(f"Total samples: {len(df)}")
print()

# Bucket by trajectory length (steps), since the heuristic is an
# asymptotic (long-trajectory) statement -- short trajectories are noisy.
bins = [0, 20, 50, 100, 200, 500, 700, 900, 1100, 1300, 1600, 2000, 10**9]
labels = ["<20", "20-50", "50-100", "100-200", "200-500", "500-700",
          "700-900", "900-1100", "1100-1300", "1300-1600", "1600-2000", ">=2000"]
df["bucket"] = pd.cut(df["steps"], bins=bins, labels=labels, right=False)

summary = df.groupby("bucket", observed=True).agg(
    n_samples=("odd_fraction", "size"),
    mean_odd_frac=("odd_fraction", "mean"),
    std_odd_frac=("odd_fraction", "std"),
    mean_steps=("steps", "mean"),
).reset_index()
summary["abs_dev_from_theory"] = (summary["mean_odd_frac"] - theory).abs()
pd.set_option("display.width", 120)
print(summary.to_string(index=False))
print()

# Also: weighted overall estimate using only the longest trajectories
long_df = df[df["steps"] >= 900]
print(f"Samples with steps>=900: {len(long_df)}")
if len(long_df) > 0:
    overall_odd = long_df["odd_steps"].sum()
    overall_even = long_df["even_steps"].sum()
    pooled_frac = overall_odd / (overall_odd + overall_even)
    print(f"Pooled odd-step fraction over long trajectories: {pooled_frac:.6f} (theory {theory:.6f}, diff {pooled_frac-theory:+.6f})")

summary.to_csv("ratio_summary.csv", index=False)
