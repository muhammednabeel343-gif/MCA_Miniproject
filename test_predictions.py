import os

from toxic_backend.app.services.model_service import predict_message

# Set TOXIC_MODEL_MODE=binary to evaluate the binary bundle; the six-class
# expected annotations remain unchanged below and are converted only for scoring.
MODEL_MODE = os.getenv("TOXIC_MODEL_MODE", "six_class").strip().lower()

# A continuous gaming conversation between two friends.
# Expected progression: peaceful -> frustration -> toxicity -> escalation

conversation = [
    # Stage 1: Peaceful gaming — Non-Toxic
    (1, "Alex", "Non-Toxic",
     "Hey bro, ready for another match?"),
    (2, "Sam", "Non-Toxic",
     "Yeah, let's play together and have some fun."),
    (3, "Alex", "Non-Toxic",
     "Nice teamwork in the last round, well played!"),
    (4, "Sam", "Non-Toxic",
     "Thanks bro, let's try to win this one too."),
    (5, "Alex", "Non-Toxic",
     "I will kill it in this game!"),

    # Stage 2: Frustration begins
    (6, "Sam", "Other Offensive Texts",
     "That was a stupid move, why did you do that?"),
    (7, "Alex", "Insults and Flaming",
     "Stop blaming me, you are a fool."),
    (8, "Sam", "Insults and Flaming",
     "You are terrible at this game."),
    (9, "Alex", "Insults and Flaming",
     "Fuck you, you ruined the whole match."),
    (10, "Sam", "Other Offensive Texts",
     "Shut up and stop talking nonsense."),

    # Stage 3: Exclusion and harassment
    (11, "Alex", "Hate and Harassment",
     "People like you do not belong in our team."),
    (12, "Sam", "Hate and Harassment",
     "Everyone should target and harass that player."),
    (13, "Alex", "Hate and Harassment",
     "You are not welcome in this community."),
    (14, "Sam", "Hate and Harassment",
     "Let's make sure nobody wants to play with you again."),

    # Stage 4: Direct threats
    (15, "Alex", "Threats",
     "I will hurt you if you keep doing this."),
    (16, "Sam", "Threats",
     "You will regret this, I will get you."),
    (17, "Alex", "Threats",
     "I will find you and make you pay for this."),

    # Stage 5: Extremist content
    (18, "Sam", "Extremism",
     "Violence is necessary to achieve extremist goals."),
    (19, "Alex", "Extremism",
     "Our extremist movement wants to spread its ideology."),
    (20, "Sam", "Extremism",
     "Support the use of violence for extremist causes."),
]

correct = 0
total = len(conversation)

for turn, speaker, expected, message in conversation:
    result = predict_message(message)

    final_prediction = result["prediction"]
    expected_prediction = (
        "Non-Toxic" if expected == "Non-Toxic" else "Toxic"
    ) if MODEL_MODE == "binary" else expected

    # Normalize labels before comparing them
    normalize = lambda label: (
        label.lower().replace("&", "and").strip()
    )

    matched = normalize(final_prediction) == normalize(expected_prediction)
    correct += int(matched)

    print("\n" + "=" * 75)
    print(f"TURN {turn} | {speaker}")
    print("Message:", message)
    print("Expected:", expected_prediction)
    print("-" * 75)

    print(
        "Logistic Regression:",
        result["logistic_regression_prediction"],
        "| Score:",
        result["logistic_regression_confidence"],
        result.get("logistic_regression_confidence_type", "uncalibrated score (%)")
    )

    print(
        "SVM:",
        result["svm_prediction"],
        "| Score:",
        result["svm_confidence"],
        result.get("svm_confidence_type", "uncalibrated score (%)")
    )

    print("-" * 75)
    print(
        "FINAL PREDICTION:",
        final_prediction,
        "| Status:",
        result["status"],
        "| Score:",
        result["confidence"],
        result.get("confidence_type", "uncalibrated score (%)"),
        "| Selected model:",
        result["selected_model"]
    )

    print(
        "Functional test:",
        "MATCH" if matched else "MISMATCH"
    )

print("\n" + "=" * 75)
print(f"Functional matches: {correct}/{total}")
print(f"Functional match rate: {correct / total * 100:.2f}%")

print("\nIMPORTANT:")
print("These are manually selected test messages.")
print("The match rate is NOT the model's test-set accuracy.")
print("Ambiguous messages may reasonably receive different labels.")
