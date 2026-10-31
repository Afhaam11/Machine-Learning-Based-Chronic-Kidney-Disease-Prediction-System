"""Shared test fixtures: train one small model per test run and reuse it."""
from __future__ import annotations

import atexit
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from ckdlab.config import ROOT, Settings
from ckdlab.service import PredictionService
from ckdlab.train import train

DATA = ROOT / "data" / "kidney_disease.csv"
_service: PredictionService | None = None
_settings: Settings | None = None


def make_settings(**overrides) -> Settings:
    return replace(Settings.from_env(), **{"data_path": DATA, "auto_train": False, **overrides})


def shared_service() -> tuple[PredictionService, Settings]:
    """A quickly trained service (smaller models, 3-fold CV), built once for the whole run."""
    global _service, _settings
    if _service is None:
        folder = Path(tempfile.mkdtemp(prefix="ckd-tests-"))
        atexit.register(shutil.rmtree, folder, ignore_errors=True)
        _settings = make_settings(model_dir=folder)
        train(_settings, quick=True)
        _service = PredictionService.load(_settings)
    return _service, _settings
