"""First-run behaviour: the app trains itself when needed instead of loading a stale pickle."""
import json
import tempfile
import unittest
from pathlib import Path

import sklearn

from ckdlab.service import PredictionService
from ckdlab.train import BUNDLE_NAME, METRICS_NAME, REFERENCE_NAME
from tests.helpers import make_settings


class FirstRun(unittest.TestCase):
    def test_missing_model_without_auto_train_explains_what_to_do(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "python -m ckdlab.train"):
                PredictionService.load(make_settings(model_dir=Path(folder), auto_train=False))

    def test_trains_when_missing_and_retrains_when_scikit_learn_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = make_settings(model_dir=Path(folder), auto_train=True, cv_folds=2, cv_repeats=1)
            service = PredictionService.load(settings)  # nothing on disk yet: trains
            for name in (BUNDLE_NAME, METRICS_NAME, REFERENCE_NAME):
                self.assertTrue((Path(folder) / name).exists(), name)
            self.assertEqual(len(service.members), 7)

            metrics_path = Path(folder) / METRICS_NAME
            metrics = json.loads(metrics_path.read_text())
            metrics["versions"]["scikit-learn"] = "0.0.1"  # pretend it was built with another version
            metrics_path.write_text(json.dumps(metrics))
            PredictionService.load(settings)  # detects the mismatch and retrains
            rebuilt = json.loads(metrics_path.read_text())
            self.assertEqual(rebuilt["versions"]["scikit-learn"], sklearn.__version__)


if __name__ == "__main__":
    unittest.main()
