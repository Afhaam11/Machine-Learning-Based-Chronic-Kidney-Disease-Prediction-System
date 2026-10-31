import math
import unittest

from ckdlab.schema import (
    BINARY_KEYS, FEATURE_MAP, FEATURES, GROUPS, KEYS, NUMERIC_KEYS, FieldError, ValidationError, parse_inputs,
)


class SchemaShape(unittest.TestCase):
    def test_24_unique_features_in_known_groups(self):
        self.assertEqual(len(FEATURES), 24)
        self.assertEqual(len(set(KEYS)), 24)
        self.assertEqual(len(NUMERIC_KEYS) + len(BINARY_KEYS), 24)
        known = {g for g, _label, _text in GROUPS}
        self.assertTrue(all(f.group in known for f in FEATURES))

    def test_public_description_is_json_friendly(self):
        import json
        json.dumps([f.public() for f in FEATURES], allow_nan=False)


class BinaryEncoding(unittest.TestCase):
    def test_one_means_the_adverse_finding(self):
        # The original Streamlit app sent good appetite as 1, but the notebook trained poor as 1.
        self.assertEqual(FEATURE_MAP["appet"].coerce("poor"), 1.0)
        self.assertEqual(FEATURE_MAP["appet"].coerce("good"), 0.0)
        for key, adverse, benign in (("rbc", "abnormal", "normal"), ("pc", "abnormal", "normal"),
                                     ("pcc", "present", "notpresent"), ("ba", "present", "notpresent"),
                                     ("htn", "yes", "no"), ("dm", "yes", "no"), ("cad", "yes", "no"),
                                     ("pe", "yes", "no"), ("ane", "yes", "no")):
            self.assertEqual(FEATURE_MAP[key].coerce(adverse), 1.0, key)
            self.assertEqual(FEATURE_MAP[key].coerce(benign), 0.0, key)

    def test_friendly_spellings(self):
        self.assertEqual(FEATURE_MAP["pcc"].coerce("absent"), 0.0)
        self.assertEqual(FEATURE_MAP["pcc"].coerce("Not Present"), 0.0)
        self.assertEqual(FEATURE_MAP["htn"].coerce(True), 1.0)
        self.assertEqual(FEATURE_MAP["htn"].coerce("  YES\t"), 1.0)
        self.assertEqual(FEATURE_MAP["appet"].coerce(0), 0.0)

    def test_unknown_word_is_rejected(self):
        with self.assertRaises(FieldError):
            FEATURE_MAP["appet"].coerce("excellent")
        with self.assertRaises(FieldError):
            FEATURE_MAP["rbc"].coerce("yes")


class NumericParsing(unittest.TestCase):
    def test_blank_tokens_are_missing(self):
        for raw in (None, "", " ", "?", "\t?", "nan", "NA", float("nan")):
            self.assertTrue(math.isnan(FEATURE_MAP["sc"].coerce(raw)), repr(raw))

    def test_strings_and_numbers(self):
        self.assertEqual(FEATURE_MAP["sc"].coerce("1.2"), 1.2)
        self.assertEqual(FEATURE_MAP["age"].coerce(" 45\t"), 45.0)

    def test_limits_are_enforced(self):
        with self.assertRaisesRegex(FieldError, "between"):
            FEATURE_MAP["sc"].coerce(99)
        with self.assertRaisesRegex(FieldError, "between"):
            FEATURE_MAP["sod"].coerce(4.5)  # a data-entry error present in the public dataset
        with self.assertRaisesRegex(FieldError, "number"):
            FEATURE_MAP["sc"].coerce("abc")
        with self.assertRaises(FieldError):
            FEATURE_MAP["sc"].coerce(float("inf"))

    def test_dipstick_levels_are_whole_numbers(self):
        self.assertEqual(FEATURE_MAP["al"].coerce("3"), 3.0)
        with self.assertRaisesRegex(FieldError, "whole"):
            FEATURE_MAP["al"].coerce(2.5)
        with self.assertRaises(FieldError):
            FEATURE_MAP["al"].coerce(6)


class RequestParsing(unittest.TestCase):
    def test_success_fills_every_key(self):
        values = parse_inputs({"age": 50, "bp": 80, "sg": 1.015, "al": 1, "htn": "yes"})
        self.assertEqual(set(values), set(KEYS))
        self.assertEqual(sum(not math.isnan(v) for v in values.values()), 5)

    def test_errors_are_collected_per_field(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_inputs({"age": 500, "sc": "x", "bogus": 1})
        self.assertEqual({d["field"] for d in ctx.exception.details}, {"age", "sc", "bogus"})

    def test_minimum_number_of_fields(self):
        with self.assertRaisesRegex(ValidationError, "at least"):
            parse_inputs({"age": 40, "bp": 80})
        with self.assertRaises(ValidationError):
            parse_inputs(["not", "an", "object"])


if __name__ == "__main__":
    unittest.main()
