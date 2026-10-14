from toxic_backend.app.services.model_service import predict_message

test_messages = [
    # 0 - Non-Toxic
    ("Good game everyone", "Non-Toxic"),
    ("Nice teamwork, well played", "Non-Toxic"),
    ("I will kill it in the game", "Non-Toxic"),

    # 1 - Insults and Flaming
    ("You are a fool", "Insults and Flaming"),
    ("Fuck you", "Insults and Flaming"),
    ("You are terrible at this game", "Insults and Flaming"),

    # 2 - Other Offensive Texts
    ("Shut up and stop talking nonsense", "Other Offensive Texts"),
    ("Your comments are disgusting", "Other Offensive Texts"),
    ("That was a stupid and annoying comment", "Other Offensive Texts"),

    # 3 - Hate and Harassment
    ("People like you do not belong here", "Hate and Harassment"),
    ("Everyone should target and harass that player", "Hate and Harassment"),
    ("You are not welcome in this community", "Hate and Harassment"),

    # 4 - Threats
    ("I will kill you", "Threats"),
    ("I am going to hurt you", "Threats"),
    ("You will regret this, I will get you", "Threats"),

    # 5 - Extremism
    ("Violence is necessary to achieve extremist goals", "Extremism"),
    ("Our extremist movement wants to spread its ideology", "Extremism"),
    ("Support the use of violence for extremist causes", "Extremism"),
]

correct = 0
total = len(test_messages)

for message, expected in test_messages:
    result = predict_message(message)

    final_prediction = result["prediction"]
    matched = (
        final_prediction.lower().replace("&", "and").strip()
        == expected.lower().replace("&", "and").strip()
    )

    correct += int(matched)

    print("\\n" + "=" * 65)
    print("Message:", message)
    print("Expected:", expected)
    print("-" * 65)

    print(
        "Logistic Regression:",
        result["logistic_regression_prediction"],
        "-",
        result["logistic_regression_confidence"],
        "%"
    )

    print(
        "SVM:",
        result["svm_prediction"],
        "-",
        result["svm_confidence"],
        "%"
    )

    print("-" * 65)
    print(
        "FINAL:",
        final_prediction,
        "-",
        result["status"],
        "-",
        result["confidence"],
        "%",
        "| Model:",
        result["selected_model"]
    )
    print("Functional test:", "MATCH" if matched else "MISMATCH")

print("\\n" + "=" * 65)
print(f"Functional matches: {correct}/{total}")
print("Note: These are manually selected functional examples,")
print("not a formal evaluation of model accuracy.")