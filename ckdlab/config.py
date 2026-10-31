"""Runtime settings, read from environment variables so nothing is hard-coded."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_path: Path
    model_dir: Path
    host: str
    port: int
    auto_train: bool
    cv_folds: int
    cv_repeats: int
    seed: int
    max_upload_kb: int
    max_batch_rows: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_path=Path(os.getenv("CKD_DATA_PATH", ROOT / "data" / "kidney_disease.csv")),
            model_dir=Path(os.getenv("CKD_MODEL_DIR", ROOT / "models")),
            host=os.getenv("CKD_HOST", "127.0.0.1"),
            port=_env_int("CKD_PORT", 8000),
            auto_train=_env_bool("CKD_AUTO_TRAIN", True),
            cv_folds=_env_int("CKD_CV_FOLDS", 5),
            cv_repeats=_env_int("CKD_CV_REPEATS", 2),
            seed=_env_int("CKD_SEED", 42),
            max_upload_kb=_env_int("CKD_MAX_UPLOAD_KB", 1024),
            max_batch_rows=_env_int("CKD_MAX_BATCH_ROWS", 2000),
            log_level=os.getenv("CKD_LOG_LEVEL", "INFO").upper(),
        )
