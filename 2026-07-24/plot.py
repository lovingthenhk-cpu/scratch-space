import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

df = pd.read_csv("ratio_summary.csv")
theory = 1.0 / (1.0 + np.log2(3.0))

# drop buckets with too few samples to be meaningful (std NaN or n<5)
df = df[df["n_samples"] >= 5].reset_index(drop=True)

x = np.arange(len(df))
y = df["mean_odd_frac"].values

fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")

ax.plot(x, y, color="#2a78d6", linewidth=2, marker="o", markersize=5, zorder=3)
ax.axhline(theory, color="#52514e", linewidth=1, linestyle="--", zorder=2)
ax.text(len(x) - 1, theory + 0.008, f"theory: 1/(1+log2 3) = {theory:.4f}",
        va="bottom", ha="right", fontsize=9, color="#52514e")

ax.set_xlim(-0.5, len(x) - 0.5)
ax.set_xticks(x)
ax.set_xticklabels(df["bucket"], rotation=30, ha="right", fontsize=9)
ax.set_xlabel("trajectory length (total steps)", fontsize=10, color="#0b0b0b")
ax.set_ylabel("mean odd-step fraction  o / (o+e)", fontsize=10, color="#0b0b0b")
ax.set_title("Collatz: odd-step fraction converges toward the equilibrium heuristic\nas trajectory length grows",
             fontsize=11, color="#0b0b0b", loc="left")

for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color("#c9c8bd")

ax.tick_params(colors="#52514e")
ax.grid(axis="y", color="#e5e4db", linewidth=0.7, zorder=0)

plt.tight_layout()
plt.savefig("odd_fraction_convergence.png", facecolor=fig.get_facecolor())
print("saved odd_fraction_convergence.png")
