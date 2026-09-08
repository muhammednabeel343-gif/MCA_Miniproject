import pandas as pd

# File paths
RAW_DATA_PATH = "dataset/cyberbullying_tweets.csv"
CLEANED_DATA_PATH = "dataset/cleaned_cyberbullying.csv"

# Load raw dataset
df = pd.read_csv(RAW_DATA_PATH)

print("Original rows:", len(df))

# Remove exact duplicate rows
df_clean = df.drop_duplicates()

print("Rows after exact duplicate removal:", len(df_clean))
print("Exact duplicates removed:", len(df) - len(df_clean))

# Find tweet texts that have multiple labels
label_counts = df_clean.groupby("tweet_text")["cyberbullying_type"].nunique()

conflicting_tweets = label_counts[label_counts > 1].index

print("Conflicting tweet texts:", len(conflicting_tweets))

# Remove all rows belonging to conflicting tweet texts
df_clean = df_clean[
    ~df_clean["tweet_text"].isin(conflicting_tweets)
].copy()

print(
    "Rows removed because of conflicting labels:",
    len(df.drop_duplicates()) - len(df_clean)
)

print("Final rows:", len(df_clean))

# Show final class distribution
print("\nFinal class distribution:")
print(df_clean["cyberbullying_type"].value_counts())

print("\nFinal class percentages:")
print(
    (df_clean["cyberbullying_type"].value_counts(normalize=True) * 100)
    .round(2)
)

# Save cleaned dataset
df_clean.to_csv(CLEANED_DATA_PATH, index=False)

print("\nCleaned dataset saved to:", CLEANED_DATA_PATH)