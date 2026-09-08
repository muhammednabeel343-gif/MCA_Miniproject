import re
import pandas as pd


INPUT_PATH = "dataset/cleaned_cyberbullying.csv"
OUTPUT_PATH = "dataset/preprocessed_cyberbullying.csv"


def clean_text(text):
    """
    Clean a tweet for NLP processing.
    """

    # Convert to lowercase
    text = str(text).lower()

    # Remove URLs
    text = re.sub(r"http\S+|www\S+|https\S+", "", text)

    # Remove @mentions
    text = re.sub(r"@\w+", "", text)

    # Remove # symbol but keep hashtag text
    text = re.sub(r"#", "", text)

    # Remove punctuation and special characters
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# Load cleaned dataset
df = pd.read_csv(INPUT_PATH)

print("Rows before preprocessing:", len(df))

# Apply text cleaning
df["cleaned_text"] = df["tweet_text"].apply(clean_text)

# Remove rows where preprocessing produced empty text
before_empty_removal = len(df)

df = df[
    df["cleaned_text"].notna()
    & (df["cleaned_text"].str.strip() != "")
].copy()

empty_removed = before_empty_removal - len(df)

print("Empty/NaN texts removed:", empty_removed)

# Save preprocessed dataset
df.to_csv(OUTPUT_PATH, index=False)

print("Final rows:", len(df))
print("Preprocessed dataset saved to:", OUTPUT_PATH)

# Display examples
print("\nSample preprocessing results:")
print(df[["tweet_text", "cleaned_text"]].head(5).to_string(index=False))