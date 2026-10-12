import pandas as pd
import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


TRAIN_PATH = "ml/artifacts/train.csv"
TEST_PATH = "ml/artifacts/test.csv"
VECTORIZER_PATH = "ml/tfidf_vectorizer.pkl"
MODEL_PATH = "ml/logistic_regression_model.pkl"


# Load train and test datasets
train_df = pd.read_csv(TRAIN_PATH, keep_default_na=False)
test_df = pd.read_csv(TEST_PATH, keep_default_na=False)

X_train_text = train_df["cleaned_text"]
X_test_text = test_df["cleaned_text"]

y_train = train_df["label"]
y_test = test_df["label"]


# Load the TF-IDF vectorizer fitted on training data
vectorizer = joblib.load(VECTORIZER_PATH)

# Convert text into TF-IDF features
X_train_tfidf = vectorizer.transform(X_train_text)
X_test_tfidf = vectorizer.transform(X_test_text)


print("Training TF-IDF shape:", X_train_tfidf.shape)
print("Testing TF-IDF shape:", X_test_tfidf.shape)


# Create Logistic Regression model
model = LogisticRegression(
    max_iter=1000,
    random_state=42
)


# Train the model
print("\nTraining Logistic Regression...")
model.fit(X_train_tfidf, y_train)

print("Training completed.")


# Make predictions
y_pred = model.predict(X_test_tfidf)


# Evaluate the model
accuracy = accuracy_score(y_test, y_pred)

print("\nAccuracy:", round(accuracy, 4))

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))


# Save the trained model
joblib.dump(model, MODEL_PATH)

print("\nModel saved to:", MODEL_PATH)