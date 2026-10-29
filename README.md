# Toxic Chat Detection for Online Games

This project contains a FastAPI backend and a React/Vite frontend for classifying gaming chat with the existing GameTox dataset.

## Requirements

- Python 3.14 (the checked-in Python dependencies have been verified in this environment)
- Node.js 20.19+ or 22.12+
- npm

The backend uses the model artifacts under `ml/`. The source dataset is `dataset/train.csv`; training and evaluation scripts do not change it.

## Model modes

The backend reads `TOXIC_MODEL_MODE` when it starts:

- `six_class` (default): loads the existing `ml/gametox_model_bundle.pkl`.
- `binary`: loads `ml/gametox_binary_model_bundle.pkl`. Original label 0 maps to `Non-Toxic`; original labels 1–5 map to `Toxic`.

An invalid value prevents startup with a clear configuration error. Set the environment variable before launching Uvicorn.

The binary bundle contains both Logistic Regression and Linear SVM. Linear SVM remains selected because it had the strongest grouped training-only cross-validation macro F1 among the compared configurations (81.86% vs. 80.23%). On the untouched holdout, SVM achieved higher Toxic precision and macro F1, while Logistic Regression achieved higher Toxic recall. SVM produced 583 false negatives and 189 false positives; Logistic Regression produced 382 false negatives and 751 false positives. For the final demonstration, retain SVM as the better balanced, higher-precision choice; choose Logistic Regression only if reducing missed toxic messages is more important than avoiding additional false alarms. The manually selected 20-message benchmark matched 9/20 for SVM and 16/20 for Logistic Regression, but is too small and selective to override grouped evaluation. Neither model's score is a calibrated probability, and neither reliably detects every threat or harassment message.

### Verified binary grouped evaluation

The evaluation uses 42,959 original rows; 605 empty-normalized messages are excluded. The first fold of a five-fold `StratifiedGroupKFold` split is the holdout, grouped by normalized text (`random_state=42`); it has zero normalized-text overlap with training. Hyperparameters are selected with three-fold grouped cross-validation on training data only.

| Model | Holdout accuracy | Toxic precision | Toxic recall | Toxic F1 | Macro F1 |
|---|---:|---:|---:|---:|---:|
| Linear SVM (`C=0.5`, unweighted) | 90.89% | 84.67% | 64.17% | 73.01% | 83.76% |
| Logistic Regression (`C=1.0`, balanced) | 86.63% | 62.37% | 76.52% | 68.73% | 80.11% |
| Majority-class baseline | 80.80% | 0.00% | 0.00% | 0.00% | 44.69% |

These are grouped holdout metrics, not the manually selected 20-message functional match rate. The held-out SVM confusion matrix is `[[6656, 189], [583, 1044]]`; rows and columns are ordered Non-Toxic, Toxic.

The dataset is substantially imbalanced, and class collapse does not eliminate annotation ambiguity. Original labels 3, 4, and 5 have only 279, 60, and 24 rows respectively, so their patterns are sparsely represented even though they are combined into the Toxic class. Empty normalized messages are excluded. Manual conversation examples remain useful as a functional check but are not representative estimates of deployment performance. In particular, the lower toxic recall means some toxic messages are missed.

## Windows PowerShell setup and startup

Run commands from the repository root (`D:\cv\Microproject`). Use separate terminals for backend and frontend.

### Backend

```powershell
Set-Location D:\cv\Microproject
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:TOXIC_MODEL_MODE = "binary"
$env:DATABASE_URL = "sqlite:///D:/cv/Microproject/toxic_backend/local.db"
python -m uvicorn toxic_backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

For the original six-class behavior, use `$env:TOXIC_MODEL_MODE = "six_class"` or omit `TOXIC_MODEL_MODE`. The backend exposes the interactive API documentation at `http://127.0.0.1:8000/docs`; prediction requests use `POST /predict` with `{"message": "chat text"}`. The game chat flow uses the authenticated `POST /rooms/{room_id}/chat` endpoint.

### Frontend

```powershell
Set-Location D:\cv\Microproject\toxic_frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the URL Vite prints (normally `http://127.0.0.1:5173`). The default frontend API URL is `http://127.0.0.1:8000`. To override it, set `VITE_API_URL` before starting Vite.

## Training and evaluation

Training is not required to run the existing binary bundle. To reproduce the binary training and grouped evaluation:

```powershell
Set-Location D:\cv\Microproject
.\.venv\Scripts\Activate.ps1
python ml\train_binary.py
```

This writes separate binary models and reports under `ml/` and `results/`, including a row-traceable split file. It does not replace the six-class artifacts.

## Validation commands

Run the backend tests and legacy six-class service checks:

```powershell
Set-Location D:\cv\Microproject
.\.venv\Scripts\Activate.ps1
$env:TOXIC_MODEL_MODE = "six_class"
python -m pytest -q
```

The binary-mode functional test and focused service tests are:

```powershell
$env:TOXIC_MODEL_MODE = "binary"
python test_predictions.py
python -m pytest toxic_backend\tests\test_binary_model_service.py -q
```

Run frontend validation from its directory:

```powershell
Set-Location D:\cv\Microproject\toxic_frontend
npm run lint
npm run build
```

The binary SVM response includes a signed decision margin and marks it as uncalibrated. A Linear SVM margin is not a probability and must not be interpreted as a percent likelihood.
