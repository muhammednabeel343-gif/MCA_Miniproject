import sys
import os

# Allow Python to find the backend package
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from toxic_backend.app.services.model_service import predict_message


# =====================================================
# TEST 1 - NORMAL GAMING CHAT
# =====================================================

normal_chat_messages = [
    "good game bro",
    "where are you bro",
    "are you ready",
    "nice play",
    "well played",
    "join us",
    "lets play",
    "on my way",
]


# =====================================================
# TEST 2 - CLEARLY TOXIC CHAT
# =====================================================

toxic_messages = [
    "you are an idiot",
    "you are stupid",
    "shut up idiot",
    "you suck",
    "you are trash",
    "go away idiot",
    "stupid player",
    "what an idiot",
]


# =====================================================
# TEST 3 - MIXED / BOUNDARY CASES
# =====================================================

boundary_messages = [
    "you are funny",
    "you are crazy",
    "good game idiot",
    "nice idiot",
    "hey idiot",
    "stupid",
    "hello bro",
    "come here bro",
]


# =====================================================
# FUNCTION TO TEST MESSAGES
# =====================================================

def test_messages(title, messages):

    print("\n")
    print("=" * 60)
    print(title)
    print("=" * 60)

    for message in messages:

        result = predict_message(message)

        print("--------------------------------")
        print("Message:", message)
        print("Prediction:", result["prediction"])
        print("Status:", result["status"])
        print("Confidence:", result["confidence"], "%")

        print(
            "LR:",
            result["logistic_regression_prediction"],
            result["logistic_regression_confidence"],
            "%"
        )

        print(
            "SVM:",
            result["svm_prediction"],
            result["svm_confidence"],
            "%"
        )


# =====================================================
# RUN ALL TESTS
# =====================================================

if __name__ == "__main__":

    test_messages(
        "TEST 1 - NORMAL GAMING CHAT",
        normal_chat_messages
    )

    test_messages(
        "TEST 2 - CLEARLY TOXIC CHAT",
        toxic_messages
    )

    test_messages(
        "TEST 3 - MIXED / BOUNDARY CASES",
        boundary_messages
    )