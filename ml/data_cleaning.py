import re
from pathlib import Path

import pandas as pd


DATA_PATH = "dataset/train.csv"
REPORT_PATH = Path("results/data_validation_report.txt")
CLASS_NAMES = {
    0: "Non-Toxic",
    1: "Insults & Flaming",
    2: "Other Offensive Texts",
    3: "Hate & Harassment",
    4: "Threats",
    5: "Extremism",
}


def legacy_clean_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+|https\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#", "", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


df = pd.read_csv(DATA_PATH)
required_columns = {"message", "label"}
missing_columns = required_columns.difference(df.columns)
if missing_columns:
    raise ValueError(f"GameTox dataset is missing columns: {sorted(missing_columns)}")

labels = pd.to_numeric(df["label"], errors="coerce")
invalid_labels = labels.isna() | (labels % 1 != 0) | ~labels.isin(CLASS_NAMES)
empty_messages = df["message"].isna() | df["message"].astype("string").str.strip().eq("").fillna(True)
if invalid_labels.any() or empty_messages.any():
    raise ValueError(
        f"Invalid GameTox rows: {int(invalid_labels.sum())} labels, "
        f"{int(empty_messages.sum())} empty messages"
    )

exact_duplicate_rows = int(df.duplicated().sum())
duplicate_message_label_rows = int(df[["message", "label"]].duplicated().sum())

# Reproduce the old pipeline's filters so its record loss is auditable.
legacy = df[["message", "label"]].copy()
legacy["message"] = legacy["message"].astype(str).str.strip()
legacy["label"] = labels.astype(int)
legacy = legacy.drop_duplicates()
legacy["normalized_text"] = legacy["message"].map(legacy_clean_text)
legacy_empty = legacy["normalized_text"].eq("")
legacy_nonempty = legacy[~legacy_empty]
conflict_counts = legacy_nonempty.groupby("normalized_text")["label"].nunique()
conflict_texts = conflict_counts[conflict_counts > 1].index
conflict_rows = legacy_nonempty["normalized_text"].isin(conflict_texts)
without_conflicts = legacy_nonempty[~conflict_rows]
normalized_duplicate_rows = int(without_conflicts.duplicated("normalized_text").sum())
legacy_final_rows = int(without_conflicts["normalized_text"].nunique())

lines = [
    "GameTox data validation report",
    f"Source: {DATA_PATH}",
    f"Original rows: {len(df)}",
    f"Exact full-row duplicates: {exact_duplicate_rows}",
    f"Repeated message+label rows: {duplicate_message_label_rows}",
    f"Empty/null source messages: {int(empty_messages.sum())}",
    f"Invalid labels (must be integer 0..5): {int(invalid_labels.sum())}",
    "",
    "Class value -> number of records -> sample messages",
]

for label, class_name in CLASS_NAMES.items():
    samples = df.loc[labels.eq(label), "message"].head(5).tolist()
    lines.append(f"{label} ({class_name}) -> {int(labels.eq(label).sum())}")
    lines.append(f"  Samples: {samples!r}")

lines.extend([
    "",
    "Previous pipeline loss accounting (sequential):",
    f"Repeated message+label rows removed: {duplicate_message_label_rows}",
    f"Rows normalized to empty by the old ASCII-only cleaner: {int(legacy_empty.sum())}",
    f"Normalized conflict groups: {len(conflict_texts)}",
    f"Rows removed from normalized conflict groups: {int(conflict_rows.sum())}",
    f"Additional same-normalized-text rows removed: {normalized_duplicate_rows}",
    f"Previous pipeline final rows: {legacy_final_rows}",
    f"Previous pipeline total rows removed: {len(df) - legacy_final_rows}",
    "",
    "The current six-class pipeline retains every validated source row.",
])

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Validated source rows:", len(df))
print("Exact full-row duplicates:", exact_duplicate_rows)
print("Repeated message+label rows retained:", duplicate_message_label_rows)
print("Empty source messages:", int(empty_messages.sum()))
print("Invalid labels:", int(invalid_labels.sum()))
print("Validation report saved to:", REPORT_PATH)