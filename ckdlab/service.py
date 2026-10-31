"""Prediction service: loads the trained bundle and answers requests.

This module knows nothing about HTTP. ``api.py`` is a thin Flask layer on top,
so the same service can be reused from a notebook, a CLI or another framework.
"""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from . import __version__
from .config import Settings
from .data import ID_NAMES, TARGET_NAMES, clean_features, find_column, parse_labels
from .explain import grid_for, seed_from_inputs, shapley
from .samples import SAMPLES
from .schema import (
    FEATURE_MAP, FEATURES, GROUPS, KEYS, MIN_FIELDS, ValidationError, parse_inputs,
)
from .train import BUNDLE_NAME, METRICS_NAME, REFERENCE_NAME, train

log = logging.getLogger("ckdlab.service")

THRESHOLD = 0.5
BANDS = ((0.0, 0.2, "low", "Low"), (0.2, 0.5, "guarded", "Guarded"),
         (0.5, 0.8, "elevated", "Elevated"), (0.8, 1.0, "high", "High"))
DISCLAIMER = ("For education and research only. This model is not a medical device, does not "
              "provide a diagnosis, and does not replace assessment by a qualified clinician.")


def band_for(risk: float) -> dict[str, str]:
    for _lo, hi, key, label in BANDS:
        if risk < hi:
            return {"key": key, "label": label}
    return {"key": "high", "label": "High"}


def _is_nan(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


class PredictionService:
    def __init__(self, bundle: dict, metrics: dict, reference: dict, settings: Settings):
        self.bundle = bundle
        self.ensemble = bundle["ensemble"]
        self.members: dict[str, Any] = dict(self.ensemble.named_estimators_)
        self.specs = {s["key"]: s for s in bundle["specs"]}
        self.metrics = metrics
        self.reference = reference
        self.settings = settings
        self.baseline: dict[str, float] = reference["baseline"]
        self.training_range: dict[str, list[float]] = reference["training_range"]
        self.importance_rank = [row["key"] for row in metrics.get("importance", [])]
        self.started = time.time()

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, settings: Settings) -> "PredictionService":
        """Load artifacts, training them first when missing or built with another scikit-learn."""
        folder = settings.model_dir
        paths = [folder / name for name in (BUNDLE_NAME, METRICS_NAME, REFERENCE_NAME)]
        reason = None
        if not all(p.exists() for p in paths):
            reason = "no trained model found"
        else:
            built_with = json.loads(paths[1].read_text(encoding="utf-8")).get("versions", {})
            if built_with.get("scikit-learn") != sklearn.__version__:
                reason = (f"model was built with scikit-learn {built_with.get('scikit-learn')}, "
                          f"this environment has {sklearn.__version__}")
        if reason is None:
            try:
                return cls._read(settings, paths)
            except Exception as exc:  # unreadable pickle, missing optional library, ...
                reason = f"saved model could not be loaded ({exc})"

        if not settings.auto_train:
            raise RuntimeError(f"{reason}. Run `python -m ckdlab.train` or set CKD_AUTO_TRAIN=1.")
        log.warning("Training a fresh model: %s. This takes about half a minute.", reason)
        train(settings)
        return cls._read(settings, paths)

    @classmethod
    def _read(cls, settings: Settings, paths: list) -> "PredictionService":
        bundle = joblib.load(paths[0])
        metrics = json.loads(paths[1].read_text(encoding="utf-8"))
        reference = json.loads(paths[2].read_text(encoding="utf-8"))
        return cls(bundle, metrics, reference, settings)

    # ------------------------------------------------------------------ helpers
    def _ensemble_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return np.mean([m.predict_proba(frame)[:, 1] for m in self.members.values()], axis=0)

    # ------------------------------------------------------------------- public
    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "uptimeSeconds": round(time.time() - self.started),
            "model": {
                "trainedAt": self.bundle["trained_at"],
                "members": list(self.members),
                "versions": self.bundle["versions"],
            },
        }

    def schema(self) -> dict[str, Any]:
        features = []
        for feature in FEATURES:
            item = feature.public()
            if feature.key in self.training_range:
                item["trainingRange"] = self.training_range[feature.key]
            features.append(item)
        return {
            "version": __version__,
            "groups": [{"id": g, "label": label, "description": text} for g, label, text in GROUPS],
            "features": features,
            "models": [self.specs[k] for k in self.members],
            "bands": [{"key": key, "label": label, "from": lo, "to": hi} for lo, hi, key, label in BANDS],
            "threshold": THRESHOLD,
            "minFields": MIN_FIELDS,
            "disclaimer": DISCLAIMER,
            "samples": SAMPLES,
        }

    def models_report(self) -> dict[str, Any]:
        return {**self.metrics, "members": [self.specs[k] for k in self.members]}

    def predict(self, raw_inputs: Any, *, explain: bool = True) -> dict[str, Any]:
        started = time.perf_counter()
        values = parse_inputs(raw_inputs)
        frame = pd.DataFrame([values], columns=KEYS)

        member_risk = {k: float(m.predict_proba(frame)[0, 1]) for k, m in self.members.items()}
        risk = float(np.mean(list(member_risk.values())))
        total = len(member_risk)
        votes_ckd = sum(p >= THRESHOLD for p in member_risk.values())
        missing = [k for k in KEYS if _is_nan(values[k])]
        provided = len(KEYS) - len(missing)

        notes, reliability = self._assess(values, missing, votes_ckd, total)
        result: dict[str, Any] = {
            "risk": round(risk, 4),
            "label": "ckd" if risk >= THRESHOLD else "notckd",
            "band": band_for(risk),
            "threshold": THRESHOLD,
            "votes": {"ckd": votes_ckd, "notckd": total - votes_ckd, "total": total},
            "models": [
                {"key": k, "name": self.specs[k]["name"], "risk": round(p, 4),
                 "vote": "ckd" if p >= THRESHOLD else "notckd"}
                for k, p in member_risk.items()
            ],
            "completeness": {"provided": provided, "total": len(KEYS),
                             "fraction": round(provided / len(KEYS), 3), "missing": missing},
            "reliability": reliability,
            "notes": notes,
            "modelVersion": self.bundle["trained_at"],
        }
        if explain:
            result["explanation"] = self._explain(values)
        result["latencyMs"] = round((time.perf_counter() - started) * 1000)
        return result

    def sensitivity(self, raw_inputs: Any, feature_key: str, points: int = 41) -> dict[str, Any]:
        feature = FEATURE_MAP.get(str(feature_key))
        if feature is None:
            raise ValidationError([{"field": "feature", "message": "Unknown measurement."}])
        values = parse_inputs(raw_inputs)
        grid = grid_for(feature, max(5, min(int(points), 101)))
        frame = pd.DataFrame([{**values, feature.key: g} for g in grid], columns=KEYS)
        risk = self._ensemble_proba(frame)
        current_risk = float(self._ensemble_proba(pd.DataFrame([values], columns=KEYS))[0])
        out: dict[str, Any] = {
            "feature": feature.key,
            "kind": feature.kind,
            "grid": grid,
            "risk": [round(float(r), 4) for r in risk],
            "current": {"value": None if _is_nan(values[feature.key]) else values[feature.key],
                        "risk": round(current_risk, 4)},
        }
        if feature.kind == "binary":
            out["labels"] = [label for _value, label in feature.options]
        elif feature.kind == "ordinal":
            out["labels"] = [label for _value, label in feature.levels]
        return out

    def predict_batch(self, raw: pd.DataFrame) -> dict[str, Any]:
        if len(raw) == 0:
            raise ValidationError([{"field": "file", "message": "The file has no rows."}])
        if len(raw) > self.settings.max_batch_rows:
            raise ValidationError([{"field": "file",
                                    "message": f"Too many rows ({len(raw)}). The limit is "
                                               f"{self.settings.max_batch_rows}."}])
        clean = clean_features(raw)
        if not clean.recognized:
            raise ValidationError([{"field": "file",
                                    "message": "No recognised columns. Use column names such as "
                                               + ", ".join(KEYS[:6]) + "... (download the template)."}])

        X = clean.X
        matrix = np.column_stack([m.predict_proba(X)[:, 1] for m in self.members.values()])
        risk = matrix.mean(axis=1)
        votes = (matrix >= THRESHOLD).sum(axis=1)
        provided = X.notna().sum(axis=1).to_numpy()

        id_col = find_column(raw, ID_NAMES)
        label_col = find_column(raw, TARGET_NAMES)
        truth = parse_labels(raw[label_col]) if label_col else None

        rows: list[dict[str, Any]] = []
        for i in range(len(raw)):
            issues = list(clean.issues.get(i, []))
            scored = provided[i] >= MIN_FIELDS
            if not scored:
                issues.append(f"Only {int(provided[i])} measurements; at least {MIN_FIELDS} are needed.")
            row: dict[str, Any] = {
                "row": i + 1,
                "id": str(raw[id_col].iloc[i]).strip()[:64] if id_col else None,
                "provided": int(provided[i]),
                "risk": round(float(risk[i]), 4) if scored else None,
                "label": ("ckd" if risk[i] >= THRESHOLD else "notckd") if scored else None,
                "band": band_for(float(risk[i]))["key"] if scored else None,
                "votesCkd": int(votes[i]) if scored else None,
                "issues": issues,
            }
            if truth is not None:
                t = truth.iloc[i]
                row["reference"] = None if pd.isna(t) else ("ckd" if t == 1 else "notckd")
            rows.append(row)

        scored_rows = [r for r in rows if r["risk"] is not None]
        known = {id_col, label_col} - {None}
        summary: dict[str, Any] = {
            "rows": len(rows),
            "scored": len(scored_rows),
            "skipped": len(rows) - len(scored_rows),
            "flaggedCkd": sum(r["label"] == "ckd" for r in scored_rows),
            "meanRisk": round(float(np.mean([r["risk"] for r in scored_rows])), 4) if scored_rows else None,
            "withIssues": sum(bool(r["issues"]) for r in rows),
            "columnsUsed": clean.recognized,
            "columnsIgnored": [str(c) for c in raw.columns
                               if str(c).strip().lower() not in KEYS and c not in known],
            "members": total_members(self.members),
        }
        if truth is not None:
            compared = [r for r in scored_rows if r.get("reference")]
            summary["agreement"] = {
                "compared": len(compared),
                "matches": sum(r["reference"] == r["label"] for r in compared),
            }
        return {"summary": summary, "rows": rows}

    # ---------------------------------------------------------------- internals
    def _explain(self, values: dict[str, float]) -> dict[str, Any]:
        phi, start, final = shapley(self._ensemble_proba, values, self.baseline,
                                    n_perm=32, seed=seed_from_inputs(values))
        contributions = []
        for key, delta in zip(KEYS, phi):
            if _is_nan(values[key]):
                continue
            feature = FEATURE_MAP[key]
            contributions.append({"key": key, "label": feature.label,
                                  "display": feature.display(values[key]),
                                  "delta": round(float(delta), 4)})
        contributions.sort(key=lambda c: -abs(c["delta"]))
        return {
            "method": "Shapley values against a typical healthy profile",
            "baselineRisk": round(start, 4),
            "risk": round(final, 4),
            "contributions": contributions,
        }

    def _assess(self, values: dict[str, float], missing: list[str], votes_ckd: int,
                total: int) -> tuple[list[dict[str, Any]], dict[str, str]]:
        notes: list[dict[str, Any]] = []
        provided = len(KEYS) - len(missing)
        completeness = provided / len(KEYS)

        if provided < 12:
            notes.append({"level": "warn", "code": "low_completeness", "features": [],
                          "message": f"Only {provided} of {len(KEYS)} measurements were provided. Blank "
                                     "values are filled with typical values from the training data, so "
                                     "treat this estimate with caution."})
        top_missing = [k for k in self.importance_rank[:6] if k in missing]
        if top_missing:
            names = ", ".join(FEATURE_MAP[k].label.lower() for k in top_missing)
            notes.append({"level": "info", "code": "influential_missing", "features": top_missing,
                          "message": f"These influential measurements are blank: {names}. "
                                     "Adding them would sharpen the estimate."})

        outside: list[str] = []
        for key, (lo, hi) in self.training_range.items():
            value = values[key]
            if _is_nan(value) or not (value < lo or value > hi):
                continue
            outside.append(key)
            feature = FEATURE_MAP[key]
            notes.append({"level": "warn", "code": "outside_training_range", "features": [key],
                          "message": f"{feature.label} of {feature.display(value)} is outside the range "
                                     f"seen in training ({lo:g} to {hi:g}), so the estimate extrapolates."})

        majority = max(votes_ckd, total - votes_ckd)
        agreement = majority / total
        if agreement < 0.75:
            notes.append({"level": "warn", "code": "models_disagree", "features": [],
                          "message": f"The models split {votes_ckd} to {total - votes_ckd}. This patient "
                                     "sits close to the decision boundary."})

        if completeness < 0.4 or agreement < 0.6:
            level = "low"
        elif completeness >= 0.7 and agreement >= 0.85 and not outside:
            level = "high"
        else:
            level = "moderate"
        summary = f"{provided} of {len(KEYS)} measurements, {majority} of {total} models agree"
        if outside:
            summary += f", {len(outside)} outside the training range"
        return notes, {"level": level, "summary": summary}


def total_members(members: dict[str, Any]) -> int:
    return len(members)
