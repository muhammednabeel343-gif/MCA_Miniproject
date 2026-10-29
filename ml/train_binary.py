import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.svm import LinearSVC

if __package__:
    from .gametox_labels import CLASS_IDS, CLASS_NAMES
    from .preprocessing import clean_text
else:
    from gametox_labels import CLASS_IDS, CLASS_NAMES
    from preprocessing import clean_text


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "dataset" / "train.csv"
OUTPUT_DIR = ROOT / "ml" / "artifacts"
RESULTS_DIR = ROOT / "results"
BUNDLE_PATH = ROOT / "ml" / "gametox_binary_model_bundle.pkl"
VECTORIZER_PATH = ROOT / "ml" / "gametox_binary_tfidf_vectorizer.pkl"
LR_MODEL_PATH = ROOT / "ml" / "gametox_binary_logistic_regression.pkl"
SVM_MODEL_PATH = ROOT / "ml" / "gametox_binary_linear_svm.pkl"
SPLIT_PATH = OUTPUT_DIR / "gametox_binary_grouped_split.csv"
EVALUATION_PATH = RESULTS_DIR / "gametox_binary_evaluation.json"
REPORT_PATH = RESULTS_DIR / "gametox_binary_classification_report.txt"
CONFUSION_PATH = RESULTS_DIR / "gametox_binary_confusion_matrix.csv"

RANDOM_STATE = 42
HOLDOUT_FOLDS = 5
HOLDOUT_FOLD = 0
CV_FOLDS = 3
CLASS_NAMES_BINARY = {0: "Non-Toxic", 1: "Toxic"}
CLASS_IDS_BINARY = [0, 1]


def convert_labels(original_labels):
    labels = pd.to_numeric(pd.Series(original_labels), errors="raise")
    if labels.isna().any() or (labels % 1 != 0).any():
        raise ValueError("Original GameTox labels must be non-null integers")
    labels = labels.astype(int)
    invalid = sorted(set(labels) - set(CLASS_IDS))
    if invalid:
        raise ValueError(f"Unexpected original GameTox labels: {invalid}")
    return labels.map(lambda label: 0 if label == 0 else 1).to_numpy(dtype=int)


def load_source():
    source = pd.read_csv(SOURCE_PATH)
    required = {"message", "label"}
    missing = required.difference(source.columns)
    if missing:
        raise ValueError(f"GameTox dataset is missing columns: {sorted(missing)}")

    source = source.copy()
    source["source_row"] = np.arange(len(source), dtype=int)
    if "index" in source.columns:
        source["source_id"] = source["index"]
    else:
        source["source_id"] = source["source_row"]
    if source["source_id"].duplicated().any():
        raise ValueError("GameTox source IDs must be unique for traceability")
    source["message"] = source["message"].fillna("").astype(str)
    numeric_labels = pd.to_numeric(source["label"], errors="raise")
    if numeric_labels.isna().any() or (numeric_labels % 1 != 0).any():
        raise ValueError("GameTox labels must be non-null integers")
    source["original_label"] = numeric_labels.astype(int)
    invalid = sorted(set(source["original_label"]) - set(CLASS_IDS))
    if invalid:
        raise ValueError(f"Unexpected GameTox labels: {invalid}")
    source["cleaned_text"] = source["message"].map(clean_text)
    source["binary_label"] = convert_labels(source["original_label"])
    return source


def make_vectorizer():
    return TfidfVectorizer(max_features=10_000, ngram_range=(1, 2))


def candidate_specs():
    return [
        {
            "key": f"{model_name}_C{c_value:g}_{weight_key}",
            "model_type": model_name,
            "C": c_value,
            "class_weight": class_weight,
            "class_weight_key": weight_key,
        }
        for model_name in ("logistic_regression", "linear_svm")
        for c_value in (0.5, 1.0)
        for class_weight, weight_key in ((None, "unweighted"), ("balanced", "balanced"))
    ]


def make_model(spec):
    if spec["model_type"] == "logistic_regression":
        return LogisticRegression(
            C=spec["C"],
            class_weight=spec["class_weight"],
            max_iter=1000,
            random_state=RANDOM_STATE,
        )
    return LinearSVC(
        C=spec["C"],
        class_weight=spec["class_weight"],
        random_state=RANDOM_STATE,
    )


def metric_summary(actual, predicted):
    precision, recall, f1, support = precision_recall_fscore_support(
        actual,
        predicted,
        labels=CLASS_IDS_BINARY,
        zero_division=0,
    )
    matrix = confusion_matrix(actual, predicted, labels=CLASS_IDS_BINARY)
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "per_class": {
            str(label): {
                "name": CLASS_NAMES_BINARY[label],
                "precision": float(precision[label]),
                "recall": float(recall[label]),
                "f1": float(f1[label]),
                "support": int(support[label]),
            }
            for label in CLASS_IDS_BINARY
        },
        "toxic_precision": float(precision[1]),
        "toxic_recall": float(recall[1]),
        "toxic_f1": float(f1[1]),
        "macro_f1": float(f1_score(
            actual,
            predicted,
            labels=CLASS_IDS_BINARY,
            average="macro",
            zero_division=0,
        )),
        "confusion_matrix": {
            "class_names": [CLASS_NAMES_BINARY[label] for label in CLASS_IDS_BINARY],
            "rows_actual_columns_predicted": matrix.tolist(),
        },
    }


def grouped_oof_metrics(training, spec):
    labels = training["binary_label"].to_numpy()
    groups = training["cleaned_text"].to_numpy()
    splitter = StratifiedGroupKFold(
        n_splits=CV_FOLDS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    predictions = np.full(len(training), -1, dtype=int)
    fold_results = []

    for fold_number, (fit_indices, validation_indices) in enumerate(
        splitter.split(training["cleaned_text"], labels, groups),
        start=1,
    ):
        fit = training.iloc[fit_indices]
        validation = training.iloc[validation_indices]
        if set(fit["binary_label"]) != set(CLASS_IDS_BINARY):
            raise ValueError(
                f"{spec['key']} CV fold {fold_number} is missing a training class"
            )
        if set(fit["cleaned_text"]) & set(validation["cleaned_text"]):
            raise RuntimeError("Normalized-text group leaked across CV partitions")

        vectorizer = make_vectorizer()
        fit_features = vectorizer.fit_transform(fit["cleaned_text"])
        validation_features = vectorizer.transform(validation["cleaned_text"])
        model = make_model(spec)
        model.fit(fit_features, fit["binary_label"])
        fold_predictions = model.predict(validation_features)
        predictions[validation_indices] = fold_predictions
        fold_results.append({
            "fold": fold_number,
            "train_rows": int(len(fit)),
            "validation_rows": int(len(validation)),
            "normalized_group_overlap": 0,
            "metrics": metric_summary(
                validation["binary_label"].to_numpy(),
                fold_predictions,
            ),
        })

    if (predictions < 0).any():
        raise RuntimeError(f"{spec['key']} CV failed to predict every training row")
    return {
        "method": "3-fold StratifiedGroupKFold by normalized text",
        "random_state": RANDOM_STATE,
        "folds": fold_results,
        "out_of_fold_metrics": metric_summary(labels, predictions),
    }


def select_candidate(candidates):
    return max(
        candidates,
        key=lambda item: (
            item["cross_validation"]["out_of_fold_metrics"]["macro_f1"],
            item["cross_validation"]["out_of_fold_metrics"]["toxic_recall"],
        ),
    )


def fit_for_holdout(training, testing, spec):
    vectorizer = make_vectorizer()
    train_features = vectorizer.fit_transform(training["cleaned_text"])
    test_features = vectorizer.transform(testing["cleaned_text"])
    model = make_model(spec)
    model.fit(train_features, training["binary_label"])
    predictions = model.predict(test_features)
    return vectorizer, model, predictions


def main():
    source = load_source()
    nonempty = source.loc[source["cleaned_text"].ne("")].reset_index(drop=True)
    labels = nonempty["binary_label"].to_numpy()
    groups = nonempty["cleaned_text"].to_numpy()
    splitter = StratifiedGroupKFold(
        n_splits=HOLDOUT_FOLDS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    split_indices = list(splitter.split(nonempty["cleaned_text"], labels, groups))
    train_indices, test_indices = split_indices[HOLDOUT_FOLD]
    training = nonempty.iloc[train_indices].reset_index(drop=True)
    testing = nonempty.iloc[test_indices].reset_index(drop=True)
    shared_groups = set(training["cleaned_text"]) & set(testing["cleaned_text"])
    if shared_groups:
        raise RuntimeError("Normalized-text group leaked across holdout partitions")
    if set(training["binary_label"]) != set(CLASS_IDS_BINARY):
        raise ValueError("Grouped training partition is missing a binary class")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    split_rows = source[
        ["source_id", "source_row", "original_label", "binary_label"]
    ].copy()
    split_rows["partition"] = "excluded"
    train_source_rows = set(training["source_row"])
    test_source_rows = set(testing["source_row"])
    split_rows.loc[split_rows["source_row"].isin(train_source_rows), "partition"] = "train"
    split_rows.loc[split_rows["source_row"].isin(test_source_rows), "partition"] = "holdout"
    split_rows.to_csv(SPLIT_PATH, index=False)

    candidates = []
    for spec in candidate_specs():
        candidates.append({
            **spec,
            "cross_validation": grouped_oof_metrics(training, spec),
        })
    selected_by_model = {
        model_type: select_candidate(
            [candidate for candidate in candidates if candidate["model_type"] == model_type]
        )
        for model_type in ("logistic_regression", "linear_svm")
    }
    selected_final = max(
        selected_by_model.values(),
        key=lambda item: (
            item["cross_validation"]["out_of_fold_metrics"]["macro_f1"],
            item["cross_validation"]["out_of_fold_metrics"]["toxic_recall"],
        ),
    )

    majority_label = int(training["binary_label"].value_counts().idxmax())
    baseline_prediction = np.full(len(testing), majority_label, dtype=int)
    majority_baseline = metric_summary(
        testing["binary_label"].to_numpy(),
        baseline_prediction,
    )
    majority_baseline["training_majority_class"] = CLASS_NAMES_BINARY[majority_label]

    holdout_models = {}
    confusion_csv = {}
    report_sections = []
    for model_type, selected in selected_by_model.items():
        vectorizer, model, predictions = fit_for_holdout(training, testing, selected)
        metrics = metric_summary(testing["binary_label"].to_numpy(), predictions)
        holdout_models[model_type] = {
            "selected_hyperparameters": {
                "C": selected["C"],
                "class_weight": selected["class_weight"],
            },
            "cross_validation": selected["cross_validation"],
            "holdout": metrics,
        }
        matrix = metrics["confusion_matrix"]["rows_actual_columns_predicted"]
        for row_index, actual_name in enumerate(CLASS_NAMES_BINARY.values()):
            confusion_csv.setdefault(actual_name, {"actual": actual_name})
            confusion_csv[actual_name][f"{model_type}_predicted_non_toxic"] = matrix[row_index][0]
            confusion_csv[actual_name][f"{model_type}_predicted_toxic"] = matrix[row_index][1]
        report_sections.append(
            f"{model_type.replace('_', ' ').title()} — grouped holdout\n"
            + classification_report(
                testing["binary_label"],
                predictions,
                labels=CLASS_IDS_BINARY,
                target_names=[CLASS_NAMES_BINARY[label] for label in CLASS_IDS_BINARY],
                digits=4,
                zero_division=0,
            )
        )

    pd.DataFrame(confusion_csv.values()).to_csv(CONFUSION_PATH, index=False)
    (REPORT_PATH).write_text(
        "Binary GameTox grouped holdout classification reports\n\n"
        + "\n".join(report_sections),
        encoding="utf-8",
    )

    final_vectorizer = make_vectorizer()
    final_features = final_vectorizer.fit_transform(nonempty["cleaned_text"])
    final_models = {}
    for model_type, selected in selected_by_model.items():
        model = make_model(selected)
        model.fit(final_features, nonempty["binary_label"])
        final_models[model_type] = model

    selected_model_type = selected_final["model_type"]
    bundle = {
        "format_version": 1,
        "task_type": "binary_toxicity",
        "class_names": CLASS_NAMES_BINARY,
        "original_label_mapping": {
            str(label): ("Non-Toxic" if label == 0 else "Toxic")
            for label in CLASS_IDS
        },
        "preprocessor": "ml/preprocessing.py:clean_text",
        "vectorizer_config": {"max_features": 10_000, "ngram_range": [1, 2]},
        "selection": {
            "metric": "training-only grouped cross-validation macro F1",
            "selected_model": selected_model_type,
            "selected_hyperparameters": {
                model_type: {
                    "C": selected["C"],
                    "class_weight": selected["class_weight"],
                }
                for model_type, selected in selected_by_model.items()
            },
            "cross_validation_metrics": {
                model_type: selected["cross_validation"]["out_of_fold_metrics"]
                for model_type, selected in selected_by_model.items()
            },
        },
        "evaluation": {
            "artifact": str(EVALUATION_PATH.relative_to(ROOT)),
            "holdout_partition": (
                "five-fold StratifiedGroupKFold, fold 0, random_state=42"
            ),
        },
        "final_fit": {
            "partition": "all nonempty normalized source rows",
            "rows": int(len(nonempty)),
            "empty_normalized_rows_excluded": int(source["cleaned_text"].eq("").sum()),
            "class_counts": {
                CLASS_NAMES_BINARY[label]: int(
                    (nonempty["binary_label"] == label).sum()
                )
                for label in CLASS_IDS_BINARY
            },
        },
        "vectorizer": final_vectorizer,
        "models": final_models,
    }
    joblib.dump(bundle, BUNDLE_PATH)
    joblib.dump(final_vectorizer, VECTORIZER_PATH)
    joblib.dump(final_models["logistic_regression"], LR_MODEL_PATH)
    joblib.dump(final_models["linear_svm"], SVM_MODEL_PATH)

    evaluation = {
        "experiment": "GameTox binary Toxic vs Non-Toxic",
        "source": str(SOURCE_PATH.relative_to(ROOT)),
        "source_rows": int(len(source)),
        "source_ids_preserved": True,
        "original_label_mapping": bundle["original_label_mapping"],
        "binary_class_counts": {
            CLASS_NAMES_BINARY[label]: int((nonempty["binary_label"] == label).sum())
            for label in CLASS_IDS_BINARY
        },
        "empty_normalized_rows_excluded": int(source["cleaned_text"].eq("").sum()),
        "split": {
            "method": "StratifiedGroupKFold; first of five folds is holdout",
            "random_state": RANDOM_STATE,
            "holdout_fold": HOLDOUT_FOLD,
            "train_rows": int(len(training)),
            "holdout_rows": int(len(testing)),
            "train_class_counts": {
                CLASS_NAMES_BINARY[label]: int((training["binary_label"] == label).sum())
                for label in CLASS_IDS_BINARY
            },
            "holdout_class_counts": {
                CLASS_NAMES_BINARY[label]: int((testing["binary_label"] == label).sum())
                for label in CLASS_IDS_BINARY
            },
            "normalized_group_overlap": int(len(shared_groups)),
            "traceability_file": str(SPLIT_PATH.relative_to(ROOT)),
        },
        "vectorizer": {
            "type": "TfidfVectorizer",
            "max_features": 10_000,
            "ngram_range": [1, 2],
        },
        "majority_class_baseline": majority_baseline,
        "candidate_cross_validation": {
            candidate["key"]: {
                "model_type": candidate["model_type"],
                "C": candidate["C"],
                "class_weight": candidate["class_weight"],
                **candidate["cross_validation"],
            }
            for candidate in candidates
        },
        "selected_models": holdout_models,
        "selected_final_model": selected_model_type,
        "deployment_fit": {
            "partition": "all nonempty rows after the holdout evaluation",
            "bundle": str(BUNDLE_PATH.relative_to(ROOT)),
            "vectorizer": str(VECTORIZER_PATH.relative_to(ROOT)),
            "logistic_regression": str(LR_MODEL_PATH.relative_to(ROOT)),
            "linear_svm": str(SVM_MODEL_PATH.relative_to(ROOT)),
        },
    }
    EVALUATION_PATH.write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "holdout_rows": len(testing),
        "baseline_accuracy": majority_baseline["accuracy"],
        "selected_final_model": selected_model_type,
        "models": {
            model_type: {
                "hyperparameters": result["selected_hyperparameters"],
                "cv": result["cross_validation"]["out_of_fold_metrics"],
                "holdout": result["holdout"],
            }
            for model_type, result in holdout_models.items()
        },
        "artifacts": evaluation["deployment_fit"],
    }, indent=2))


if __name__ == "__main__":
    main()
