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

from gametox_labels import CLASS_IDS, CLASS_NAMES
from preprocessing import clean_text


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "dataset" / "train.csv"
RESULTS_DIR = ROOT / "results"
CANDIDATE_DIR = ROOT / "ml" / "artifacts" / "grouped_candidates"
RANDOM_STATE = 42
HOLDOUT_FOLDS = 5
HOLDOUT_FOLD = 0
CV_FOLDS = 3
MAX_CONFLICT_EXAMPLES = 10
MAX_ROWS_PER_CONFLICT_EXAMPLE = 8


def load_source():
    source = pd.read_csv(SOURCE_PATH)
    required_columns = {"message", "label"}
    missing = required_columns.difference(source.columns)
    if missing:
        raise ValueError(f"GameTox dataset is missing columns: {sorted(missing)}")
    source = source.copy()
    source["source_row"] = np.arange(len(source))
    source["message"] = source["message"].fillna("").astype(str)
    numeric_labels = pd.to_numeric(source["label"], errors="raise")
    if numeric_labels.isna().any() or (numeric_labels % 1 != 0).any():
        raise ValueError("GameTox labels must be non-null integers")
    source["label"] = numeric_labels.astype(int)
    invalid_labels = sorted(set(source["label"]) - set(CLASS_IDS))
    if invalid_labels:
        raise ValueError(f"Unexpected GameTox labels: {invalid_labels}")
    source["cleaned_text"] = source["message"].map(clean_text)
    return source


def build_data_quality_report(source):
    group_stats = (
        source.groupby("cleaned_text", sort=True)
        .agg(
            row_count=("source_row", "size"),
            distinct_label_count=("label", "nunique"),
            labels=("label", lambda values: sorted(set(map(int, values)))),
        )
        .reset_index()
    )
    conflict_groups = group_stats[group_stats["distinct_label_count"] > 1]
    conflicts = []
    for row in conflict_groups.head(MAX_CONFLICT_EXAMPLES).itertuples(index=False):
        sample_rows = source.loc[
            source["cleaned_text"].eq(row.cleaned_text),
            ["source_row", "message", "label"],
        ].head(MAX_ROWS_PER_CONFLICT_EXAMPLE)
        conflicts.append(
            {
                "normalized_text": row.cleaned_text,
                "row_count": int(row.row_count),
                "labels": row.labels,
                "examples": [
                    {
                        "source_row": int(example.source_row),
                        "message": example.message,
                        "label": int(example.label),
                        "label_name": CLASS_NAMES[int(example.label)],
                    }
                    for example in sample_rows.itertuples(index=False)
                ],
            }
        )

    label_counts = source["label"].value_counts().sort_index()
    return {
        "source": str(SOURCE_PATH.relative_to(ROOT)),
        "source_rows": int(len(source)),
        "label_mapping": {str(key): value for key, value in CLASS_NAMES.items()},
        "source_class_counts": {
            str(label): int(label_counts.get(label, 0))
            for label in CLASS_IDS
        },
        "exact_full_row_duplicate_rows": int(
            source.drop(columns=["source_row", "cleaned_text"]).duplicated().sum()
        ),
        "repeated_message_label_rows": int(
            source[["message", "label"]].duplicated().sum()
        ),
        "normalized_text_groups": int(len(group_stats)),
        "normalized_duplicate_groups": int(
            group_stats["row_count"].gt(1).sum()
        ),
        "rows_in_normalized_duplicate_groups": int(
            group_stats.loc[group_stats["row_count"].gt(1), "row_count"].sum()
        ),
        "empty_normalized_rows": int(source["cleaned_text"].eq("").sum()),
        "conflicting_label_group_count": int(len(conflict_groups)),
        "rows_in_conflicting_label_groups": int(
            source["cleaned_text"].isin(
                set(conflict_groups["cleaned_text"])
            ).sum()
        ),
        "conflicting_groups_including_empty_text": int(
            conflict_groups["cleaned_text"].eq("").sum()
        ),
        "conflicting_group_examples": conflicts,
        "conflict_policy": (
            "Keep every original row and label unchanged; assign all rows sharing "
            "normalized text to one partition. Conflicting groups are neither "
            "relabeled nor removed. Empty normalized rows are excluded from both "
            "model fitting and evaluation, but counted and reported here."
        ),
        "empty_text_policy": (
            "Exclude rows whose project-preprocessed normalized text is empty "
            "from both the train/test split and all model fitting/evaluation. "
            "Do not alter the source dataset."
        ),
    }


def make_vectorizer():
    return TfidfVectorizer(max_features=10_000, ngram_range=(1, 2))


def make_model(candidate, labels):
    if candidate == "unweighted_bigram":
        return LinearSVC(random_state=RANDOM_STATE)
    if candidate == "balanced_C1_bigram":
        return LinearSVC(
            class_weight="balanced",
            C=1.0,
            random_state=RANDOM_STATE,
        )
    if candidate == "balanced_C0.5_bigram":
        return LinearSVC(
            class_weight="balanced",
            C=0.5,
            random_state=RANDOM_STATE,
        )
    raise ValueError(f"Unknown candidate: {candidate}")


def metric_summary(actual, predicted):
    matrix = confusion_matrix(actual, predicted, labels=CLASS_IDS)
    precision, recall, f1, support = precision_recall_fscore_support(
        actual,
        predicted,
        labels=CLASS_IDS,
        zero_division=0,
    )
    per_class = {
        str(label): {
            "name": CLASS_NAMES[label],
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(CLASS_IDS)
    }
    toxic_false_positives = int(matrix[0, 1:].sum())
    non_toxic_support = int(matrix[0].sum())
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_precision": float(
            precision_score(
                actual,
                predicted,
                labels=CLASS_IDS,
                average="macro",
                zero_division=0,
            )
        ),
        "macro_recall": float(
            recall_score(
                actual,
                predicted,
                labels=CLASS_IDS,
                average="macro",
                zero_division=0,
            )
        ),
        "macro_f1": float(
            f1_score(
                actual,
                predicted,
                labels=CLASS_IDS,
                average="macro",
                zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(
                actual,
                predicted,
                labels=CLASS_IDS,
                average="weighted",
                zero_division=0,
            )
        ),
        "non_toxic_to_toxic_false_positive_count": toxic_false_positives,
        "non_toxic_to_toxic_false_positive_rate": (
            toxic_false_positives / non_toxic_support
            if non_toxic_support
            else 0.0
        ),
        "per_class": per_class,
        "confusion_matrix": {
            "class_ids": CLASS_IDS,
            "rows_actual_columns_predicted": matrix.tolist(),
        },
    }


def grouped_cross_validation(training, candidate):
    labels = training["label"].to_numpy()
    groups = training["cleaned_text"].to_numpy()
    splitter = StratifiedGroupKFold(
        n_splits=CV_FOLDS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    predictions = np.full(len(training), -1, dtype=int)
    fold_reports = []

    for fold_number, (fit_indices, validation_indices) in enumerate(
        splitter.split(training["cleaned_text"], labels, groups),
        start=1,
    ):
        fit = training.iloc[fit_indices]
        validation = training.iloc[validation_indices]
        fit_labels = fit["label"].to_numpy()
        missing_classes = sorted(set(CLASS_IDS) - set(fit_labels))
        if missing_classes:
            raise ValueError(
                f"{candidate} CV fold {fold_number} training is missing classes "
                f"{missing_classes}"
            )
        overlap = set(fit["cleaned_text"]) & set(validation["cleaned_text"])
        if overlap:
            raise RuntimeError(
                f"Grouped CV leaked {len(overlap)} normalized-text groups"
            )

        fold_vectorizer = make_vectorizer()
        fit_features = fold_vectorizer.fit_transform(fit["cleaned_text"])
        validation_features = fold_vectorizer.transform(validation["cleaned_text"])
        model = make_model(candidate, fit_labels)
        model.fit(fit_features, fit_labels)
        fold_predictions = model.predict(validation_features)
        predictions[validation_indices] = fold_predictions
        fold_reports.append(
            {
                "fold": fold_number,
                "train_rows": int(len(fit)),
                "validation_rows": int(len(validation)),
                "validation_class_counts": {
                    str(label): int((validation["label"] == label).sum())
                    for label in CLASS_IDS
                },
                "normalized_group_overlap": 0,
                "metrics": metric_summary(
                    validation["label"].to_numpy(),
                    fold_predictions,
                ),
            }
        )

    if (predictions < 0).any():
        raise RuntimeError(f"{candidate} grouped CV did not predict every row")
    return {
        "method": "3-fold StratifiedGroupKFold grouped by normalized text",
        "random_state": RANDOM_STATE,
        "folds": fold_reports,
        "out_of_fold_metrics": metric_summary(labels, predictions),
    }


def main():
    source = load_source()
    quality_report = build_data_quality_report(source)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    quality_path = RESULTS_DIR / "gametox_grouped_data_quality.json"
    quality_path.write_text(
        json.dumps(quality_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    modeling_data = source.loc[source["cleaned_text"].ne("")].reset_index(drop=True)
    labels = modeling_data["label"].to_numpy()
    groups = modeling_data["cleaned_text"].to_numpy()
    splitter = StratifiedGroupKFold(
        n_splits=HOLDOUT_FOLDS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    train_indices, test_indices = list(
        splitter.split(modeling_data["cleaned_text"], labels, groups)
    )[HOLDOUT_FOLD]
    training = modeling_data.iloc[train_indices].reset_index(drop=True)
    testing = modeling_data.iloc[test_indices].reset_index(drop=True)
    shared_groups = set(training["cleaned_text"]) & set(testing["cleaned_text"])
    if shared_groups:
        raise RuntimeError(
            f"Grouped holdout contains {len(shared_groups)} shared text groups"
        )

    candidate_names = (
        "unweighted_bigram",
        "balanced_C1_bigram",
        "balanced_C0.5_bigram",
    )
    candidate_dir = CANDIDATE_DIR
    candidate_dir.mkdir(parents=True, exist_ok=True)
    training.to_csv(candidate_dir / "grouped_train.csv", index=False)
    testing.to_csv(candidate_dir / "grouped_test.csv", index=False)
    vectorizer = make_vectorizer()
    train_features = vectorizer.fit_transform(training["cleaned_text"])
    test_features = vectorizer.transform(testing["cleaned_text"])
    results = {}
    comparison_rows = []

    for candidate in candidate_names:
        model = make_model(candidate, training["label"].to_numpy())
        model.fit(train_features, training["label"].to_numpy())
        predictions = model.predict(test_features)
        test_metrics = metric_summary(testing["label"].to_numpy(), predictions)
        test_metrics["normalized_group_overlap_train_test"] = len(shared_groups)
        results[candidate] = {
            "test": test_metrics,
            "train_class_counts": {
                str(label): int((training["label"] == label).sum())
                for label in CLASS_IDS
            },
            "test_class_counts": {
                str(label): int((testing["label"] == label).sum())
                for label in CLASS_IDS
            },
            "test_normalized_group_count": int(
                testing["cleaned_text"].nunique()
            ),
            "train_normalized_group_count": int(
                training["cleaned_text"].nunique()
            ),
            "grouped_cross_validation_on_training_only": grouped_cross_validation(
                training,
                candidate,
            ),
        }
        model_path = candidate_dir / f"{candidate}.joblib"
        joblib.dump(model, model_path)
        comparison_rows.append(
            {
                "model": candidate,
                **{
                    key: value
                    for key, value in test_metrics.items()
                    if isinstance(value, (int, float))
                },
                **{
                    f"cv_{key}": value
                    for key, value in results[candidate][
                        "grouped_cross_validation_on_training_only"
                    ]["out_of_fold_metrics"].items()
                    if isinstance(value, (int, float))
                },
            }
        )

    vectorizer_path = candidate_dir / "grouped_tfidf_vectorizer.joblib"
    joblib.dump(vectorizer, vectorizer_path)
    manifest = {
        "experiment": "GameTox grouped evaluation",
        "source": str(SOURCE_PATH.relative_to(ROOT)),
        "preprocessor": "ml/preprocessing.py:clean_text",
        "split": {
            "method": "StratifiedGroupKFold; first of five folds is held-out test",
            "random_state": RANDOM_STATE,
            "holdout_fold": HOLDOUT_FOLD,
            "holdout_folds": HOLDOUT_FOLDS,
            "train_rows": int(len(training)),
            "test_rows": int(len(testing)),
            "train_class_counts": {
                str(label): int((training["label"] == label).sum())
                for label in CLASS_IDS
            },
            "test_class_counts": {
                str(label): int((testing["label"] == label).sum())
                for label in CLASS_IDS
            },
            "train_normalized_groups": int(training["cleaned_text"].nunique()),
            "test_normalized_groups": int(testing["cleaned_text"].nunique()),
            "shared_normalized_groups": int(len(shared_groups)),
            "empty_normalized_rows_excluded": int(
                source["cleaned_text"].eq("").sum()
            ),
            "conflicting_labels_policy": (
                "Original labels retained unchanged; same normalized text stays "
                "within one split."
            ),
        },
        "vectorizer": {
            "type": "TfidfVectorizer",
            "max_features": 10_000,
            "ngram_range": [1, 2],
            "vocabulary_size": int(len(vectorizer.vocabulary_)),
            "fit_partition": "grouped training partition only",
            "artifact": str(vectorizer_path.relative_to(ROOT)),
        },
        "candidate_artifact_directory": str(candidate_dir.relative_to(ROOT)),
        "data_quality_report": str(quality_path.relative_to(ROOT)),
        "models": results,
    }
    results_path = RESULTS_DIR / "gametox_grouped_evaluation.json"
    results_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    comparison_path = RESULTS_DIR / "gametox_grouped_model_comparison.csv"
    pd.DataFrame(comparison_rows).to_csv(comparison_path, index=False)

    print("Data quality report:", quality_path)
    print(
        "Conflicting groups:",
        quality_report["conflicting_label_group_count"],
        "conflicting rows:",
        quality_report["rows_in_conflicting_label_groups"],
        "empty normalized rows excluded:",
        quality_report["empty_normalized_rows"],
    )
    print(
        "Grouped split:",
        {
            "train_rows": len(training),
            "test_rows": len(testing),
            "train_class_counts": manifest["split"]["train_class_counts"],
            "test_class_counts": manifest["split"]["test_class_counts"],
            "shared_normalized_groups": len(shared_groups),
        },
    )
    for candidate, result in results.items():
        print(
            candidate,
            {
                key: round(result["test"][key], 5)
                for key in (
                    "accuracy",
                    "macro_precision",
                    "macro_recall",
                    "macro_f1",
                    "weighted_f1",
                    "non_toxic_to_toxic_false_positive_rate",
                )
            },
        )
        print("  Per-class:", result["test"]["per_class"])
        print("  Confusion:", result["test"]["confusion_matrix"])
        print(
            "  Training-only grouped CV OOF metrics:",
            {
                key: round(
                    result["grouped_cross_validation_on_training_only"][
                        "out_of_fold_metrics"
                    ][key],
                    5,
                )
                for key in (
                    "accuracy",
                    "macro_precision",
                    "macro_recall",
                    "macro_f1",
                    "weighted_f1",
                )
            },
        )
    print("Model comparison:", comparison_path)
    print("Detailed evaluation:", results_path)
    print("Candidate artifacts saved separately under:", candidate_dir)


if __name__ == "__main__":
    main()
