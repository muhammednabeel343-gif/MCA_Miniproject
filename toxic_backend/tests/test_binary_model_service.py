import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ml.train_binary import SPLIT_PATH, convert_labels, load_source
from toxic_backend.app.database import get_db
from toxic_backend.app.services import model_service


class FakeLogisticRegression:
    classes_ = np.array([0, 1])

    def predict_proba(self, _features):
        return np.array([[0.2, 0.8]])


class FakeLinearSVC:
    classes_ = np.array([0, 1])

    def __init__(self, prediction, margin):
        self.prediction = prediction
        self.margin = margin

    def predict(self, _features):
        return np.array([self.prediction])

    def decision_function(self, _features):
        return self.margin


@pytest.mark.parametrize(
    ("original", "expected"),
    [([0, 1, 2, 3, 4, 5], [0, 1, 1, 1, 1, 1])],
)
def test_original_labels_convert_without_mutating_input(original, expected):
    source = list(original)

    assert convert_labels(source).tolist() == expected
    assert source == original


def test_label_conversion_rejects_unknown_labels():
    with pytest.raises(ValueError, match="Unexpected original"):
        convert_labels([0, 6])


def test_grouped_split_traceability_includes_all_source_rows():
    source = load_source()
    split = pd.read_csv(SPLIT_PATH)
    empty_source_rows = set(
        source.loc[source["cleaned_text"].eq(""), "source_row"]
    )
    excluded_source_rows = set(
        split.loc[split["partition"].eq("excluded"), "source_row"]
    )

    assert len(split) == len(source)
    assert split["source_id"].is_unique
    assert empty_source_rows.issubset(excluded_source_rows)
    assert split["original_label"].tolist() == source["original_label"].tolist()


def test_binary_bundle_loads_and_matches_vectorizer():
    assets = model_service.load_model_bundle("binary")

    assert assets["bundle"]["task_type"] == "binary_toxicity"
    assert assets["class_names"] == {0: "Non-Toxic", 1: "Toxic"}
    assert assets["bundle"]["original_label_mapping"] == {
        "0": "Non-Toxic",
        "1": "Toxic",
        "2": "Toxic",
        "3": "Toxic",
        "4": "Toxic",
        "5": "Toxic",
    }
    assert set(assets["lr_model"].classes_) == {0, 1}
    assert set(assets["svm_model"].classes_) == {0, 1}
    assert assets["lr_model"].n_features_in_ == len(assets["vectorizer"].vocabulary_)
    assert assets["svm_model"].n_features_in_ == len(assets["vectorizer"].vocabulary_)


def test_invalid_model_mode_fails_clearly():
    with pytest.raises(ValueError, match="TOXIC_MODEL_MODE"):
        model_service.load_model_bundle("invalid")


@pytest.mark.parametrize(
    ("prediction", "margin", "label"),
    [(0, -0.75, "Non-Toxic"), (1, 1.25, "Toxic")],
)
def test_binary_svm_scalar_margin_and_status(prediction, margin, label):
    assets = {
        "bundle": {"selection": {"selected_model": "linear_svm"}},
        "class_names": {0: "Non-Toxic", 1: "Toxic"},
        "lr_model": FakeLogisticRegression(),
        "svm_model": FakeLinearSVC(prediction, margin),
    }

    result = model_service._predict_binary(np.array([[0.0]]), assets)

    assert result["prediction"] == label
    assert result["status"] == label
    assert result["svm_prediction"] == label
    assert result["svm_score"] == margin
    assert result["confidence_is_calibrated"] is False
    assert "not a probability" in result["svm_confidence_type"]


def test_six_class_bundle_remains_loadable():
    assets = model_service.load_model_bundle("six_class")

    assert assets["class_names"] == model_service.CLASS_NAMES
    assert set(assets["svm_model"].classes_) == set(model_service.CLASS_NAMES)


@pytest.mark.parametrize(
    ("selected_model", "expected_type"),
    [
        (
            "linear_svm",
            "uncalibrated absolute Linear SVM decision margin; not a probability",
        ),
        (
            "logistic_regression",
            "uncalibrated Logistic Regression score (%)",
        ),
        ("legacy model", "uncalibrated score"),
    ],
)
def test_admin_score_metadata_marks_scores_uncalibrated(
    selected_model, expected_type
):
    from toxic_backend.app.routes.admin import _model_score_metadata

    metadata = _model_score_metadata(selected_model)

    assert metadata["selected_model"] == selected_model
    assert metadata["confidence_is_calibrated"] is False
    assert metadata["confidence_type"] == expected_type


def test_binary_service_predicts_non_toxic_and_toxic_with_real_bundle():
    non_toxic = model_service.predict_message(
        "Nice teamwork in the last round, well played!",
        model_mode="binary",
    )
    toxic = model_service.predict_message(
        "Fuck you, you ruined the whole match.",
        model_mode="binary",
    )

    assert non_toxic["prediction"] == "Non-Toxic"
    assert non_toxic["status"] == "Non-Toxic"
    assert toxic["prediction"] == "Toxic"
    assert toxic["status"] == "Toxic"
    assert non_toxic["svm_score_type"] == "signed LinearSVC decision_function margin"


def test_binary_empty_short_and_repeated_messages():
    empty = model_service.predict_message("   ", model_mode="binary")
    short = model_service.predict_message("gg", model_mode="binary")
    first = model_service.predict_message("you are a fool", model_mode="binary")
    repeated = model_service.predict_message("you are a fool", model_mode="binary")

    assert empty["prediction"] == "Non-Toxic"
    assert empty["status"] == "Non-Toxic"
    assert empty["svm_prediction"] == "Not Evaluated"
    assert short["prediction"] in {"Non-Toxic", "Toxic"}
    assert first["prediction"] == repeated["prediction"]
    assert first["svm_score"] == repeated["svm_score"]


def test_predict_api_preserves_response_fields_and_binary_status(monkeypatch):
    from toxic_backend.app.routes import predict as predict_route

    class FakeDatabase:
        def add(self, _record):
            pass

        def commit(self):
            pass

        def refresh(self, _record):
            pass

        def close(self):
            pass

    def fake_get_db():
        yield FakeDatabase()

    expected = {
        "prediction": "Toxic",
        "status": "Toxic",
        "confidence": 0.75,
        "confidence_is_calibrated": False,
        "confidence_type": "uncalibrated absolute Linear SVM decision margin; not a probability",
        "selected_model": "linear_svm",
        "logistic_regression_prediction": "Toxic",
        "logistic_regression_confidence": 80.0,
        "svm_prediction": "Toxic",
        "svm_confidence": 0.75,
        "svm_score": 0.75,
        "svm_score_type": "signed LinearSVC decision_function margin",
    }
    monkeypatch.setattr(predict_route, "predict_message", lambda _message: expected)
    app = FastAPI()
    app.include_router(predict_route.router)
    app.dependency_overrides[get_db] = fake_get_db

    with TestClient(app) as client:
        response = client.post("/predict", json={"message": "test message"})
        invalid_response = client.post("/predict", json={"message": 42})
        missing_response = client.post("/predict", json={})

    assert response.status_code == 200
    assert response.json() == {"message": "test message", **expected}
    assert invalid_response.status_code == 422
    assert missing_response.status_code == 422
