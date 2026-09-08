import pandas as pd
from sklearn.model_selection import train_test_split


INPUT_PATH = "dataset/preprocessed_cyberbullying.csv"

TRAIN_PATH = "dataset/train.csv"
TEST_PATH = "dataset/test.csv"


# Load preprocessed dataset
df = pd.read_csv(INPUT_PATH)

print("Total records:", len(df))

# Separate features and labels
X = df["cleaned_text"]
y = df["cyberbullying_type"]


# Split into 80% training and 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# Create training and testing DataFrames
train_df = pd.DataFrame({
    "cleaned_text": X_train,
    "cyberbullying_type": y_train
})

test_df = pd.DataFrame({
    "cleaned_text": X_test,
    "cyberbullying_type": y_test
})


# Save datasets
train_df.to_csv(TRAIN_PATH, index=False)
test_df.to_csv(TEST_PATH, index=False)


# Display results
print("\nTraining records:", len(train_df))
print("Testing records:", len(test_df))

print("\nTraining class distribution:")
print(train_df["cyberbullying_type"].value_counts())

print("\nTesting class distribution:")
print(test_df["cyberbullying_type"].value_counts())

print("\nTraining dataset saved to:", TRAIN_PATH)
print("Testing dataset saved to:", TEST_PATH)