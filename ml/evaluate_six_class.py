import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from gametox_labels import CLASS_IDS, CLASS_NAMES


TRAIN_PATH = Path("ml/artifacts/train.csv")
TEST_PATH = Path("ml/artifacts/test.csv")
VECTORIZER_PATH = Path("ml/tfidf_vectorizer.pkl")
LR_MODEL_PATH = Path("ml/logistic_regression_model.pkl")
SVM_MODEL_PATH = Path("ml/svm_model.pkl")
RESULTS_DIR = Path("results")
METRIC_NAMES = (
    "accuracy",
    "weighted_precision",
    "weighted_recall",
    "weighted_f1",
    "macro_precision",
    "macro_recall",
    "macro_f1",
)


def score_predictions(actual, predicted):
    report = classification_report(
        actual,
        predicted,
        labels=CLASS_IDS,
        target_names=[CLASS_NAMES[label] for label in CLASS_IDS],
        output_dict=True,
        zero_division=0,
    )
    metrics = {
        "accuracy": accuracy_score(actual, predicted),
        "weighted_precision": precision_score(
            actual, predicted, labels=CLASS_IDS, average="weighted", zero_division=0
        ),
        "weighted_recall": recall_score(
            actual, predicted, labels=CLASS_IDS, average="weighted", zero_division=0
        ),
        "weighted_f1": f1_score(
            actual, predicted, labels=CLASS_IDS, average="weighted", zero_division=0
        ),
        "macro_precision": precision_score(
            actual, predicted, labels=CLASS_IDS, average="macro", zero_division=0
        ),
        "macro_recall": recall_score(
            actual, predicted, labels=CLASS_IDS, average="macro", zero_division=0
        ),
        "macro_f1": f1_score(
            actual, predicted, labels=CLASS_IDS, average="macro", zero_division=0
        ),
        "per_class": {
            CLASS_NAMES[label]: {
                "precision": report[CLASS_NAMES[label]]["precision"],
                "recall": report[CLASS_NAMES[label]]["recall"],
                "f1": report[CLASS_NAMES[label]]["f1-score"],
                "support": int(report[CLASS_NAMES[label]]["support"]),
            }
            for label in CLASS_IDS
        },
    }
    return metrics


def save_model_report(model_key, model_title, actual, predicted, test_metrics):
    report = classification_report(
        actual,
        predicted,
        labels=CLASS_IDS,
        target_names=[CLASS_NAMES[label] for label in CLASS_IDS],
        digits=4,
        zero_division=0,
    )
    metric_summary = "\n".join(
        f"{name}: {test_metrics[name]:.6f}" for name in METRIC_NAMES
    )
    report_path = RESULTS_DIR / f"classification_report_{model_key}.txt"
    report_path.write_text(
        f"{model_title} six-class test evaluation\n\n"
        f"{metric_summary}\n\nPer-class report:\n{report}",
        encoding="utf-8",
    )


def save_confusion_matrix(model_key, model_title, actual, predicted):
    matrix = confusion_matrix(actual, predicted, labels=CLASS_IDS)
    display = ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=[CLASS_NAMES[label] for label in CLASS_IDS],
    )
    fig, ax = plt.subplots(figsize=(11, 9))
    display.plot(ax=ax, xticks_rotation=35, cmap="Blues", colorbar=True)
    ax.set_title(f"{model_title} Six-Class Confusion Matrix")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / f"{model_key}_confusion_matrix.png", dpi=200, bbox_inches="tight")
    fig.savefig(Path(f"{model_key}_confusion_matrix.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    return matrix.tolist()


def evaluate_model(model_key, model_title, model, train_features, train_labels, test_features, test_labels):
    train_predictions = model.predict(train_features)
    test_predictions = model.predict(test_features)
    train_metrics = score_predictions(train_labels, train_predictions)
    test_metrics = score_predictions(test_labels, test_predictions)
    save_model_report(model_key, model_title, test_labels, test_predictions, test_metrics)
    matrix = save_confusion_matrix(model_key, model_title, test_labels, test_predictions)
    return {
        "train": train_metrics,
        "test": test_metrics,
        "train_test_gaps": {
            name: train_metrics[name] - test_metrics[name]
            for name in ("accuracy", "weighted_f1", "macro_f1")
        },
        "test_confusion_matrix": matrix,
    }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    train_df = pd.read_csv(TRAIN_PATH, keep_default_na=False)
    test_df = pd.read_csv(TEST_PATH, keep_default_na=False)
    source_df = pd.read_csv("dataset/train.csv")
    vectorizer = joblib.load(VECTORIZER_PATH)
    lr_model = joblib.load(LR_MODEL_PATH)
    svm_model = joblib.load(SVM_MODEL_PATH)

    for name, model in (("Logistic Regression", lr_model), ("Linear SVM", svm_model)):
        if set(model.classes_) != set(CLASS_IDS):
            raise ValueError(f"{name} must be trained on all six GameTox labels")

    train_features = vectorizer.transform(train_df["cleaned_text"])
    test_features = vectorizer.transform(test_df["cleaned_text"])
    train_labels = train_df["label"].astype(int)
    test_labels = test_df["label"].astype(int)
    class_counts = source_df["label"].astype(int).value_counts()
    train_counts = train_labels.value_counts()
    test_counts = test_labels.value_counts()
    train_texts = set(train_df["cleaned_text"])
    test_overlap = test_df["cleaned_text"].isin(train_texts)
    nonempty_test = test_df["cleaned_text"].ne("")

    models = {
        "logistic_regression": evaluate_model(
            "lr", "Logistic Regression", lr_model,
            train_features, train_labels, test_features, test_labels,
        ),
        "linear_svm": evaluate_model(
            "svm", "Linear SVM", svm_model,
            train_features, train_labels, test_features, test_labels,
        ),
    }

    comparison_rows = []
    for model_name, result in models.items():
        row = {"model": model_name}
        for split in ("train", "test"):
            for metric in METRIC_NAMES:
                row[f"{split}_{metric}"] = result[split][metric]
        for metric, gap in result["train_test_gaps"].items():
            row[f"train_test_gap_{metric}"] = gap
        comparison_rows.append(row)
    pd.DataFrame(comparison_rows).to_csv(RESULTS_DIR / "model_comparison.csv", index=False)

    metrics_data = {
        "dataset": {
            "source": "dataset/train.csv",
            "total_rows": len(source_df),
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "normalized_text_overlap": {
                "test_rows_with_text_in_train": int(test_overlap.sum()),
                "test_row_percentage": float(test_overlap.mean() * 100),
                "distinct_shared_texts": len(set(test_df.loc[test_overlap, "cleaned_text"])),
                "nonempty_test_rows_with_text_in_train": int((test_overlap & nonempty_test).sum()),
            },
            "class_distribution": {
                str(label): {
                    "name": CLASS_NAMES[label],
                    "total": int(class_counts.get(label, 0)),
                    "train": int(train_counts.get(label, 0)),
                    "test": int(test_counts.get(label, 0)),
                    "percentage": float(class_counts.get(label, 0) / len(source_df) * 100),
                }
                for label in CLASS_IDS
            },
        },
        "models": models,
    }
    (RESULTS_DIR / "metrics.json").write_text(
        json.dumps(metrics_data, indent=2),
        encoding="utf-8",
    )

    for name, result in models.items():
        print(f"\n{name.replace('_', ' ').title()}")
        for split in ("train", "test"):
            print(split.title(), {metric: round(result[split][metric], 4) for metric in METRIC_NAMES})
        print("Train-test gaps:", result["train_test_gaps"])
        print("Test per-class metrics:", result["test"]["per_class"])
        print("Six-class test confusion matrix:")
        print(pd.DataFrame(
            result["test_confusion_matrix"],
            index=[CLASS_NAMES[label] for label in CLASS_IDS],
            columns=[CLASS_NAMES[label] for label in CLASS_IDS],
        ).to_string())

    print("\nSix-class evaluation artifacts saved under:", RESULTS_DIR)


if __name__ == "__main__":
    main()