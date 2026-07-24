import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

df = pd.read_csv("glide_records_with_lnfit.csv")
x = np.log(df["n"].values.astype(np.float64))
y = df["steps"].values.astype(np.float64)

A = np.vstack([x, np.ones_like(x)]).T
(c, b), *_ = np.linalg.lstsq(A, y, rcond=None)
y_pred = c * x + b
r2 = 1 - np.sum((y - y_pred) ** 2) / np.sum((y - np.mean(y)) ** 2)

fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")

ax.scatter(x, y, color="#2a78d6", s=22, zorder=3, label="glide record (n, steps)")
xs = np.linspace(x.min(), x.max(), 50)
ax.plot(xs, c * xs + b, color="#c0392b", linewidth=1.6, zorder=2,
        label=f"fit: steps = {c:.2f}·ln(n) {b:+.1f}  (R²={r2:.3f})")

ax.set_xlabel("ln(n)", fontsize=10, color="#0b0b0b")
ax.set_ylabel("total stopping time (steps)", fontsize=10, color="#0b0b0b")
ax.set_title("Collatz glide records: steps vs ln(n), n up to 7×10⁹",
             fontsize=11, color="#0b0b0b", loc="left")
ax.legend(loc="upper left", fontsize=9, frameon=False)

for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color("#c9c8bd")
ax.tick_params(colors="#52514e")
ax.grid(axis="y", color="#e5e4db", linewidth=0.7, zorder=0)

plt.tight_layout()
plt.savefig("glide_records_regression.png", facecolor=fig.get_facecolor())
print("saved glide_records_regression.png")
