import os

import pandas as pd
from sklearn.model_selection import train_test_split


INPUT_PATH = "dataset/gametox_preprocessed.csv"

OUTPUT_DIR = "ml/artifacts"
TRAIN_PATH = os.path.join(OUTPUT_DIR, "train.csv")
TEST_PATH = os.path.join(OUTPUT_DIR, "test.csv")


df = pd.read_csv(INPUT_PATH, keep_default_na=False)

print("Total records:", len(df))

X = df["cleaned_text"]
y = df["label"]


# Split into 80% training and 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

train_df = pd.DataFrame({
    "cleaned_text": X_train,
    "label": y_train
})

test_df = pd.DataFrame({
    "cleaned_text": X_test,
    "label": y_test
})

os.makedirs(OUTPUT_DIR, exist_ok=True)
train_df.to_csv(TRAIN_PATH, index=False)
test_df.to_csv(TEST_PATH, index=False)

print("\nTraining records:", len(train_df))
print("Testing records:", len(test_df))

print("\nTraining class distribution:")
print(train_df["label"].value_counts().sort_index())

print("\nTesting class distribution:")
print(test_df["label"].value_counts().sort_index())

print("\nTraining dataset saved to:", TRAIN_PATH)
print("Testing dataset saved to:", TEST_PATH)