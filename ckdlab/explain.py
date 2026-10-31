"""Model-agnostic explanations with no extra dependencies.

Contributions are Shapley values estimated by walking from a *healthy reference
profile* to the patient's values, one measurement at a time, over many random
orderings (plus their reverses to cut variance). Averaging the marginal change
in risk at each step gives every measurement a fair share of the credit, even
when measurements are correlated or the risk is already saturated near 0 or 1,
where one-at-a-time ablation would show nothing.

The contributions add up exactly to ``risk(patient) - risk(reference)``.
Measurements the user left blank are held blank on both sides of the walk, so
they get no credit and no blame.
"""
from __future__ import annotations

import json
import zlib
from typing import Callable

import numpy as np
import pandas as pd

from .schema import KEYS, Feature

Predict = Callable[[pd.DataFrame], np.ndarray]


def seed_from_inputs(values: dict[str, float]) -> int:
    """Deterministic seed so the same patient always gets the same explanation."""
    payload = json.dumps(
        {k: (None if np.isnan(v) else round(float(v), 6)) for k, v in sorted(values.items())}
    )
    return zlib.crc32(payload.encode())


def shapley(
    predict: Predict,
    values: dict[str, float],
    baseline: dict[str, float],
    *,
    n_perm: int = 32,
    seed: int = 0,
) -> tuple[np.ndarray, float, float]:
    """Return ``(phi, risk_at_reference, risk_at_patient)``; ``phi`` is aligned with ``KEYS``."""
    x = np.array([values[k] for k in KEYS], dtype=float)
    start = np.array([baseline[k] for k in KEYS], dtype=float)
    start[np.isnan(x)] = np.nan  # blank stays blank on both sides
    provided = np.flatnonzero(~np.isnan(x))
    m = len(provided)

    rng = np.random.default_rng(seed)
    orders = np.stack([rng.permutation(provided) for _ in range(n_perm)])
    orders = np.concatenate([orders, orders[:, ::-1]])  # antithetic pairs
    walks = len(orders)

    rows = np.empty((walks, m, len(KEYS)))
    for w, order in enumerate(orders):
        current = start.copy()
        for step, j in enumerate(order):
            current[j] = x[j]
            rows[w, step] = current

    p_start = float(predict(pd.DataFrame([start], columns=KEYS))[0])
    probs = predict(pd.DataFrame(rows.reshape(walks * m, len(KEYS)), columns=KEYS)).reshape(walks, m)
    previous = np.concatenate([np.full((walks, 1), p_start), probs[:, :-1]], axis=1)

    phi = np.zeros(len(KEYS))
    np.add.at(phi, orders.ravel(), (probs - previous).ravel())
    return phi / walks, p_start, float(probs[0, -1])


def grid_for(feature: Feature, points: int = 41) -> list[float]:
    """Values to sweep for a what-if curve."""
    if feature.kind == "binary":
        return [0.0, 1.0]
    if feature.kind == "ordinal":
        return [float(v) for v, _ in feature.levels]
    lo, hi = float(feature.ui_lo), float(feature.ui_hi)
    grid = np.geomspace(lo, hi, points) if feature.scale == "log" else np.linspace(lo, hi, points)
    return [round(float(v), feature.decimals + 1) for v in grid]
