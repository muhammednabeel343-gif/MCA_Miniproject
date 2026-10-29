import os
import re
import joblib
import numpy as np


# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)

CLASS_NAMES = {
    0: "Non-Toxic",
    1: "Insults & Flaming",
    2: "Other Offensive Texts",
    3: "Hate & Harassment",
    4: "Threats",
    5: "Extremism",
}

BINARY_CLASS_NAMES = {0: "Non-Toxic", 1: "Toxic"}
MODEL_MODE = os.getenv("TOXIC_MODEL_MODE", "six_class").strip().lower()
_MODEL_ASSETS = {}


def load_model_bundle(model_mode=None):
    selected_mode = (model_mode or MODEL_MODE).strip().lower()
    if selected_mode not in {"six_class", "binary"}:
        raise ValueError("TOXIC_MODEL_MODE must be 'six_class' or 'binary'")
    bundle_name = (
        "gametox_binary_model_bundle.pkl"
        if selected_mode == "binary"
        else "gametox_model_bundle.pkl"
    )
    bundle_path = os.path.join(BASE_DIR, "ml", bundle_name)
    loaded_bundle = joblib.load(bundle_path)
    if loaded_bundle.get("format_version") != 1:
        raise ValueError(f"Unsupported GameTox {selected_mode} bundle format")

    expected_names = (
        BINARY_CLASS_NAMES if selected_mode == "binary" else CLASS_NAMES
    )
    if loaded_bundle.get("class_names") != expected_names:
        raise ValueError(
            f"GameTox {selected_mode} bundle has an incompatible label mapping"
        )
    if selected_mode == "binary" and loaded_bundle.get("task_type") != "binary_toxicity":
        raise ValueError("Binary GameTox bundle has an incompatible task type")
    if selected_mode == "binary":
        expected_original_mapping = {
            str(label): ("Non-Toxic" if label == 0 else "Toxic")
            for label in range(6)
        }
        if loaded_bundle.get("original_label_mapping") != expected_original_mapping:
            raise ValueError("Binary GameTox bundle has an incompatible source-label mapping")

    loaded_vectorizer = loaded_bundle["vectorizer"]
    config = loaded_bundle.get("vectorizer_config", {})
    max_features = config.get("max_features", loaded_vectorizer.max_features)
    ngram_range = tuple(config.get("ngram_range", loaded_vectorizer.ngram_range))
    if max_features != 10_000 or ngram_range != (1, 2):
        raise ValueError(
            f"GameTox {selected_mode} bundle has an incompatible TF-IDF configuration"
        )

    expected_classes = set(expected_names)
    loaded_models = loaded_bundle["models"]
    for model_key, display_name in (
        ("logistic_regression", "Logistic Regression"),
        ("linear_svm", "Linear SVM"),
    ):
        model = loaded_models[model_key]
        if {int(label) for label in model.classes_} != expected_classes:
            raise ValueError(
                f"{display_name} artifact does not match the {selected_mode} labels"
            )
        if model.n_features_in_ != len(loaded_vectorizer.vocabulary_):
            raise ValueError(
                f"{display_name} artifact does not match the saved TF-IDF vectorizer"
            )

    return {
        "bundle": loaded_bundle,
        "vectorizer": loaded_vectorizer,
        "lr_model": loaded_models["logistic_regression"],
        "svm_model": loaded_models["linear_svm"],
        "class_names": expected_names,
        "mode": selected_mode,
    }


def _get_model_assets(model_mode=None):
    selected_mode = (model_mode or MODEL_MODE).strip().lower()
    if selected_mode not in _MODEL_ASSETS:
        _MODEL_ASSETS[selected_mode] = load_model_bundle(selected_mode)
    return _MODEL_ASSETS[selected_mode]


model_assets = _get_model_assets()
model_bundle = model_assets["bundle"]
vectorizer = model_assets["vectorizer"]
lr_model = model_assets["lr_model"]
svm_model = model_assets["svm_model"]


def display_prediction(label, model_mode=None):
    names = (
        BINARY_CLASS_NAMES
        if (model_mode or MODEL_MODE).strip().lower() == "binary"
        else CLASS_NAMES
    )
    return names[int(label)]


# =====================================================
# KNOWN SAFE COMMON CHAT MESSAGES
# =====================================================
SAFE_MESSAGES = {
    "hi",
    "hey",
    "hello",
    "yo",
    "sup",
    "hiya",
    "thanks",
    "thank you",
    "thx",
    "ty",
    "tysm",
    "welcome",
    "you're welcome",
    "no problem",
    "np",
    "good game",
    "good game bro",
    "nice game",
    "gg",
    "ggs",
    "good luck",
    "gl",
    "glhf",
    "bye",
    "goodbye",
    "see ya",
    "see you",
    "cya",
    "later",
    "take care",
    "okay",
    "ok",
    "yes",
    "yeah",
    "yep",
    "yup",
    "nope",
    "nah",
    "sure",
    "alright",
    "right",
    "fine",
    "nice",
    "nice one",
    "well played",
    "good play",
    "nice play",
    "great game",
    "great play",
    "cool",
    "great",
    "awesome",
    "perfect",
    "amazing",
    "good",
    "great stuff",
    "nice job",
    "good job",
    "great job",
    "well done",
    "good team",
    "nice team",
    "great team",
    "we got this",
    "we can do this",
    "we got it",
    "my bad",
    "my mistake",
    "sorry",
    "sorry guys",
    "sorry team",
    "got it",
    "i got it",
    "understood",
    "understand",
    "same",
    "same here",
    "me too",
    "i agree",
    "agreed",
    "coming",
    "on my way",
    "omw",
    "be right back",
    "brb"
}


# =====================================================
# NORMAL CHAT PATTERNS
# =====================================================
NORMAL_CHAT_PATTERNS = [

    # Greetings
    r"^(yo|sup|hiya)$",
    r"^(hey|hi|hello)\s+(bro|man|dude|mate|everyone|guys)$",
    r"^(yo)\s+(bro|man|dude|mate)$",

    # Acknowledgements
    r"^(yes|yeah|yep|yup|nope|nah|sure|alright|right|fine)$",

    # Thanks
    r"^(thx|ty|tysm|welcome|you're welcome|no problem|np)$",

    # Goodbye
    r"^(see ya|see you|cya|later|take care)$",

    # Gaming reactions
    r"^(ggs|wp|glhf|hf|nice|nice one|well played)$",
    r"^(good play|nice play|great game|great play)$",
    r"^(good game|good game bro|nice game)$",

    # Waiting
    r"^(wait|wait a sec|wait a second|one sec|one second|one moment)$",
    r"^(hold on|hold up|hang on|give me a sec|give me a second)$",

    # Joining
    r"^(join me|join us|come join|come join us)$",
    r"^(i'll join|ill join|let me join|can i join)$",

    # Playing
    r"^(lets play|let's play|let us play|wanna play|want to play)$",
    r"^(ready|are you ready)$",
    r"^(start|start the game|let's go|lets go)$",

    # Location / coordination
    r"^(where are you|where r you|where are u)$",
    r"^(where are we|where is everyone|where is everybody)$",
    r"^(come here|come over|come to me)$",
    r"^(follow me|follow us|stay here|stay with me)$",
    r"^(go here|go there|come this way)$",

    # Team communication
    r"^(help me|help us|can you help|can u help)$",
    r"^(cover me|cover us|watch my back)$",
    r"^(wait for me|wait for us)$",
    r"^(look here|look at this|check this)$",
    r"^(listen|listen to me)$",

    # Positive reactions
    r"^(cool|great|awesome|perfect|amazing|good|great stuff)$",

    # Team phrases
    r"^(nice job|good job|great job|well done)$",
    r"^(good team|nice team|great team)$",
    r"^(we got this|we can do this|we got it)$",

    # Apologies / mistakes
    r"^(my bad|my mistake|sorry|sorry guys|sorry team)$",

    # Casual questions
    r"^(what happened|what's happening|whats happening)$",
    r"^(what are you doing|what r you doing|what are u doing)$",
    r"^(which way|what now|what next)$",
    r"^(you there|are you there|anyone there)$",

    # Short responses
    r"^(same|same here|me too|i agree|agreed)$",
    r"^(got it|i got it|understood|understand)$",

    # Gaming status
    r"^(coming|on my way|omw|be right back|brb)$",

    # Casual greeting + person
    r"^(hey|hi|hello|yo)\s+(bro|man|dude|mate|everyone|guys)$",

    # More normal gaming coordination
    r"^(come here|come over|join me|join us)\s+(bro|man|dude|mate)$",
    r"^(what are you doing)\s+(bro|man|dude|mate)$",
]


# =====================================================
# SAFE RESULT HELPER
# =====================================================
def safe_result(selected_model="Safe Message Rule"):
    return {
        "prediction": "Non-Toxic",
        "status": "Safe",
        "confidence": 100.0,
        "confidence_is_calibrated": False,
        "confidence_type": "rule-based result",
        "selected_model": selected_model,

        "logistic_regression_prediction": "Not Evaluated",
        "logistic_regression_confidence": 0.0,

        "svm_prediction": "Not Evaluated",
        "svm_confidence": 0.0,
    }


def _predict_binary(message_vector, assets):
    binary_names = assets["class_names"]
    logistic_model = assets["lr_model"]
    svm_classifier = assets["svm_model"]

    logistic_probabilities = logistic_model.predict_proba(message_vector)[0]
    logistic_index = int(np.argmax(logistic_probabilities))
    logistic_label = int(logistic_model.classes_[logistic_index])
    logistic_confidence = float(logistic_probabilities[logistic_index]) * 100

    svm_label = int(svm_classifier.predict(message_vector)[0])
    svm_margin = float(np.asarray(svm_classifier.decision_function(message_vector)).reshape(-1)[0])
    svm_confidence = abs(svm_margin)

    selected_model = assets["bundle"].get("selection", {}).get(
        "selected_model", "linear_svm"
    )
    if selected_model == "logistic_regression":
        final_label = logistic_label
        final_confidence = logistic_confidence
        confidence_type = "uncalibrated Logistic Regression score (%)"
    elif selected_model == "linear_svm":
        final_label = svm_label
        final_confidence = svm_confidence
        confidence_type = (
            "uncalibrated absolute Linear SVM decision margin; not a probability"
        )
    else:
        raise ValueError(f"Binary bundle selected unknown model: {selected_model}")

    final_prediction = binary_names[final_label]
    logistic_prediction = binary_names[logistic_label]
    svm_prediction = binary_names[svm_label]
    return {
        "prediction": final_prediction,
        "status": final_prediction,
        "confidence": round(final_confidence, 4),
        "confidence_is_calibrated": False,
        "confidence_type": confidence_type,
        "selected_model": selected_model,
        "logistic_regression_prediction": logistic_prediction,
        "logistic_regression_confidence": round(logistic_confidence, 4),
        "logistic_regression_confidence_type": (
            "uncalibrated Logistic Regression score (%)"
        ),
        "svm_prediction": svm_prediction,
        "svm_confidence": round(svm_confidence, 4),
        "svm_confidence_type": (
            "uncalibrated absolute decision margin; not a probability"
        ),
        "svm_score": round(svm_margin, 6),
        "svm_score_type": "signed LinearSVC decision_function margin",
    }


def predict_message(message: str, model_mode=None):
    assets = _get_model_assets(model_mode)
    selected_mode = assets["mode"]
    cleaned_message = clean_text(message)

    if selected_mode == "binary":
        if not cleaned_message:
            return {
                "prediction": "Non-Toxic",
                "status": "Non-Toxic",
                "confidence": 0.0,
                "confidence_is_calibrated": False,
                "confidence_type": "unavailable for empty normalized text",
                "selected_model": assets["bundle"]["selection"]["selected_model"],
                "logistic_regression_prediction": "Not Evaluated",
                "logistic_regression_confidence": 0.0,
                "svm_prediction": "Not Evaluated",
                "svm_confidence": 0.0,
                "svm_score": None,
                "svm_score_type": "not evaluated",
            }
        message_vector = assets["vectorizer"].transform([cleaned_message])
        return _predict_binary(message_vector, assets)

    if not cleaned_message:
        return safe_result("Empty Message Rule")

    if cleaned_message in SAFE_MESSAGES:
        return safe_result("Safe Message Rule")

    if any(
        re.fullmatch(pattern, cleaned_message)
        for pattern in NORMAL_CHAT_PATTERNS
    ):
        return safe_result("Normal Chat Rule")

    message_vector = assets["vectorizer"].transform([cleaned_message])

    lr_probabilities = assets["lr_model"].predict_proba(message_vector)[0]

    lr_index = int(np.argmax(lr_probabilities))
    lr_prediction = assets["lr_model"].classes_[lr_index]
    lr_confidence = float(lr_probabilities[lr_index])

    svm_scores = assets["svm_model"].decision_function(message_vector)[0]
    svm_probabilities = np.exp(svm_scores - np.max(svm_scores))
    svm_probabilities /= svm_probabilities.sum()
    svm_index = int(np.argmax(svm_probabilities))
    svm_prediction = assets["svm_model"].classes_[svm_index]
    svm_confidence = float(svm_probabilities[svm_index])

    final_prediction = svm_prediction
    status = "Safe" if final_prediction == 0 else "Toxic"
    final_confidence = svm_confidence

    return {
        "prediction": display_prediction(final_prediction, selected_mode),
        "status": status,
        "confidence": round(final_confidence * 100, 2),
        "confidence_is_calibrated": False,
        "selected_model": "Balanced Linear SVM, C=0.5 (uncalibrated score)",
        "logistic_regression_prediction": display_prediction(lr_prediction, selected_mode),
        "logistic_regression_confidence": round(lr_confidence * 100, 2),
        "svm_prediction": display_prediction(svm_prediction, selected_mode),
        "svm_confidence": round(svm_confidence * 100, 2),
    }


# =====================================================
# Text preprocessing
# =====================================================
def clean_text(text: str):

    text = str(text).lower()

    # Remove URLs
    text = re.sub(
        r"http\S+|www\S+|https\S+",
        "",
        text
    )

    # Remove @mentions
    text = re.sub(
        r"@\w+",
        "",
        text
    )

    # Remove # symbol but keep hashtag text
    text = re.sub(
        r"#",
        "",
        text
    )

    # Remove punctuation and special characters
    text = re.sub(
        r"[^\w\s]",
        " ",
        text
    )

    # Normalize whitespace
    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text
