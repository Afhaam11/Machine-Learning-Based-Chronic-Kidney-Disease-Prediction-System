"""Model zoo, preprocessing and the voting ensemble.

Improvements over the notebook:

* Imputation and scaling live *inside* each scikit-learn ``Pipeline``. The
  notebook imputed the whole dataset before splitting, which leaks test-set
  statistics into training.
* Distance-based models (KNN, SVM, logistic regression) see scaled features.
* The ensemble votes on probabilities (soft voting) so the app can report a
  risk percentage, not just a class. The hard-vote tally is still reported.
* Every model is smoke-tested before use. A model that cannot fit in the
  current environment is dropped with a warning instead of breaking training.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from .schema import BINARY_KEYS, NUMERIC_KEYS

log = logging.getLogger("ckdlab.modeling")


def build_preprocessor() -> ColumnTransformer:
    """Median-impute and scale numeric columns; mode-impute the 0/1 columns."""
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    return ColumnTransformer(
        [("numeric", numeric, NUMERIC_KEYS),
         ("binary", SimpleImputer(strategy="most_frequent"), BINARY_KEYS)],
        verbose_feature_names_out=False,
    )


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    family: str
    blurb: str
    factory: Callable[[], BaseEstimator]
    fallback_for: str | None = None  # used only if the model with this key cannot run

    def build(self) -> Pipeline:
        return Pipeline([("prep", build_preprocessor()), ("model", self.factory())])

    def public(self) -> dict[str, str]:
        return {"key": self.key, "name": self.name, "family": self.family, "blurb": self.blurb}


def _xgboost_factory(seed: int, quick: bool) -> Callable[[], BaseEstimator] | None:
    try:
        from xgboost import XGBClassifier  # noqa: WPS433 (optional dependency)
    except Exception as exc:  # ImportError, or a broken native library
        log.warning("XGBoost is unavailable (%s); using scikit-learn gradient boosting instead.", exc)
        return None

    def make() -> BaseEstimator:
        return XGBClassifier(
            n_estimators=80 if quick else 250, max_depth=3, learning_rate=0.08, subsample=0.9,
            colsample_bytree=0.9, eval_metric="logloss", random_state=seed, n_jobs=1, verbosity=0,
        )

    return make


def model_specs(seed: int = 42, quick: bool = False) -> list[ModelSpec]:
    """The seven classifiers from the original project, in the original order.

    scikit-learn's gradient boosting is listed as a fallback for XGBoost. ``smoke_test`` keeps it only
    when XGBoost is missing or cannot fit in this environment, so the ensemble always has seven members.
    """
    boosted = _xgboost_factory(seed, quick)
    blurb = "Builds trees one after another, each one correcting the mistakes of the last."
    boosting: list[ModelSpec] = []
    if boosted is not None:
        boosting.append(ModelSpec("xgboost", "XGBoost", "Boosted trees", blurb, boosted))
    boosting.append(ModelSpec(
        "gboost", "Gradient boosting", "Boosted trees", blurb,
        lambda: GradientBoostingClassifier(n_estimators=60 if quick else 150, max_depth=3, learning_rate=0.1,
                                           subsample=0.9, random_state=seed),
        fallback_for="xgboost"))

    return [
        ModelSpec("logreg", "Logistic regression", "Linear",
                  "Weighs each measurement and adds the evidence up.",
                  lambda: LogisticRegression(C=1.0, max_iter=2000, random_state=seed)),
        ModelSpec("tree", "Decision tree", "Tree",
                  "Asks a chain of yes/no questions about the measurements.",
                  lambda: DecisionTreeClassifier(max_depth=5, min_samples_leaf=3, random_state=seed)),
        ModelSpec("forest", "Random forest", "Tree ensemble",
                  "Averages many decision trees, each trained on a different slice of the data.",
                  lambda: RandomForestClassifier(n_estimators=60 if quick else 300, min_samples_leaf=2,
                                                 random_state=seed, n_jobs=1)),
        *boosting,
        ModelSpec("knn", "K-nearest neighbors", "Instance based",
                  "Compares the patient with the most similar patients in the training data.",
                  lambda: KNeighborsClassifier(n_neighbors=7, weights="distance")),
        ModelSpec("svm", "Support vector machine", "Kernel",
                  "Finds the boundary that best separates CKD from non-CKD patients.",
                  lambda: SVC(C=1.0, kernel="rbf", probability=True, random_state=seed)),
        ModelSpec("bayes", "Gaussian naive Bayes", "Probabilistic",
                  "Combines how typical each value is for each group, treating values as independent.",
                  lambda: GaussianNB()),
    ]


def smoke_test(specs: list[ModelSpec], X: pd.DataFrame, y: pd.Series) -> list[ModelSpec]:
    """Keep only the specs that can fit and predict here; fallbacks stand in for failed primaries."""
    n = min(len(X), 80)
    idx = np.concatenate([np.flatnonzero(y.to_numpy() == c)[: n // 2] for c in (0, 1)])
    Xs, ys = X.iloc[idx], y.iloc[idx]
    works: dict[str, bool] = {}
    for spec in specs:
        try:
            proba = spec.build().fit(Xs, ys).predict_proba(Xs.iloc[:5])
            if proba.shape != (5, 2) or not np.isfinite(proba).all():
                raise ValueError("unexpected predict_proba output")
            works[spec.key] = True
        except Exception as exc:
            log.warning("Dropping %s: %s", spec.name, exc)
            works[spec.key] = False
    healthy = [s for s in specs if works[s.key] and not (s.fallback_for and works.get(s.fallback_for))]
    if not healthy:
        raise RuntimeError("None of the models could be trained in this environment.")
    return healthy


def make_ensemble(specs: list[ModelSpec]) -> VotingClassifier:
    return VotingClassifier([(s.key, s.build()) for s in specs], voting="soft")


def clone_pipeline(pipeline: Pipeline) -> Pipeline:
    return clone(pipeline)
