from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gametox_labels import CLASS_IDS, CLASS_NAMES


DATA_PATH = "dataset/train.csv"
OUTPUT_PATH = Path("results/class_percentage_distribution.png")

df = pd.read_csv(DATA_PATH)
labels = pd.to_numeric(df["label"], errors="raise").astype(int)
counts = labels.value_counts().reindex(CLASS_IDS, fill_value=0)
percentages = counts / len(df) * 100

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.bar(
    range(len(CLASS_IDS)),
    percentages,
    color=["#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b", "#b279a2"],
)
ax.set_xticks(
    range(len(CLASS_IDS)),
    [f"{label}\n{CLASS_NAMES[label]}" for label in CLASS_IDS],
)
ax.set_ylabel("Records (%)")
ax.set_title("GameTox Class Percentage Distribution")
ax.set_ylim(0, max(percentages) * 1.15)
ax.grid(axis="y", alpha=0.25)
ax.bar_label(bars, labels=[f"{value:.2f}%" for value in percentages], padding=3)
fig.tight_layout()
fig.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight")
plt.close(fig)

print("Rows:", len(df))
print("Class distribution:")
for label in CLASS_IDS:
    print(f"{label} ({CLASS_NAMES[label]}): {counts[label]} ({percentages[label]:.2f}%)")
print("Class distribution plot saved to:", OUTPUT_PATH)