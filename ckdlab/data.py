"""Dataset loading and cleaning.

``clean_features`` is the one cleaning routine used everywhere: for the training
CSV, for batch uploads, and (value by value) for single predictions. It fixes
the quirks of the public CKD file (stray tabs and spaces, ``?`` placeholders,
``ckd\\t`` labels) and blanks implausible values rather than letting them
distort a model. Nothing here fits on data, so there is no leakage.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .schema import FEATURE_MAP, FEATURES, KEYS, FieldError

TARGET_NAMES = ("classification", "class", "label", "target", "diagnosis")
ID_NAMES = ("id", "patient_id", "patient", "name", "mrn")


@dataclass
class CleanResult:
    X: pd.DataFrame  # one row per input row, columns = schema keys, NaN where missing
    issues: dict[int, list[str]] = field(default_factory=dict)  # row position -> messages
    nulled: int = 0  # cells blanked because they were invalid or implausible
    repaired: int = 0  # cells that had stray whitespace removed
    recognized: list[str] = field(default_factory=list)


def find_column(raw: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {str(c).strip().lower(): c for c in raw.columns}
    for name in names:
        if name in lookup:
            return lookup[name]
    return None


def clean_features(raw: pd.DataFrame) -> CleanResult:
    """Turn a raw frame (any dtype) into a clean numeric feature matrix."""
    lookup = {str(c).strip().lower(): c for c in raw.columns}
    n = len(raw)
    matrix: dict[str, np.ndarray] = {key: np.full(n, np.nan) for key in KEYS}
    issues: dict[int, list[str]] = defaultdict(list)
    nulled = repaired = 0
    recognized: list[str] = []

    for feature in FEATURES:
        source = lookup.get(feature.key)
        if source is None:
            continue
        recognized.append(feature.key)
        column = matrix[feature.key]
        for i, cell in enumerate(raw[source].tolist()):
            if isinstance(cell, str) and cell != cell.strip():
                repaired += 1
            try:
                column[i] = feature.coerce(cell)
            except FieldError as exc:
                issues[i].append(str(exc))
                nulled += 1

    X = pd.DataFrame(matrix, columns=KEYS)
    return CleanResult(X=X, issues=dict(issues), nulled=nulled, repaired=repaired,
                       recognized=recognized)


def parse_labels(values: pd.Series) -> pd.Series:
    """Map 'ckd' / 'notckd' (any case, stray whitespace) to 1 / 0; anything else is NaN."""
    text = values.astype(str).str.strip().str.lower()
    return text.map({"ckd": 1.0, "notckd": 0.0})


def load_training_data(path: Path | str) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    """Read and clean the training CSV. Returns ``(X, y, report)`` with y = 1 for CKD."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Training data not found at {path}. Set CKD_DATA_PATH to its location.")
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    target = find_column(raw, TARGET_NAMES)
    if target is None:
        raise ValueError(f"No label column found. Expected one of: {', '.join(TARGET_NAMES)}.")

    y = parse_labels(raw[target])
    bad = int(y.isna().sum())
    if bad:
        raise ValueError(f"{bad} rows have a label other than 'ckd' or 'notckd'.")

    clean = clean_features(raw)
    y = y.astype(int).reset_index(drop=True)
    X = clean.X
    n = len(X)
    report = {
        "source": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
        "rows": n,
        "features": len(KEYS),
        "class_counts": {"ckd": int((y == 1).sum()), "notckd": int((y == 0).sum())},
        "missing_fraction": {k: round(float(X[k].isna().mean()), 4) for k in KEYS},
        "cells_blanked": clean.nulled,
        "cells_repaired": clean.repaired,
        "complete_rows": int(X.notna().all(axis=1).sum()),
    }
    return X, y, report


def build_reference(X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
    """Statistics about the training data used for explanations and sanity warnings."""
    healthy = X[y == 0]
    baseline: dict[str, float] = {}
    training_range: dict[str, list[float]] = {}
    for feature in FEATURES:
        col = X[feature.key].dropna()
        hcol = healthy[feature.key].dropna()
        if feature.kind == "binary":
            baseline[feature.key] = float(hcol.mode().iloc[0]) if len(hcol) else 0.0
            continue
        baseline[feature.key] = float(hcol.median()) if len(hcol) else float(col.median())
        if feature.kind == "ordinal":
            lo, hi = float(col.min()), float(col.max())
        else:
            p1, p99 = float(col.quantile(0.01)), float(col.quantile(0.99))
            pad = 0.15 * (p99 - p1)
            lo = max(p1 - pad, feature.lo if feature.lo is not None else -np.inf)
            hi = min(p99 + pad, feature.hi if feature.hi is not None else np.inf)
        training_range[feature.key] = [round(lo, 4), round(hi, 4)]
    return {"baseline": baseline, "training_range": training_range}


def describe(key: str) -> str:
    return FEATURE_MAP[key].label
