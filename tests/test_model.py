import json
import math
import unittest

import numpy as np
import pandas as pd

from ckdlab.schema import KEYS, ValidationError, parse_inputs
from ckdlab.service import THRESHOLD
from tests.helpers import shared_service


def sample(service, sample_id):
    return next(s for s in service.schema()["samples"] if s["id"] == sample_id)["inputs"]


class Predictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, _ = shared_service()

    def test_samples_land_where_a_reader_would_expect(self):
        typical = self.service.predict(sample(self.service, "typical"))
        advanced = self.service.predict(sample(self.service, "advanced"))
        mixed = self.service.predict(sample(self.service, "mixed"))
        self.assertLess(typical["risk"], 0.2)
        self.assertEqual(typical["band"]["key"], "low")
        self.assertGreater(advanced["risk"], 0.8)
        self.assertEqual(advanced["label"], "ckd")
        self.assertTrue(0.05 < mixed["risk"] < 0.95)  # deliberately ambiguous (XGBoost may shift it)

    def test_ensemble_is_the_mean_of_its_members_and_matches_voting_classifier(self):
        values = parse_inputs(sample(self.service, "mixed"))
        frame = pd.DataFrame([values], columns=KEYS)
        result = self.service.predict(sample(self.service, "mixed"), explain=False)
        mean = float(np.mean([m["risk"] for m in result["models"]]))
        self.assertAlmostEqual(result["risk"], mean, places=3)
        self.assertAlmostEqual(result["risk"], float(self.service.ensemble.predict_proba(frame)[0, 1]), places=3)
        self.assertEqual(result["votes"]["total"], len(result["models"]))
        self.assertEqual(result["votes"]["ckd"], sum(m["risk"] >= THRESHOLD for m in result["models"]))

    def test_all_probabilities_are_valid(self):
        for sample_id in ("typical", "mixed", "advanced"):
            result = self.service.predict(sample(self.service, sample_id))
            self.assertTrue(0 <= result["risk"] <= 1)
            self.assertTrue(all(0 <= m["risk"] <= 1 for m in result["models"]))

    def test_seven_models_are_in_the_ensemble(self):
        self.assertEqual(len(self.service.members), 7)
        names = [m["name"] for m in self.service.predict(sample(self.service, "typical"), explain=False)["models"]]
        self.assertIn("Random forest", names)

    def test_worse_kidney_markers_do_not_lower_the_risk(self):
        base = dict(sample(self.service, "mixed"))
        worse = {**base, "sc": 6.0, "bu": 110, "hemo": 8.5, "al": 4}
        self.assertGreater(self.service.predict(worse, explain=False)["risk"],
                           self.service.predict(base, explain=False)["risk"])

    def test_works_with_the_minimum_number_of_fields(self):
        result = self.service.predict({"age": 50, "bp": 80, "sg": 1.01, "al": 3, "hemo": 9})
        self.assertEqual(result["completeness"]["provided"], 5)
        self.assertEqual(result["reliability"]["level"], "low")
        self.assertTrue(any(n["code"] == "low_completeness" for n in result["notes"]))

    def test_out_of_training_range_values_are_flagged(self):
        result = self.service.predict({**sample(self.service, "typical"), "sg": 1.045})
        self.assertTrue(any(n["code"] == "outside_training_range" and n["features"] == ["sg"] for n in result["notes"]))

    def test_invalid_input_raises(self):
        with self.assertRaises(ValidationError):
            self.service.predict({"age": 40})


class Explanations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, _ = shared_service()

    def test_contributions_add_up_to_the_total_shift(self):
        result = self.service.predict(sample(self.service, "advanced"))
        ex = result["explanation"]
        self.assertAlmostEqual(sum(c["delta"] for c in ex["contributions"]), result["risk"] - ex["baselineRisk"], delta=0.005)
        self.assertLess(ex["baselineRisk"], 0.2)

    def test_explanations_are_deterministic_and_sorted(self):
        a = self.service.predict(sample(self.service, "mixed"))["explanation"]["contributions"]
        b = self.service.predict(sample(self.service, "mixed"))["explanation"]["contributions"]
        self.assertEqual(a, b)
        sizes = [abs(c["delta"]) for c in a]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_blank_measurements_get_no_credit(self):
        inputs = {k: v for k, v in sample(self.service, "advanced").items() if k in ("age", "bp", "sg", "al", "hemo", "htn")}
        keys = {c["key"] for c in self.service.predict(inputs)["explanation"]["contributions"]}
        self.assertEqual(keys, set(inputs))

    def test_the_decisive_measurement_gets_the_most_credit(self):
        # Take a typical patient and change only the urine specific gravity and albumin.
        inputs = {**sample(self.service, "typical"), "sg": 1.005, "al": 4}
        top = self.service.predict(inputs)["explanation"]["contributions"][:2]
        self.assertTrue({"sg", "al"} & {c["key"] for c in top})


class WhatIf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, _ = shared_service()
        cls.inputs = sample(cls.service, "mixed")

    def test_numeric_sweep(self):
        out = self.service.sensitivity(self.inputs, "bp", points=21)
        self.assertEqual(len(out["grid"]), 21)
        self.assertEqual(len(out["risk"]), 21)
        self.assertEqual(out["grid"], sorted(out["grid"]))
        self.assertTrue(all(0 <= r <= 1 for r in out["risk"]))
        self.assertEqual(out["current"]["value"], 90.0)

    def test_log_scale_feature_is_geometric(self):
        # Serum creatinine spans 0.3 to 15 mg/dL, so the sweep is spaced geometrically, not evenly.
        grid = self.service.sensitivity(self.inputs, "sc", points=31)["grid"]
        self.assertEqual(grid, sorted(grid))
        self.assertAlmostEqual(grid[0], 0.3, places=2)
        self.assertAlmostEqual(grid[-1], 15.0, places=2)
        self.assertAlmostEqual(grid[len(grid) // 2], (0.3 * 15) ** 0.5, delta=0.1)  # geometric mean, not 7.65

    def test_discrete_features(self):
        binary = self.service.sensitivity(self.inputs, "htn")
        self.assertEqual(binary["labels"], ["No", "Yes"])
        self.assertEqual(len(binary["risk"]), 2)
        self.assertLess(binary["risk"][0], binary["risk"][1])  # hypertension raises the risk here
        ordinal = self.service.sensitivity(self.inputs, "al")
        self.assertEqual(ordinal["labels"], ["0", "1", "2", "3", "4", "5"])

    def test_unknown_feature(self):
        with self.assertRaises(ValidationError):
            self.service.sensitivity(self.inputs, "nope")


class Batch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, _ = shared_service()

    def test_scores_rows_and_reports_problems(self):
        raw = pd.DataFrame({
            "id": ["a", "b", "c"], "age": ["50", "40", "30"], "bp": ["80", "70", "?"], "sg": ["1.01", "1.02", ""],
            "al": ["3", "0", ""], "hemo": ["9", "15", ""], "sod": ["4.5", "140", ""], "classification": ["ckd", "notckd", "ckd"],
        })
        out = self.service.predict_batch(raw)
        rows = out["rows"]
        self.assertEqual([r["id"] for r in rows], ["a", "b", "c"])
        self.assertEqual(out["summary"]["scored"], 2)
        self.assertEqual(out["summary"]["skipped"], 1)
        self.assertIsNone(rows[2]["risk"])
        self.assertTrue(any("Sodium" in issue for issue in rows[0]["issues"]))
        self.assertGreater(rows[0]["risk"], rows[1]["risk"])
        self.assertEqual(out["summary"]["agreement"], {"compared": 2, "matches": 2})
        json.dumps(out, allow_nan=False)

    def test_rejects_empty_and_unrecognised_files(self):
        with self.assertRaises(ValidationError):
            self.service.predict_batch(pd.DataFrame({"age": []}))
        with self.assertRaisesRegex(ValidationError, "recognised"):
            self.service.predict_batch(pd.DataFrame({"foo": [1]}))

    def test_row_limit(self):
        limit = self.service.settings.max_batch_rows
        with self.assertRaisesRegex(ValidationError, "Too many rows"):
            self.service.predict_batch(pd.DataFrame({"age": ["40"] * (limit + 1)}))


class ModelZoo(unittest.TestCase):
    def test_fallback_replaces_a_model_that_cannot_fit(self):
        from sklearn.base import BaseEstimator, ClassifierMixin
        from sklearn.naive_bayes import GaussianNB
        from ckdlab.data import load_training_data
        from ckdlab.modeling import ModelSpec, smoke_test
        from tests.helpers import DATA

        class Broken(ClassifierMixin, BaseEstimator):
            def fit(self, X, y):
                raise RuntimeError("incompatible library version")

        X, y, _ = load_training_data(DATA)
        primary = ModelSpec("fancy", "Fancy", "x", "x", Broken)
        fallback = ModelSpec("plain", "Plain", "x", "x", GaussianNB, fallback_for="fancy")
        steady = ModelSpec("steady", "Steady", "x", "x", GaussianNB)
        self.assertEqual([s.key for s in smoke_test([steady, primary, fallback], X, y)], ["steady", "plain"])
        # when the primary works, the fallback is not used
        working = ModelSpec("fancy", "Fancy", "x", "x", GaussianNB)
        self.assertEqual([s.key for s in smoke_test([steady, working, fallback], X, y)], ["steady", "fancy"])

    def test_the_real_zoo_always_yields_seven_models(self):
        from ckdlab.data import load_training_data
        from ckdlab.modeling import model_specs, smoke_test
        from tests.helpers import DATA

        X, y, _ = load_training_data(DATA)
        self.assertEqual(len(smoke_test(model_specs(quick=True), X, y)), 7)


class Reports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, _ = shared_service()

    def test_schema_and_models_report_are_strict_json(self):
        schema = self.service.schema()
        json.dumps(schema, allow_nan=False)
        self.assertEqual(len(schema["features"]), 24)
        self.assertEqual([b["key"] for b in schema["bands"]], ["low", "guarded", "elevated", "high"])
        report = self.service.models_report()
        json.dumps(report, allow_nan=False)
        self.assertEqual(len(report["models"]), 8)  # seven models plus the ensemble
        ensemble = next(m for m in report["models"] if m["is_ensemble"])
        self.assertGreater(ensemble["accuracy"], 0.9)
        self.assertGreater(ensemble["roc_auc"], 0.95)
        self.assertTrue(math.isclose(sum(ensemble["confusion"].values()), 400))
        self.assertEqual(report["importance"][0]["relative"], 1.0)


if __name__ == "__main__":
    unittest.main()
