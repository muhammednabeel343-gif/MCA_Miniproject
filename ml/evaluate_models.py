import pandas as pd
import joblib

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)

import matplotlib.pyplot as plt


# =====================================================
# FILE PATHS
# =====================================================

TRAIN_PATH = "dataset/train.csv"
TEST_PATH = "dataset/test.csv"

VECTORIZER_PATH = "ml/tfidf_vectorizer.pkl"

LR_MODEL_PATH = "ml/logistic_regression_model.pkl"
SVM_MODEL_PATH = "ml/svm_model.pkl"


# =====================================================
# LOAD DATASETS
# =====================================================

train_df = pd.read_csv(TRAIN_PATH)
test_df = pd.read_csv(TEST_PATH)

X_train_text = train_df["cleaned_text"]
X_test_text = test_df["cleaned_text"]

y_train = train_df["cyberbullying_type"]
y_test = test_df["cyberbullying_type"]


# =====================================================
# LOAD TF-IDF VECTORIZER
# =====================================================

vectorizer = joblib.load(VECTORIZER_PATH)

X_train_tfidf = vectorizer.transform(X_train_text)
X_test_tfidf = vectorizer.transform(X_test_text)

print("Training TF-IDF shape:", X_train_tfidf.shape)
print("Testing TF-IDF shape:", X_test_tfidf.shape)


# =====================================================
# LOAD TRAINED MODELS
# =====================================================

lr_model = joblib.load(LR_MODEL_PATH)
svm_model = joblib.load(SVM_MODEL_PATH)


# =====================================================
# LOGISTIC REGRESSION
# =====================================================

print("\n" + "=" * 60)
print("LOGISTIC REGRESSION EVALUATION")
print("=" * 60)


# Predictions on training data
y_train_pred_lr = lr_model.predict(X_train_tfidf)

# Predictions on testing data
y_test_pred_lr = lr_model.predict(X_test_tfidf)


# -----------------------------------------------------
# Training Performance
# -----------------------------------------------------

lr_train_accuracy = accuracy_score(y_train, y_train_pred_lr)

lr_train_precision = precision_score(
    y_train,
    y_train_pred_lr,
    average="weighted"
)

lr_train_recall = recall_score(
    y_train,
    y_train_pred_lr,
    average="weighted"
)

lr_train_f1 = f1_score(
    y_train,
    y_train_pred_lr,
    average="weighted"
)


print("\n--- Training Performance ---")

print("Accuracy :", round(lr_train_accuracy, 4))
print("Precision:", round(lr_train_precision, 4))
print("Recall   :", round(lr_train_recall, 4))
print("F1 Score :", round(lr_train_f1, 4))


# -----------------------------------------------------
# Testing Performance
# -----------------------------------------------------

lr_test_accuracy = accuracy_score(y_test, y_test_pred_lr)

lr_test_precision = precision_score(
    y_test,
    y_test_pred_lr,
    average="weighted"
)

lr_test_recall = recall_score(
    y_test,
    y_test_pred_lr,
    average="weighted"
)

lr_test_f1 = f1_score(
    y_test,
    y_test_pred_lr,
    average="weighted"
)


print("\n--- Testing Performance ---")

print("Accuracy :", round(lr_test_accuracy, 4))
print("Precision:", round(lr_test_precision, 4))
print("Recall   :", round(lr_test_recall, 4))
print("F1 Score :", round(lr_test_f1, 4))


# -----------------------------------------------------
# Classification Report
# -----------------------------------------------------

print("\n--- Classification Report ---")

print(
    classification_report(
        y_test,
        y_test_pred_lr
    )
)


# -----------------------------------------------------
# Confusion Matrix
# -----------------------------------------------------

print("\n--- Confusion Matrix ---")

cm_lr = confusion_matrix(
    y_test,
    y_test_pred_lr
)

print(cm_lr)


# -----------------------------------------------------
# Logistic Regression Confusion Matrix Graph
# -----------------------------------------------------

fig_lr, ax_lr = plt.subplots(figsize=(9, 7))

disp_lr = ConfusionMatrixDisplay(
    confusion_matrix=cm_lr,
    display_labels=lr_model.classes_
)

disp_lr.plot(
    ax=ax_lr,
    xticks_rotation=45
)

ax_lr.set_title("Logistic Regression - Confusion Matrix")

plt.tight_layout()

plt.savefig(
    "lr_confusion_matrix.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

plt.close(fig_lr)


# =====================================================
# SVM
# =====================================================

print("\n" + "=" * 60)
print("SVM EVALUATION")
print("=" * 60)


# Predictions on training data
y_train_pred_svm = svm_model.predict(X_train_tfidf)

# Predictions on testing data
y_test_pred_svm = svm_model.predict(X_test_tfidf)


# -----------------------------------------------------
# Training Performance
# -----------------------------------------------------

svm_train_accuracy = accuracy_score(
    y_train,
    y_train_pred_svm
)

svm_train_precision = precision_score(
    y_train,
    y_train_pred_svm,
    average="weighted"
)

svm_train_recall = recall_score(
    y_train,
    y_train_pred_svm,
    average="weighted"
)

svm_train_f1 = f1_score(
    y_train,
    y_train_pred_svm,
    average="weighted"
)


print("\n--- Training Performance ---")

print("Accuracy :", round(svm_train_accuracy, 4))
print("Precision:", round(svm_train_precision, 4))
print("Recall   :", round(svm_train_recall, 4))
print("F1 Score :", round(svm_train_f1, 4))


# -----------------------------------------------------
# Testing Performance
# -----------------------------------------------------

svm_test_accuracy = accuracy_score(
    y_test,
    y_test_pred_svm
)

svm_test_precision = precision_score(
    y_test,
    y_test_pred_svm,
    average="weighted"
)

svm_test_recall = recall_score(
    y_test,
    y_test_pred_svm,
    average="weighted"
)

svm_test_f1 = f1_score(
    y_test,
    y_test_pred_svm,
    average="weighted"
)


print("\n--- Testing Performance ---")

print("Accuracy :", round(svm_test_accuracy, 4))
print("Precision:", round(svm_test_precision, 4))
print("Recall   :", round(svm_test_recall, 4))
print("F1 Score :", round(svm_test_f1, 4))


# -----------------------------------------------------
# Classification Report
# -----------------------------------------------------

print("\n--- Classification Report ---")

print(
    classification_report(
        y_test,
        y_test_pred_svm
    )
)


# -----------------------------------------------------
# Confusion Matrix
# -----------------------------------------------------

print("\n--- Confusion Matrix ---")

cm_svm = confusion_matrix(
    y_test,
    y_test_pred_svm
)

print(cm_svm)


# -----------------------------------------------------
# SVM Confusion Matrix Graph
# -----------------------------------------------------

fig_svm, ax_svm = plt.subplots(figsize=(9, 7))

disp_svm = ConfusionMatrixDisplay(
    confusion_matrix=cm_svm,
    display_labels=svm_model.classes_
)

disp_svm.plot(
    ax=ax_svm,
    xticks_rotation=45
)

ax_svm.set_title("SVM - Confusion Matrix")

plt.tight_layout()

plt.savefig(
    "svm_confusion_matrix.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

plt.close(fig_svm)


# =====================================================
# TRAINING VS TESTING COMPARISON
# =====================================================

print("\n" + "=" * 60)
print("TRAINING VS TESTING COMPARISON")
print("=" * 60)


print("\nLogistic Regression:")

print(
    "Accuracy Gap:",
    round(lr_train_accuracy - lr_test_accuracy, 4)
)

print(
    "F1 Score Gap:",
    round(lr_train_f1 - lr_test_f1, 4)
)


print("\nSVM:")

print(
    "Accuracy Gap:",
    round(svm_train_accuracy - svm_test_accuracy, 4)
)

print(
    "F1 Score Gap:",
    round(svm_train_f1 - svm_test_f1, 4)
)


# =====================================================
# FINAL MODEL COMPARISON
# =====================================================

print("\n" + "=" * 60)
print("MODEL COMPARISON")
print("=" * 60)


results = pd.DataFrame({
    "Model": [
        "Logistic Regression",
        "SVM"
    ],

    "Training Accuracy": [
        lr_train_accuracy,
        svm_train_accuracy
    ],

    "Testing Accuracy": [
        lr_test_accuracy,
        svm_test_accuracy
    ],

    "Testing Precision": [
        lr_test_precision,
        svm_test_precision
    ],

    "Testing Recall": [
        lr_test_recall,
        svm_test_recall
    ],

    "Testing F1": [
        lr_test_f1,
        svm_test_f1
    ]
})


print(
    results.round(4).to_string(index=False)
)


# =====================================================
# END
# =====================================================

print("\nEvaluation completed.")

print("\nConfusion matrix graphs saved as:")

print("lr_confusion_matrix.png")
print("svm_confusion_matrix.png")