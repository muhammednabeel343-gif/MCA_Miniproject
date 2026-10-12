from toxic_backend.app.services.model_service import predict_message


test_messages = [
    "you are a fool ",
    
    
]


for message in test_messages:
    result = predict_message(message)

    print("\n" + "=" * 60)
    print("Message:", message)
    print("-" * 60)

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

    print("-" * 60)
    print(
        "FINAL:",
        result["prediction"],
        "-",
        result["status"],
        "-",
        result["confidence"],
        "%",
        "| Model:",
        result["selected_model"]
    )