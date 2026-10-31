import unittest

import pandas as pd

from ckdlab.data import build_reference, clean_features, load_training_data, parse_labels
from ckdlab.schema import KEYS
from tests.helpers import DATA


class Cleaning(unittest.TestCase):
    def test_repairs_stray_whitespace_and_placeholders(self):
        raw = pd.DataFrame({"pcv": ["\t43", "44", "\t?"], "dm": ["\tyes", " no", "yes"], "AGE": ["50", "?", "61"]})
        clean = clean_features(raw)
        self.assertEqual(clean.X["pcv"].iloc[0], 43.0)
        self.assertTrue(pd.isna(clean.X["pcv"].iloc[2]))
        self.assertEqual(list(clean.X["dm"]), [1.0, 0.0, 1.0])
        self.assertEqual(clean.X["age"].iloc[2], 61.0)  # column names are case-insensitive
        self.assertGreaterEqual(clean.repaired, 4)
        self.assertEqual(clean.nulled, 0)

    def test_implausible_values_become_missing_and_are_reported(self):
        raw = pd.DataFrame({"age": ["50", "40"], "sod": ["4.5", "140"], "sc": ["76", "1.1"]})
        clean = clean_features(raw)
        self.assertTrue(pd.isna(clean.X["sod"].iloc[0]) and pd.isna(clean.X["sc"].iloc[0]))
        self.assertEqual(clean.nulled, 2)
        self.assertEqual(len(clean.issues[0]), 2)
        self.assertNotIn(1, clean.issues)

    def test_unrecognised_columns_are_ignored(self):
        clean = clean_features(pd.DataFrame({"foo": [1], "age": [30]}))
        self.assertEqual(clean.recognized, ["age"])
        self.assertEqual(list(clean.X.columns), KEYS)

    def test_labels(self):
        parsed = parse_labels(pd.Series(["ckd", "ckd\t", " notckd", "maybe"]))
        self.assertEqual(parsed.iloc[:3].tolist(), [1.0, 1.0, 0.0])
        self.assertTrue(pd.isna(parsed.iloc[3]))


class TrainingData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.X, cls.y, cls.report = load_training_data(DATA)

    def test_shape_and_balance(self):
        self.assertEqual(self.X.shape, (400, 24))
        self.assertEqual(self.report["class_counts"], {"ckd": 250, "notckd": 150})
        self.assertTrue(all(str(t) == "float64" for t in self.X.dtypes))
        self.assertEqual(set(self.y.unique()), {0, 1})

    def test_appetite_is_encoded_with_poor_as_one(self):
        # Poor appetite should be more common among CKD patients if 1 really means "poor".
        self.assertGreater(self.X.loc[self.y == 1, "appet"].mean(), self.X.loc[self.y == 0, "appet"].mean() + 0.2)

    def test_cleaning_report(self):
        self.assertGreater(self.report["cells_repaired"], 0)
        self.assertGreaterEqual(self.report["cells_blanked"], 3)  # sod 4.5, pot 47, sc 76 at least
        self.assertLess(self.report["complete_rows"], 400)

    def test_reference_profile_is_healthy(self):
        ref = build_reference(self.X, self.y)
        self.assertEqual(ref["baseline"]["al"], 0.0)
        self.assertGreater(ref["baseline"]["hemo"], 13.0)
        self.assertLess(ref["baseline"]["sc"], 1.5)
        self.assertEqual(ref["baseline"]["htn"], 0.0)
        lo, hi = ref["training_range"]["hemo"]
        self.assertLess(lo, 6.0)
        self.assertGreater(hi, 17.0)


if __name__ == "__main__":
    unittest.main()
