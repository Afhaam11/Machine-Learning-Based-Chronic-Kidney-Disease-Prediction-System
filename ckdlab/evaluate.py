"""Honest evaluation.

Every patient is scored by models that never saw that patient (stratified
k-fold, optionally repeated). Preprocessing is part of each pipeline, so it is
re-fitted inside every fold. The ensemble's out-of-fold probability is the mean
of its members' out-of-fold probabilities, which is exactly what soft voting
does.
"""
from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import StratifiedKFold

from .modeling import ModelSpec
from .schema import KEYS

log = logging.getLogger("ckdlab.evaluate")


def log_loss_clipped(y: np.ndarray, p: np.ndarray, eps: float = 1e-3) -> float:
    p = np.clip(p, eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _permutation_importance(
    predict: Callable[[pd.DataFrame], np.ndarray],
    X: pd.DataFrame,
    y: np.ndarray,
    repeats: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Increase in log loss when one column is shuffled (all variants scored in one batch)."""
    blocks = [X]
    for key in KEYS:
        for _ in range(repeats):
            shuffled = X.copy()
            shuffled[key] = rng.permutation(shuffled[key].to_numpy())
            blocks.append(shuffled)
    proba = predict(pd.concat(blocks, ignore_index=True))
    n = len(X)
    base = log_loss_clipped(y, proba[:n])
    gains = np.zeros(len(KEYS))
    for i in range(len(KEYS)):
        for r in range(repeats):
            start = n * (1 + i * repeats + r)
            gains[i] += log_loss_clipped(y, proba[start:start + n]) - base
    return gains / repeats


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    specs: list[ModelSpec],
    *,
    n_splits: int,
    n_repeats: int,
    seed: int,
    importance_repeats: int = 3,
) -> dict:
    keys = [s.key for s in specs]
    labels = y.to_numpy()
    n = len(labels)
    oof = {k: np.zeros(n) for k in keys}
    oof_ens = np.zeros(n)
    folds: dict[str, dict[str, list[float]]] = {
        k: {"accuracy": [], "roc_auc": [], "f1": []} for k in keys + ["ensemble"]
    }
    importance = np.zeros(len(KEYS))
    rng = np.random.default_rng(seed)
    total = n_splits * n_repeats
    done = 0

    for rep in range(n_repeats):
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed + rep)
        for train_idx, test_idx in splitter.split(X, labels):
            X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
            y_tr, y_te = labels[train_idx], labels[test_idx]
            fitted = {s.key: s.build().fit(X_tr, y_tr) for s in specs}
            probs = {k: m.predict_proba(X_te)[:, 1] for k, m in fitted.items()}
            ens = np.mean(list(probs.values()), axis=0)

            for k, p in {**probs, "ensemble": ens}.items():
                folds[k]["accuracy"].append(float(accuracy_score(y_te, p >= 0.5)))
                folds[k]["f1"].append(float(f1_score(y_te, p >= 0.5, zero_division=0)))
                folds[k]["roc_auc"].append(float(roc_auc_score(y_te, p)))
            for k in keys:
                oof[k][test_idx] += probs[k] / n_repeats
            oof_ens[test_idx] += ens / n_repeats

            def predict(frame: pd.DataFrame, _fitted=fitted) -> np.ndarray:
                return np.mean([m.predict_proba(frame)[:, 1] for m in _fitted.values()], axis=0)

            importance += _permutation_importance(predict, X_te, y_te, importance_repeats, rng)
            done += 1
            log.info("  fold %d/%d done", done, total)

    return {"oof": oof, "oof_ensemble": oof_ens, "folds": folds, "importance": importance / total}


def _downsample(fpr: np.ndarray, tpr: np.ndarray, limit: int = 80) -> dict[str, list[float]]:
    if len(fpr) > limit:
        keep = np.unique(np.linspace(0, len(fpr) - 1, limit).round().astype(int))
        fpr, tpr = fpr[keep], tpr[keep]
    return {"fpr": [round(float(v), 4) for v in fpr], "tpr": [round(float(v), 4) for v in tpr]}


def summarize(y: np.ndarray, p: np.ndarray, fold_scores: dict[str, list[float]] | None = None) -> dict:
    pred = p >= 0.5
    tn, fp, fn, tp = (int(v) for v in confusion_matrix(y, pred, labels=[0, 1]).ravel())
    fpr, tpr, _ = roc_curve(y, p)
    out = {
        "accuracy": float(accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0,
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": log_loss_clipped(y, p),
        "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "roc": _downsample(fpr, tpr),
    }
    out = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()}
    if fold_scores:
        out["accuracy_std"] = round(float(np.std(fold_scores["accuracy"])), 4)
        out["roc_auc_std"] = round(float(np.std(fold_scores["roc_auc"])), 4)
    return out
