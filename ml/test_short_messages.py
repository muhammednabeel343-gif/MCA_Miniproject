import joblib

VECTORIZER_PATH = "ml/tfidf_vectorizer.pkl"
MODEL_PATH = "ml/logistic_regression_model.pkl"

vectorizer = joblib.load(VECTORIZER_PATH)
model = joblib.load(MODEL_PATH)

messages = [
    "hey",
    "hi",
    "hello",
    "yo",
    "gg",
    "good game",
    "nice",
    "okay",
    "join me",
    "you are an idiot",
    "shut up",
    "you are stupid"
]

X = vectorizer.transform(messages)

predictions = model.predict(X)
probabilities = model.predict_proba(X)

for message, prediction, probability in zip(
    messages,
    predictions,
    probabilities
):
    confidence = max(probability) * 100

    print("--------------------------------")
    print("Message:", message)
    print("Prediction:", prediction)
    print("Confidence:", round(confidence, 2), "%")