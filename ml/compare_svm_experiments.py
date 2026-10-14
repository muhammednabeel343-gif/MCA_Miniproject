import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.svm import LinearSVC


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "ml" / "artifacts" / "train.csv"
TEST_PATH = ROOT / "ml" / "artifacts" / "test.csv"
VECTORIZER_PATH = ROOT / "ml" / "tfidf_vectorizer.pkl"
OUTPUT_DIR = ROOT / "ml" / "artifacts"
CLASS_NAMES = {
    0: "Non-Toxic",
    1: "Insults & Flaming",
    2: "Other Offensive Texts",
    3: "Hate & Harassment",
    4: "Threats",
    5: "Extremism",
}
CLASS_IDS = list(CLASS_NAMES)
MAX_EXAMPLES_PER_PAIR = 8


def build_model(labels, weight_setting, c_value):
    if weight_setting == "balanced":
        class_weight = "balanced"
    elif isinstance(weight_setting, float):
        class_weight = intermediate_class_weights(labels, weight_setting)
    else:
        class_weight = None
    return LinearSVC(
        class_weight=class_weight,
        C=c_value,
        random_state=42,
    )


def intermediate_class_weights(labels, exponent):
    counts = np.bincount(labels, minlength=len(CLASS_IDS))
    total = len(labels)
    raw_weights = (total / (len(CLASS_IDS) * counts)) ** exponent
    weighted_mean = np.sum(counts * raw_weights) / total
    return {
        label: float(raw_weights[label] / weighted_mean)
        for label in CLASS_IDS
    }


def summarize_predictions(actual, predicted):
    matrix = confusion_matrix(actual, predicted, labels=CLASS_IDS)
    precision, recall, f1, support = precision_recall_fscore_support(
        actual,
        predicted,
        labels=CLASS_IDS,
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_precision": float(
            precision_score(
                actual, predicted, labels=CLASS_IDS,
                average="macro", zero_division=0,
            )
        ),
        "macro_recall": float(
            recall_score(
                actual, predicted, labels=CLASS_IDS,
                average="macro", zero_division=0,
            )
        ),
        "macro_f1": float(
            f1_score(
                actual, predicted, labels=CLASS_IDS,
                average="macro", zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(
                actual, predicted, labels=CLASS_IDS,
                average="weighted", zero_division=0,
            )
        ),
        "per_class": {
            CLASS_NAMES[label]: {
                "precision": float(precision[label]),
                "recall": float(recall[label]),
                "f1": float(f1[label]),
                "support": int(support[label]),
            }
            for label in CLASS_IDS
        },
    }


def cross_validate_candidates(train, train_labels, train_texts):
    specs = {
        "baseline_unweighted_bigram": ((1, 2), None, 1.0, False),
        "balanced_bigram": ((1, 2), "balanced", 1.0, False),
        "mild_weight_bigram": ((1, 2), 0.25, 1.0, False),
        "sqrt_weight_bigram": ((1, 2), 0.5, 1.0, False),
        "balanced_C_0.5_bigram": ((1, 2), "balanced", 0.5, False),
        "baseline_unweighted_unigram": ((1, 1), None, 1.0, False),
        "deduplicated_train_unweighted": ((1, 2), None, 1.0, True),
    }
    splitter = StratifiedGroupKFold(
        n_splits=3,
        shuffle=True,
        random_state=42,
    )
    groups = train_texts.to_numpy()
    cross_validation_results = {}

    for name, (ngram_range, weight_setting, c_value, deduplicate) in specs.items():
        out_of_fold_predictions = np.full(len(train), -1, dtype=int)
        for fit_indices, validation_indices in splitter.split(
            train_texts,
            train_labels,
            groups=groups,
        ):
            fit_frame = train.iloc[fit_indices]
            if deduplicate:
                fit_frame = fit_frame.drop_duplicates(
                    subset=["cleaned_text", "label"],
                    keep="first",
                )
            fit_labels = fit_frame["label"].astype(int).to_numpy()
            fold_vectorizer = TfidfVectorizer(
                max_features=10_000,
                ngram_range=ngram_range,
            )
            fit_features = fold_vectorizer.fit_transform(
                fit_frame["cleaned_text"].astype(str)
            )
            validation_features = fold_vectorizer.transform(
                train_texts.iloc[validation_indices]
            )
            model = build_model(fit_labels, weight_setting, c_value)
            model.fit(fit_features, fit_labels)
            out_of_fold_predictions[validation_indices] = model.predict(
                validation_features
            )

        if (out_of_fold_predictions < 0).any():
            raise RuntimeError(f"Cross-validation missed rows for {name}")
        cross_validation_results[name] = summarize_predictions(
            train_labels,
            out_of_fold_predictions,
        )

    return cross_validation_results


def evaluate_model(name, model, test_features, test_labels, test_texts):
    predictions = model.predict(test_features)
    matrix = confusion_matrix(test_labels, predictions, labels=CLASS_IDS)
    precision, recall, f1, support = precision_recall_fscore_support(
        test_labels,
        predictions,
        labels=CLASS_IDS,
        zero_division=0,
    )

    class_metrics = {}
    for label in CLASS_IDS:
        false_positive = int(matrix[:, label].sum() - matrix[label, label])
        false_negative = int(matrix[label, :].sum() - matrix[label, label])
        negative_support = len(test_labels) - int(support[label])
        class_metrics[CLASS_NAMES[label]] = {
            "precision": float(precision[label]),
            "recall": float(recall[label]),
            "f1": float(f1[label]),
            "support": int(support[label]),
            "false_positive": false_positive,
            "false_negative": false_negative,
            "false_positive_rate": (
                float(false_positive / negative_support)
                if negative_support
                else 0.0
            ),
        }

    confusion_pairs = []
    example_rows = []
    for actual in CLASS_IDS:
        pair_counts = []
        for predicted in CLASS_IDS:
            count = int(matrix[actual, predicted])
            if actual != predicted and count:
                pair_counts.append((predicted, count))
                example_rows.extend(
                    {
                        "model": name,
                        "test_row": int(index),
                        "text": str(test_texts[index]),
                        "actual_id": actual,
                        "actual": CLASS_NAMES[actual],
                        "predicted_id": predicted,
                        "predicted": CLASS_NAMES[predicted],
                    }
                    for index, (actual_id, predicted_id) in enumerate(
                        zip(test_labels, predictions)
                    )
                    if int(actual_id) == actual and int(predicted_id) == predicted
                )

        confusion_pairs.extend(
            {
                "actual_id": actual,
                "actual": CLASS_NAMES[actual],
                "predicted_id": predicted,
                "predicted": CLASS_NAMES[predicted],
                "count": count,
            }
            for predicted, count in sorted(
                pair_counts, key=lambda pair: pair[1], reverse=True
            )
        )

    example_groups = {}
    for actual in CLASS_IDS:
        targets = [1] if actual == 0 else [0, 1]
        for predicted in targets:
            group = [
                row
                for row in example_rows
                if row["actual_id"] == actual
                and row["predicted_id"] == predicted
            ]
            if group:
                example_groups[f"{actual}->{predicted}"] = group[
                    :MAX_EXAMPLES_PER_PAIR
                ]

    return {
        "accuracy": float(accuracy_score(test_labels, predictions)),
        "macro_precision": float(
            precision_score(
                test_labels, predictions, labels=CLASS_IDS,
                average="macro", zero_division=0,
            )
        ),
        "macro_recall": float(
            recall_score(
                test_labels, predictions, labels=CLASS_IDS,
                average="macro", zero_division=0,
            )
        ),
        "macro_f1": float(
            f1_score(
                test_labels, predictions, labels=CLASS_IDS,
                average="macro", zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(
                test_labels, predictions, labels=CLASS_IDS,
                average="weighted", zero_division=0,
            )
        ),
        "non_toxic_false_positive_rate": class_metrics["Non-Toxic"][
            "false_negative"
        ] / class_metrics["Non-Toxic"]["support"],
        "per_class": class_metrics,
        "confusion_matrix": matrix.tolist(),
        "most_frequent_confusions": sorted(
            confusion_pairs, key=lambda pair: pair["count"], reverse=True
        )[:10],
        "examples_predicted_as_non_toxic_or_insults": example_groups,
        "misclassified_examples": example_rows,
    }


def main():
    train = pd.read_csv(TRAIN_PATH, keep_default_na=False)
    test = pd.read_csv(TEST_PATH, keep_default_na=False)
    vectorizer = joblib.load(VECTORIZER_PATH)
    train_labels = train["label"].astype(int).to_numpy()
    test_labels = test["label"].astype(int).to_numpy()
    train_texts = train["cleaned_text"].astype(str)
    test_texts = test["cleaned_text"].astype(str).tolist()
    cross_validation_results = cross_validate_candidates(
        train,
        train_labels,
        train_texts,
    )
    train_features = vectorizer.transform(train_texts)
    test_features = vectorizer.transform(test_texts)

    counts = np.bincount(train_labels, minlength=len(CLASS_IDS))
    candidates = [
        (
            "baseline_unweighted_bigram",
            LinearSVC(random_state=42),
            train_features,
            train_labels,
            test_features,
            {"class_weight": None, "C": 1.0, "ngram_range": [1, 2]},
        ),
        (
            "balanced_bigram",
            LinearSVC(class_weight="balanced", random_state=42),
            train_features,
            train_labels,
            test_features,
            {"class_weight": "balanced", "C": 1.0, "ngram_range": [1, 2]},
        ),
        (
            "mild_weight_bigram",
            LinearSVC(
                class_weight=intermediate_class_weights(train_labels, 0.25),
                random_state=42,
            ),
            train_features,
            train_labels,
            test_features,
            {
                "class_weight_exponent": 0.25,
                "class_weight": intermediate_class_weights(train_labels, 0.25),
                "C": 1.0,
                "ngram_range": [1, 2],
            },
        ),
        (
            "sqrt_weight_bigram",
            LinearSVC(
                class_weight=intermediate_class_weights(train_labels, 0.5),
                random_state=42,
            ),
            train_features,
            train_labels,
            test_features,
            {
                "class_weight_exponent": 0.5,
                "class_weight": intermediate_class_weights(train_labels, 0.5),
                "C": 1.0,
                "ngram_range": [1, 2],
            },
        ),
        (
            "balanced_C_0.5_bigram",
            LinearSVC(class_weight="balanced", C=0.5, random_state=42),
            train_features,
            train_labels,
            test_features,
            {"class_weight": "balanced", "C": 0.5, "ngram_range": [1, 2]},
        ),
    ]

    unigram_vectorizer = TfidfVectorizer(
        max_features=10_000,
        ngram_range=(1, 1),
    )
    unigram_train = unigram_vectorizer.fit_transform(train_texts)
    unigram_test = unigram_vectorizer.transform(test_texts)
    candidates.append(
        (
            "baseline_unweighted_unigram",
            LinearSVC(random_state=42),
            unigram_train,
            train_labels,
            unigram_test,
            {
                "class_weight": None,
                "C": 1.0,
                "ngram_range": [1, 1],
                "features": int(unigram_train.shape[1]),
            },
        )
    )

    deduplicated_train = train.drop_duplicates(
        subset=["cleaned_text", "label"],
        keep="first",
    )
    deduplicated_labels = deduplicated_train["label"].astype(int).to_numpy()
    deduplicated_features = vectorizer.transform(
        deduplicated_train["cleaned_text"].astype(str)
    )
    candidates.append(
        (
            "deduplicated_train_unweighted",
            LinearSVC(random_state=42),
            deduplicated_features,
            deduplicated_labels,
            test_features,
            {
                "class_weight": None,
                "C": 1.0,
                "training_rows_before": len(train),
                "training_rows_after": len(deduplicated_train),
                "deduplication_key": ["cleaned_text", "label"],
            },
        )
    )

    results = {}
    all_errors = []
    for name, model, features, labels, held_out_features, parameters in candidates:
        model.fit(features, labels)
        result = evaluate_model(
            name, model, held_out_features, test_labels, test_texts
        )
        result["parameters"] = parameters
        results[name] = result
        all_errors.extend(result.pop("misclassified_examples"))

    train_text_set = set(train_texts)
    leakage_summary = {
        "train_rows": len(train),
        "test_rows": len(test),
        "train_class_counts": {
            str(label): int(counts[label]) for label in CLASS_IDS
        },
        "test_class_counts": {
            str(label): int((test_labels == label).sum()) for label in CLASS_IDS
        },
        "test_rows_with_normalized_text_in_train": int(
            test["cleaned_text"].isin(train_text_set).sum()
        ),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUTPUT_DIR / "svm_experiment_results.json"
    errors_path = OUTPUT_DIR / "svm_misclassified_examples.csv"
    results_path.write_text(
        json.dumps(
            {
                "dataset": leakage_summary,
                "class_names": CLASS_NAMES,
                "train_only_grouped_cross_validation": {
                    "folds": 3,
                    "grouped_by": "cleaned_text",
                    "random_state": 42,
                    "experiments": cross_validation_results,
                },
                "experiments": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(all_errors).to_csv(errors_path, index=False)

    print("Dataset:", leakage_summary)
    print("Train-only grouped 3-fold cross-validation:")
    for name, result in cross_validation_results.items():
        print(
            name,
            {
                metric: round(result[metric], 5)
                for metric in (
                    "accuracy",
                    "macro_precision",
                    "macro_recall",
                    "macro_f1",
                    "weighted_f1",
                )
            },
        )
    print("Experiments:")
    for name, result in results.items():
        print(
            name,
            {
                metric: round(result[metric], 5)
                for metric in (
                    "accuracy",
                    "macro_precision",
                    "macro_recall",
                    "macro_f1",
                    "weighted_f1",
                    "non_toxic_false_positive_rate",
                )
            },
        )
        print("  Per-class:", result["per_class"])
        print("  Confusion matrix:", result["confusion_matrix"])
        print(
            "  Most frequent confusions:",
            result["most_frequent_confusions"][:5],
        )
        print(
            "  Example groups in JSON:",
            list(result["examples_predicted_as_non_toxic_or_insults"]),
        )
    print("Full metrics saved to:", results_path)
    print("Misclassified rows saved to:", errors_path)


if __name__ == "__main__":
    main()
