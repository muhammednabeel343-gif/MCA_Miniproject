import re
import pandas as pd


INPUT_PATH = "dataset/train.csv"
OUTPUT_PATH = "dataset/gametox_preprocessed.csv"


def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+|https\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#", "", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    df = pd.read_csv(INPUT_PATH)
    df["cleaned_text"] = df["message"].map(clean_text)
    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)
    processed = df[["cleaned_text", "label"]]

    if len(processed) != len(df):
        raise RuntimeError("Preprocessing changed the GameTox row count")

    processed.to_csv(OUTPUT_PATH, index=False)

    print("Rows preserved:", len(processed))
    print(
        "Messages empty after normalization (retained):",
        int(processed["cleaned_text"].eq("").sum()),
    )
    print("Labels:")
    print(processed["label"].value_counts().sort_index())
    print("Preprocessed dataset saved to:", OUTPUT_PATH)


if __name__ == "__main__":
    main()