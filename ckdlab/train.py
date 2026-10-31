"""Train the ensemble and write the artifacts the API serves.

    python -m ckdlab.train            # full run: cross-validation + final fit
    python -m ckdlab.train --quick    # smaller models, 3 folds (used by the tests)
    python -m ckdlab.train --skip-cv  # fit only, no evaluation
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from .config import Settings
from .data import build_reference, load_training_data
from .evaluate import cross_validate, summarize
from .modeling import make_ensemble, model_specs, smoke_test
from .schema import FEATURE_MAP, KEYS

log = logging.getLogger("ckdlab.train")

BUNDLE_NAME = "ckd_ensemble.joblib"
METRICS_NAME = "metrics.json"
REFERENCE_NAME = "reference.json"


def library_versions() -> dict[str, str | None]:
    try:
        import xgboost  # noqa: WPS433

        xgb_version: str | None = xgboost.__version__
    except Exception:
        xgb_version = None
    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "xgboost": xgb_version,
    }


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def train(settings: Settings, *, quick: bool = False, skip_cv: bool = False) -> dict[str, Any]:
    started = time.time()
    X, y, report = load_training_data(settings.data_path)
    log.info("Loaded %d patients (%d CKD, %d not CKD); %d implausible cells blanked, %d repaired.",
             report["rows"], report["class_counts"]["ckd"], report["class_counts"]["notckd"],
             report["cells_blanked"], report["cells_repaired"])

    specs = smoke_test(model_specs(settings.seed, quick), X, y)
    log.info("Models: %s", ", ".join(s.name for s in specs))
    reference = build_reference(X, y)

    folds = 3 if quick else settings.cv_folds
    repeats = 1 if quick else settings.cv_repeats
    models_report: list[dict[str, Any]] = []
    importance: list[dict[str, Any]] = []
    evaluation: dict[str, Any] | None = None

    if not skip_cv:
        log.info("Cross-validating (%d folds x %d repeat%s)...", folds, repeats, "" if repeats == 1 else "s")
        cv = cross_validate(X, y, specs, n_splits=folds, n_repeats=repeats, seed=settings.seed,
                            importance_repeats=2 if quick else 3)
        labels = y.to_numpy()
        for spec in specs:
            models_report.append({**spec.public(), "is_ensemble": False,
                                  **summarize(labels, cv["oof"][spec.key], cv["folds"][spec.key])})
        models_report.append({
            "key": "ensemble", "name": "Voting ensemble", "family": "Soft vote",
            "blurb": "Averages the risk from every model above.", "is_ensemble": True,
            **summarize(labels, cv["oof_ensemble"], cv["folds"]["ensemble"]),
        })
        gains = np.clip(cv["importance"], 0, None)
        top = float(gains.max()) or 1.0
        importance = sorted(
            ({"key": k, "label": FEATURE_MAP[k].label, "importance": round(float(g), 5),
              "relative": round(float(g) / top, 4)} for k, g in zip(KEYS, gains)),
            key=lambda row: -row["importance"],
        )
        evaluation = {
            "method": "Stratified k-fold cross-validation",
            "folds": folds,
            "repeats": repeats,
            "threshold": 0.5,
            "positive_class": "CKD",
            "note": ("Every patient is scored by models that never saw that patient. Imputation "
                     "and scaling are re-fitted inside each fold, so nothing leaks."),
        }

    log.info("Fitting the final ensemble on all %d patients...", len(X))
    ensemble = make_ensemble(specs).fit(X, y)

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    versions = library_versions()
    bundle = {
        "format": 1,
        "ensemble": ensemble,
        "specs": [s.public() for s in specs],
        "trained_at": trained_at,
        "versions": versions,
        "seed": settings.seed,
        "quick": quick,
    }
    metrics = {
        "generated_at": trained_at,
        "evaluation": evaluation,
        "dataset": report,
        "models": models_report,
        "importance": importance,
        "versions": versions,
        "seconds": round(time.time() - started, 1),
    }
    ref_payload = {**reference, "dataset": report, "trained_at": trained_at}

    settings.model_dir.mkdir(parents=True, exist_ok=True)
    tmp = settings.model_dir / (BUNDLE_NAME + ".tmp")
    joblib.dump(bundle, tmp, compress=3)
    os.replace(tmp, settings.model_dir / BUNDLE_NAME)
    _atomic_json(settings.model_dir / METRICS_NAME, metrics)
    _atomic_json(settings.model_dir / REFERENCE_NAME, ref_payload)
    log.info("Saved model and reports to %s in %.1fs.", settings.model_dir, time.time() - started)
    return metrics


def _print_table(metrics: dict[str, Any]) -> None:
    rows = metrics["models"]
    if not rows:
        return
    print(f"\n{'Model':<26}{'Accuracy':>9}{'Precision':>10}{'Recall':>8}{'F1':>7}{'ROC AUC':>9}")
    for r in rows:
        mark = "*" if r["is_ensemble"] else " "
        print(f"{mark}{r['name']:<25}{r['accuracy']:>9.3f}{r['precision']:>10.3f}"
              f"{r['recall']:>8.3f}{r['f1']:>7.3f}{r['roc_auc']:>9.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the CKD risk ensemble.")
    parser.add_argument("--quick", action="store_true", help="smaller models and 3 folds")
    parser.add_argument("--skip-cv", action="store_true", help="fit only, skip evaluation")
    args = parser.parse_args()
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    _print_table(train(settings, quick=args.quick, skip_cv=args.skip_cv))


if __name__ == "__main__":
    main()
