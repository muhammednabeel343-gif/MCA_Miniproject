const TOXIC_PREDICTIONS = new Set([
  "toxic",
  "insultsflaming",
  "otheroffensivetexts",
  "hateharassment",
  "threats",
  "extremism",
]);
const NON_TOXIC_PREDICTIONS = new Set(["nontoxic", "safe"]);
const TOXIC_CATEGORY_LABELS = {
  insultsflaming: "Insults & Flaming",
  otheroffensivetexts: "Other Offensive Texts",
  hateharassment: "Hate & Harassment",
  threats: "Threats",
  extremism: "Extremism",
};

function normalizePrediction(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

export function formatModelScore(record) {
  const score = Number(record?.confidence);
  if (!Number.isFinite(score)) {
    return "Unavailable";
  }

  const selectedModel = String(record?.selected_model || "").toLowerCase();
  if (selectedModel === "linear_svm") {
    return `${score.toFixed(4)} (uncalibrated SVM margin)`;
  }
  if (selectedModel === "logistic_regression") {
    return `${score.toFixed(2)}/100 (uncalibrated LR score)`;
  }
  return `${score}/100 (uncalibrated score)`;
}

export function isToxicStatus(status) {
  return getPredictionLabel(status) === "TOXIC";
}

export function getPredictionLabel(prediction, fallbackStatus = "") {
  const label = normalizePrediction(prediction);

  if (TOXIC_PREDICTIONS.has(label)) return "TOXIC";
  if (NON_TOXIC_PREDICTIONS.has(label)) return "NON-TOXIC";

  const fallback = normalizePrediction(fallbackStatus);
  if (TOXIC_PREDICTIONS.has(fallback)) return "TOXIC";
  if (NON_TOXIC_PREDICTIONS.has(fallback)) return "NON-TOXIC";

  return null;
}

export function getCategoryLabel(prediction) {
  const normalized = normalizePrediction(prediction);
  if (normalized === "nontoxic" || normalized === "safe") return "Non-Toxic";
  if (normalized === "toxic") return "Toxic (binary model)";
  return TOXIC_CATEGORY_LABELS[normalized] || "Unclassified toxic";
}
