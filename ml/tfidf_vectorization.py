import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer


TRAIN_PATH = "dataset/train.csv"
TEST_PATH = "dataset/test.csv"

VECTORIZER_PATH = "ml/tfidf_vectorizer.pkl"


# Load train and test datasets
train_df = pd.read_csv(TRAIN_PATH)
test_df = pd.read_csv(TEST_PATH)

X_train_text = train_df["cleaned_text"]
X_test_text = test_df["cleaned_text"]


# Create TF-IDF vectorizer
vectorizer = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    min_df=2
)


# Fit ONLY on training data
X_train_tfidf = vectorizer.fit_transform(X_train_text)

# Transform test data using the already-fitted vectorizer
X_test_tfidf = vectorizer.transform(X_test_text)


# Display information
print("Training records:", X_train_tfidf.shape[0])
print("Testing records:", X_test_tfidf.shape[0])
print("Number of TF-IDF features:", X_train_tfidf.shape[1])

print("\nTraining TF-IDF matrix shape:", X_train_tfidf.shape)
print("Testing TF-IDF matrix shape:", X_test_tfidf.shape)


# Save the fitted vectorizer
joblib.dump(vectorizer, VECTORIZER_PATH)

print("\nTF-IDF vectorizer saved to:", VECTORIZER_PATH)