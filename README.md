# CKD Risk Lab

*Machine Learning-Based Chronic Kidney Disease Prediction System*

Estimate chronic kidney disease (CKD) risk from 24 routine clinical measurements, see which values drive the result, and test what-if changes. Seven machine-learning classifiers vote through a soft-voting ensemble, behind a Flask API and a browser interface with no build step.

![The Assess page: patient form on the left, result panel on the right](docs/assess-light.png)

> For education and research only. This is not a medical device and does not provide a diagnosis.

| Dark theme | Model evaluation |
| --- | --- |
| ![Dark theme with an advanced-findings sample](docs/assess-dark.png) | ![The Models page](docs/models.png) |

## Objectives

- Detect potential CKD cases with machine learning.
- Improve accuracy through ensemble learning.
- Make every result understandable: show which measurements drive it and how far the models agree.
- Demonstrate machine learning for healthcare analytics, with honest evaluation.

## What it does

- **Assess.** A form generated from the API's schema, with a typical-range strip for each lab value and a warning when a value lies outside the range the models were trained on. Three sample patients load in one click. Blank fields are allowed: missing values are imputed inside each model's pipeline, and the result reports how complete the input was. The arrow keys step a number, and Ctrl+Enter (Cmd+Enter on macOS) runs the assessment. With "Update as I type" on, the result refreshes after every edit.
- **Risk strip.** One axis shows the ensemble risk, every model's own estimate and four risk bands. A tight cluster of dots means the models agree; a spread means the case is near the 50% decision line.
- **Model votes and reliability.** Each model's risk and vote, plus a reliability level (high, moderate or low) based on how many measurements were provided, how many models agree and whether values fall inside the training range.
- **Why this result.** Shapley values measured against a typical healthy profile. They add up to the difference between that profile's risk and the patient's risk.
- **What if.** Pick any measurement, drag a slider or the curve, and watch the estimate move. One API call sweeps the range; after that the projection is instant. "Use this value" writes the value back to the form.
- **Models.** Cross-validated accuracy, precision, recall, F1 and ROC AUC for every model (sortable), ROC curves with a zoom toggle, a confusion matrix per model, feature importance and a data-quality summary.
- **Batch.** Upload a CSV, get a scored table you can filter and sort, and download the results.
- **History.** Your last 30 manual assessments, kept in this browser only. Sample loads and live updates are not saved.
- **Report.** "Print report" opens a clean A4 report of about two pages, which you can save as a PDF. "Copy summary" puts a plain-text summary on the clipboard.
- **About.** How an estimate is made, how to read the risk strip, limits, privacy, the project developer and the tech stack.
- Light and dark themes (it follows your system, with a toggle), keyboard friendly, responsive down to phone width, and aware of the reduced-motion setting.

## Results

Cross-validated on the 400 bundled patients: 5-fold stratified cross-validation, repeated twice, so every patient is scored by models that never saw them. The figures come from one training run with Python 3.13.3, scikit-learn 1.6.1 and XGBoost 3.4.1.

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
| --- | --- | --- | --- | --- | --- |
| **Voting ensemble** | 99.0% | 99.2% | 99.2% | 99.2% | 1.000 |
| Logistic regression | 99.0% | 99.2% | 99.2% | 99.2% | 1.000 |
| Decision tree | 97.5% | 97.6% | 98.4% | 98.0% | 0.982 |
| Random forest | 99.0% | 98.4% | 100.0% | 99.2% | 0.999 |
| XGBoost | 98.0% | 98.4% | 98.4% | 98.4% | 0.999 |
| K-nearest neighbors | 96.8% | 100.0% | 94.8% | 97.3% | 0.997 |
| Support vector machine | 100.0% | 100.0% | 100.0% | 100.0% | 1.000 |
| Gaussian naive Bayes | 96.5% | 100.0% | 94.4% | 97.1% | 1.000 |

The ensemble makes 4 mistakes in 400 patients (2 missed CKD cases and 2 false alarms) and varies by about 1 point of accuracy between folds. The models lean most on urine specific gravity, hemoglobin and albumin in urine.

This dataset is small and its classes are well separated, so read near-perfect scores as a sign of an easy dataset, not of clinical performance. Your numbers will differ slightly with other library versions. The Models page always shows the figures for the model you are running.

## Quick start

Python 3.10 or newer (developed on 3.12 and 3.13).

```powershell
# Windows (PowerShell)
git clone https://github.com/Afhaam11/Machine-Learning-Based-Chronic-Kidney-Disease-Prediction-System.git
cd Machine-Learning-Based-Chronic-Kidney-Disease-Prediction-System
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

If PowerShell refuses to run the activation script, allow scripts for this window only with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.

```bash
# macOS / Linux
git clone https://github.com/Afhaam11/Machine-Learning-Based-Chronic-Kidney-Disease-Prediction-System.git
cd Machine-Learning-Based-Chronic-Kidney-Disease-Prediction-System
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open <http://127.0.0.1:8000>.

The first launch trains the models, which takes roughly 10 to 30 seconds depending on your machine. After that the app starts immediately. Training writes three files into `models/`.

`python run.py` takes these options:

| Option | Meaning |
| --- | --- |
| `--port 9000` | Use another port (default 8000) |
| `--host 0.0.0.0` | Listen on all interfaces (default `127.0.0.1`, which keeps patient data on your machine) |
| `--retrain` | Train the models again before starting |
| `--debug` | Flask development server with auto-reload, for development |

## How it works

```
Browser (static HTML, CSS and ES modules, no build step)
   |  JSON over HTTP
Flask API ........ ckdlab/api.py        routes, validation errors, security headers
   |
PredictionService  ckdlab/service.py    predict, explain, what-if, batch (no HTTP knowledge)
   |-- schema.py    one definition of the 24 measurements: validation, encoding, the browser form
   |-- data.py      cleaning shared by training, uploads and single requests
   |-- modeling.py  seven scikit-learn pipelines and the soft-voting ensemble
   |-- explain.py   Monte-Carlo Shapley values and what-if sweeps
   `-- train.py     cross-validation, final fit, artifacts written to models/
```

1. **Clean.** Stray tabs and spaces and `?` placeholders are repaired. Implausible values (such as sodium 4.5 or creatinine 76) are blanked so they count as missing.
2. **Encode.** Every yes/no style measurement is encoded once, in `schema.py`, with 1 meaning the adverse finding (abnormal, present, yes, poor).
3. **Fit.** Each of the seven classifiers sits in its own pipeline: median imputation and scaling for numeric values, most-frequent imputation for yes/no values.
4. **Vote.** The ensemble risk is the average of the seven probabilities. A risk of 50% or more is predicted as CKD.
5. **Explain.** Shapley values against a typical healthy profile, and what-if sweeps of one measurement at a time.

### Project layout

```
ckdlab/            the Python package (above)
  static/          the browser interface: index.html, css/, js/ (ES modules), img/
data/              kidney_disease.csv, the training data
docs/              screenshots used in this README
legacy/            the original Streamlit app, notebook and pickles (see legacy/README.md)
models/            written by training: ckd_ensemble.joblib, metrics.json, reference.json (ignored by git)
tests/             unit and API tests
Dockerfile         container image (see Docker below)
requirements.txt   Python dependencies
run.py             start the server
```

### What changed from the original version

| Before | Now |
| --- | --- |
| Streamlit app, form hand-coded | Flask API plus a custom front end; the form is generated from `/api/schema` |
| Imputation ran on the whole dataset before the train/test split, leaking test statistics | Imputation and scaling live inside each model's `Pipeline` and are re-fitted in every fold |
| KNN, SVM and logistic regression saw unscaled features | They get standardised inputs |
| Hard voting: a class only, no probability | Soft voting: a risk percentage, plus the vote tally |
| One stratified 80/20 split, 80 test patients | 5-fold stratified cross-validation, repeated twice; every patient is scored by models that never saw them |
| The app encoded appetite as good = 1 while training used poor = 1 | Every encoding is defined once in `schema.py`, with a test |
| Pickles tied to exact library versions | Models retrain on start-up if the scikit-learn version has changed |
| No handling of missing values in the app | Any field can be left blank, and the result says how much that matters |
| Implausible values (sodium 4.5, creatinine 76) were trained on as they were | They are blanked and treated as missing, in training and at prediction time |

## Input fields

Every field is optional, but at least 5 measurements are needed for a prediction. Values outside the limits below are rejected by the API (HTTP 422). In a batch file they are blanked and reported on that row instead.

**Vitals**

| Field | Measurement | Accepted values |
| --- | --- | --- |
| `age` | Age | 0 to 120 years |
| `bp` | Blood pressure | 30 to 260 mm Hg |

**Urinalysis**

| Field | Measurement | Accepted values |
| --- | --- | --- |
| `sg` | Urine specific gravity | 1.000 to 1.050 (the form offers 1.005, 1.010, 1.015, 1.020, 1.025) |
| `al` | Albumin in urine | whole number 0 to 5 (dipstick scale) |
| `su` | Sugar in urine | whole number 0 to 5 (dipstick scale) |
| `rbc` | Red blood cells in urine | `normal` or `abnormal` |
| `pc` | Pus cells in urine | `normal` or `abnormal` |
| `pcc` | Pus cell clumps | `notpresent` or `present` |
| `ba` | Bacteria in urine | `notpresent` or `present` |

**Blood work**

| Field | Measurement | Accepted values |
| --- | --- | --- |
| `bgr` | Random blood glucose | 10 to 900 mg/dL |
| `bu` | Blood urea | 1 to 500 mg/dL |
| `sc` | Serum creatinine | 0.1 to 40 mg/dL |
| `sod` | Sodium | 80 to 180 mEq/L |
| `pot` | Potassium | 1 to 10 mEq/L |
| `hemo` | Hemoglobin | 2 to 25 g/dL |
| `pcv` | Packed cell volume | 5 to 70% |
| `wc` | White blood cell count | 500 to 60,000 cells/cmm |
| `rc` | Red blood cell count | 1 to 10 million/cmm |

**History and signs**

| Field | Measurement | Accepted values |
| --- | --- | --- |
| `htn` | Hypertension | `no` or `yes` |
| `dm` | Diabetes mellitus | `no` or `yes` |
| `cad` | Coronary artery disease | `no` or `yes` |
| `appet` | Appetite | `good` or `poor` |
| `pe` | Pedal edema | `no` or `yes` |
| `ane` | Anemia | `no` or `yes` |

The API also accepts friendly spellings for yes/no fields, such as `true`, `false` or `absent`.

### Sample patients

Three illustrative profiles ship with the app (they are not records from the dataset). The tests check that the first and last land where you would expect.

| Sample | What it looks like | What to expect |
| --- | --- | --- |
| Typical adult | Normal vitals, clear urine, blood values inside the usual ranges | Low risk, under 20% |
| Mixed signals | Typical blood chemistry, but hypertension, swollen ankles, a higher blood pressure reading and abnormal red cells in the urine | Away from both extremes, and the models often split. The exact numbers vary by training run |
| Advanced findings | High creatinine and urea, low hemoglobin, heavy protein in the urine, with hypertension, diabetes, edema and poor appetite | High risk, above 80% |

## Batch scoring

Open the Batch page, drop in a CSV, and download the scored results. Use "Download a template" for the exact layout, or upload the original dataset as it is.

- Column names match the field names above and are not case-sensitive. Comma and semicolon delimiters both work.
- An id column (`id`, `patient_id`, `patient`, `name` or `mrn`) is carried through to the results.
- If the file has a label column (`classification`, `class`, `label`, `target` or `diagnosis`), the page reports how often the ensemble agrees with it. If the file overlaps the training data, that agreement is optimistic.
- Blank cells are fine, but a row needs at least 5 measurements to be scored. Rows with too few values, or with invalid or implausible ones, are flagged in a Notes column.
- Limits: 1 MB and 2,000 rows per upload, both configurable (see Configuration). The exported CSV neutralises spreadsheet formulas.

## API

Every field is optional, but at least 5 measurements are needed.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness and model info |
| GET | `/api/schema` | Features, units, ranges, risk bands, sample patients |
| GET | `/api/models` | Cross-validated metrics, ROC curves, feature importance |
| POST | `/api/predict` | `{"inputs": {...}, "explain": true}` |
| POST | `/api/sensitivity` | `{"inputs": {...}, "feature": "sc", "points": 41}` |
| POST | `/api/predict/batch` | Multipart upload, field `file` (CSV) |
| GET | `/api/template.csv` | CSV template for batch uploads |

```bash
curl -X POST http://127.0.0.1:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"age": 52, "sg": 1.015, "al": 2, "hemo": 11.2, "sc": 2.4, "htn": "yes"}}'
```

An abbreviated response (the numbers vary slightly between training runs). Only 6 of 24 measurements were given, so the reliability is low even though the models agree:

```json
{
  "risk": 0.9998,
  "label": "ckd",
  "band": { "key": "high", "label": "High" },
  "votes": { "ckd": 7, "notckd": 0, "total": 7 },
  "models": [{ "key": "logreg", "name": "Logistic regression", "risk": 0.9986, "vote": "ckd" }, "..."],
  "completeness": { "provided": 6, "total": 24, "fraction": 0.25 },
  "reliability": { "level": "low", "summary": "6 of 24 measurements, 7 of 7 models agree" },
  "notes": [{ "level": "warn", "code": "low_completeness", "message": "..." }, "..."],
  "explanation": {
    "baselineRisk": 0.0689,
    "contributions": [{ "key": "hemo", "label": "Hemoglobin", "display": "11.2 g/dL", "delta": 0.2446 }, "..."]
  }
}
```

Errors use one shape: `{"error": {"code": "validation_error", "message": "...", "details": [{"field": "sc", "message": "..."}]}}`.

## Configuration

All settings are environment variables, and all are optional.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CKD_HOST` | `127.0.0.1` | Interface to bind. Patient data is sensitive, so it is local-only by default. |
| `CKD_PORT` | `8000` | Port |
| `CKD_MODEL_DIR` | `models/` | Where trained artifacts are written and read |
| `CKD_DATA_PATH` | `data/kidney_disease.csv` | Training data (same columns as the bundled file) |
| `CKD_AUTO_TRAIN` | `1` | Train automatically when no compatible model exists |
| `CKD_CV_FOLDS`, `CKD_CV_REPEATS` | `5`, `2` | Cross-validation settings |
| `CKD_SEED` | `42` | Random seed |
| `CKD_MAX_UPLOAD_KB` | `1024` | Largest accepted CSV upload |
| `CKD_MAX_BATCH_ROWS` | `2000` | Most rows scored per upload |
| `CKD_LOG_LEVEL` | `INFO` | Logging level |

To retrain explicitly, run `python -m ckdlab.train`. Add `--quick` for a fast run with smaller models, or `--skip-cv` to skip the evaluation.

### Training on your own data

The file needs the same measurement columns as the bundled one and a label column named `classification` (or `class`, `label`, `target`, `diagnosis`) containing `ckd` or `notckd`. An `id` column is ignored.

```powershell
# Windows (PowerShell)
$env:CKD_DATA_PATH = "C:\path\to\file.csv"
python -m ckdlab.train
```

```bash
# macOS / Linux
CKD_DATA_PATH=path/to/file.csv python -m ckdlab.train
```

## Tests

```bash
python -m unittest -v
```

The tests cover value parsing and encoding, data cleaning, predictions, the explanation maths, what-if sweeps, batch scoring, the HTTP API and the first-run behaviour. They train a small model once per run, so the suite takes about ten seconds.

## Docker

```bash
docker build -t ckd-risk-lab .
docker run --rm -p 8000:8000 ckd-risk-lab
```

The image trains the models during the build, so the container starts instantly. It sets `CKD_HOST=0.0.0.0` so the published port is reachable.

## Troubleshooting

- **Port already in use.** Start on another port: `python run.py --port 9000`.
- **The models train again on start-up.** That is expected on the first run, and again after you upgrade scikit-learn, because saved models are tied to the library version that built them. It takes roughly 10 to 30 seconds. With `CKD_AUTO_TRAIN=0` the app stops with a message asking you to run `python -m ckdlab.train` instead.
- **XGBoost will not import or fit.** On Linux it may need the `libgomp1` system package, and an old XGBoost can clash with a new scikit-learn. The app then uses scikit-learn's gradient boosting in its place, so you still get seven models, and the Models page says so. Run `pip install -U xgboost` to switch back.
- **PowerShell will not run `Activate.ps1`.** See the execution-policy note under Quick start.

## Limits

- 400 patients from one published dataset, with many missing values. Treat the numbers as a demonstration of method.
- The typical ranges on the form are general adult reference intervals. Laboratories, age and sex all shift them.
- Reliability is a rule of thumb from completeness, model agreement and training range. It is not a statistical confidence interval.
- The server keeps no record of the values you send. History lives in your browser's local storage and can be cleared from the History page.

## Technologies

- **Backend:** Python, Flask, Waitress
- **Machine learning:** scikit-learn, XGBoost, pandas, NumPy, joblib
- **Frontend:** HTML, CSS and JavaScript ES modules, with hand-written SVG charts and no build step
- **Packaging:** Docker

## Data

The Chronic Kidney Disease dataset from the UCI Machine Learning Repository: 400 patient records, 24 measurements, 250 with CKD and 150 without.

Rubini, L., Soundarapandian, P., & Eswaran, P. (2015). *Chronic Kidney Disease* [Dataset]. UCI Machine Learning Repository. <https://archive.ics.uci.edu/dataset/336/chronic+kidney+disease>. DOI: [10.24432/C5G020](https://doi.org/10.24432/C5G020). The dataset is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Author

**Afhaam Asief Ali Muhammed**

AI/ML Engineer: Reinforcement Learning, Explainable AI & Data Visualization

- [LinkedIn](https://www.linkedin.com/in/muhammed-afhaam-a-23259b240)
- [GitHub](https://github.com/afhaam11)
