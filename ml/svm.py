import pandas as pd
import joblib
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


TRAIN_PATH = "dataset/train.csv"
TEST_PATH = "dataset/test.csv"
VECTORIZER_PATH = "ml/tfidf_vectorizer.pkl"
MODEL_PATH = "ml/svm_model.pkl"


# Load train and test datasets
train_df = pd.read_csv(TRAIN_PATH)
test_df = pd.read_csv(TEST_PATH)

X_train_text = train_df["cleaned_text"]
X_test_text = test_df["cleaned_text"]

y_train = train_df["cyberbullying_type"]
y_test = test_df["cyberbullying_type"]


# Load the TF-IDF vectorizer
vectorizer = joblib.load(VECTORIZER_PATH)

# Convert text to TF-IDF features
X_train_tfidf = vectorizer.transform(X_train_text)
X_test_tfidf = vectorizer.transform(X_test_text)

print("Training TF-IDF shape:", X_train_tfidf.shape)
print("Testing TF-IDF shape:", X_test_tfidf.shape)


# Create Linear SVM model
base_svm = LinearSVC(
    random_state=42
)

model = CalibratedClassifierCV(
    estimator=base_svm,
    method="sigmoid",
    cv=5
)

# Train the model
print("\nTraining SVM...")
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