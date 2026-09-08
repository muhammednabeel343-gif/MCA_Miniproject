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

LR_MODEL_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "logistic_regression_model.pkl"
)

SVM_MODEL_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "svm_model.pkl"
)

VECTORIZER_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "tfidf_vectorizer.pkl"
)


# -----------------------------
# Load models and vectorizer
# -----------------------------
lr_model = joblib.load(LR_MODEL_PATH)
svm_model = joblib.load(SVM_MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)


# -----------------------------
# User-friendly labels
LABEL_MAP = {
    "age": "age",
    "ethnicity": "ethnicity",
    "gender": "gender",
    "religion": "religion",
    "other_cyberbullying": "other_cyberbullying",
    "not_cyberbullying": "not_cyberbullying"
}


# =====================================================
# CLEARLY TOXIC WORDS
# =====================================================
TOXIC_WORDS = {
    "idiot",
    "stupid",
    "dumb",
    "moron",
    "loser",
    "trash",
    "sucks",
    "suck",
    "shut up",
    "hate",
    "pathetic",
    "useless",
    "fool",
    "jerk",
    "ugly",
    "annoying"
}


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
        "selected_model": selected_model,

        "logistic_regression_prediction": "Not Evaluated",
        "logistic_regression_confidence": 0.0,

        "svm_prediction": "Not Evaluated",
        "svm_confidence": 0.0
    }


# =====================================================
# TOXIC RESULT HELPER
# =====================================================
def toxic_keyword_result():
    return {
        "prediction": "General Toxicity",
        "status": "Toxic",
        "confidence": 100.0,
        "selected_model": "Toxic Keyword Rule",

        "logistic_regression_prediction": "Not Evaluated",
        "logistic_regression_confidence": 0.0,

        "svm_prediction": "Not Evaluated",
        "svm_confidence": 0.0
    }


# =====================================================
# Prediction
# =====================================================
def predict_message(message: str):

    # -----------------------------
    # Preprocess message
    # -----------------------------
    cleaned_message = clean_text(message)

    # -----------------------------
    # Empty message
    # -----------------------------
    if not cleaned_message:
        return safe_result("Empty Message Rule")

    # =================================================
    # IMPORTANT:
    # Check toxic words BEFORE normal chat rules
    # =================================================
    for word in TOXIC_WORDS:

        # For multi-word toxic phrases
        if " " in word:
            if word in cleaned_message:
                return toxic_keyword_result()

        # For single toxic words
        else:
            if re.search(
                r"\b" + re.escape(word) + r"\b",
                cleaned_message
            ):
                return toxic_keyword_result()

    # =================================================
    # Exact known safe messages
    # =================================================
    if cleaned_message in SAFE_MESSAGES:
        return safe_result("Safe Message Rule")

    # =================================================
    # Normal conversational / gaming chat
    # =================================================
    if any(
        re.fullmatch(pattern, cleaned_message)
        for pattern in NORMAL_CHAT_PATTERNS
    ):
        return safe_result("Normal Chat Rule")

    # =================================================
    # Convert to TF-IDF
    # =================================================
    message_vector = vectorizer.transform(
        [cleaned_message]
    )

    # =================================================
    # Logistic Regression prediction
    # =================================================
    lr_probabilities = lr_model.predict_proba(
        message_vector
    )[0]

    lr_index = np.argmax(lr_probabilities)

    lr_prediction = lr_model.classes_[lr_index]

    lr_confidence = float(
        lr_probabilities[lr_index]
    )

    # =================================================
    # SVM prediction
    # =================================================
    svm_probabilities = svm_model.predict_proba(
        message_vector
    )[0]

    svm_index = np.argmax(svm_probabilities)

    svm_prediction = svm_model.classes_[svm_index]

    svm_confidence = float(
        svm_probabilities[svm_index]
    )

    # =================================================
    # Ensemble probabilities
    # =================================================
    all_classes = sorted(
        set(lr_model.classes_) |
        set(svm_model.classes_)
    )

    ensemble_probabilities = {}

    for class_name in all_classes:

        lr_class_probability = 0.0
        svm_class_probability = 0.0

        if class_name in lr_model.classes_:

            lr_class_index = list(
                lr_model.classes_
            ).index(class_name)

            lr_class_probability = float(
                lr_probabilities[lr_class_index]
            )

        if class_name in svm_model.classes_:

            svm_class_index = list(
                svm_model.classes_
            ).index(class_name)

            svm_class_probability = float(
                svm_probabilities[svm_class_index]
            )

        ensemble_probabilities[class_name] = (
            lr_class_probability +
            svm_class_probability
        ) / 2

    # =================================================
    # Safe vs Toxic
    # =================================================
    safe_probability = ensemble_probabilities.get(
        "not_cyberbullying",
        0.0
    )

    toxic_probability = sum(
        probability
        for class_name, probability
        in ensemble_probabilities.items()
        if class_name != "not_cyberbullying"
    )

    # =================================================
    # Final decision
    # =================================================
    if safe_probability >= toxic_probability:

        status = "Safe"

        final_prediction = "not_cyberbullying"

        final_confidence = safe_probability

    else:

        status = "Toxic"

        toxic_classes = {
            class_name: probability
            for class_name, probability
            in ensemble_probabilities.items()
            if class_name != "not_cyberbullying"
        }

        final_prediction = max(
            toxic_classes,
            key=toxic_classes.get
        )

        final_confidence = toxic_classes[
            final_prediction
        ]

    # =================================================
    # Return result
    # =================================================
    return {
        "prediction": LABEL_MAP.get(
            final_prediction,
            final_prediction
        ),

        "status": status,

        "confidence": round(
            final_confidence * 100,
            2
        ),

        "selected_model": "Ensemble (LR + SVM)",

        "logistic_regression_prediction": LABEL_MAP.get(
            lr_prediction,
            lr_prediction
        ),

        "logistic_regression_confidence": round(
            lr_confidence * 100,
            2
        ),

        "svm_prediction": LABEL_MAP.get(
            svm_prediction,
            svm_prediction
        ),

        "svm_confidence": round(
            svm_confidence * 100,
            2
        )
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
        r"[^a-zA-Z0-9\s]",
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
