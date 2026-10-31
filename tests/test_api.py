import io
import json
import unittest
from dataclasses import replace

from ckdlab.api import create_app
from tests.helpers import shared_service


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, cls.settings = shared_service()
        cls.app = create_app(cls.settings, cls.service)
        cls.client = cls.app.test_client()
        cls.samples = {s["id"]: s["inputs"] for s in cls.client.get("/api/schema").get_json()["samples"]}

    def post(self, path, **kwargs):
        return self.client.post(path, **kwargs)

    # ------------------------------------------------------------- read-only
    def test_health_schema_models(self):
        health = self.client.get("/api/health").get_json()
        self.assertEqual(health["status"], "ok")
        self.assertEqual(len(health["model"]["members"]), 7)
        schema = self.client.get("/api/schema").get_json()
        self.assertEqual(len(schema["features"]), 24)
        self.assertEqual(schema["minFields"], 5)
        self.assertIn("not a medical device", schema["disclaimer"])
        models = self.client.get("/api/models").get_json()
        self.assertEqual(len(models["models"]), 8)

    def test_index_and_static_files(self):
        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn(b"CKD Risk Lab", index.data)
        self.assertEqual(self.client.get("/static/js/main.js").status_code, 200)
        self.assertEqual(self.client.get("/static/css/styles.css").status_code, 200)

    def test_headers(self):
        api = self.client.get("/api/health")
        self.assertEqual(api.headers["Cache-Control"], "no-store")
        self.assertEqual(api.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'self'", api.headers["Content-Security-Policy"])
        self.assertEqual(self.client.get("/").headers["Cache-Control"], "no-cache")

    # --------------------------------------------------------------- predict
    def test_predict(self):
        r = self.post("/api/predict", json={"inputs": self.samples["advanced"]})
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(body["label"], "ckd")
        self.assertEqual(len(body["models"]), 7)
        self.assertIn("explanation", body)
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_predict_without_explanation_is_lighter(self):
        body = self.post("/api/predict", json={"inputs": self.samples["typical"], "explain": False}).get_json()
        self.assertNotIn("explanation", body)

    def test_predict_accepts_friendly_values(self):
        r = self.post("/api/predict", json={"inputs": {**self.samples["typical"], "pcc": "absent", "htn": False, "sg": "1.02"}, "explain": False})
        self.assertEqual(r.status_code, 200)

    def test_validation_errors_are_reported_per_field(self):
        r = self.post("/api/predict", json={"inputs": {**self.samples["typical"], "sc": 99, "sod": "abc", "xyz": 1}})
        body = r.get_json()
        self.assertEqual(r.status_code, 422)
        self.assertEqual(body["error"]["code"], "validation_error")
        self.assertEqual({d["field"] for d in body["error"]["details"]}, {"sc", "sod", "xyz"})
        self.assertIn("2 more problems", body["error"]["message"])

    def test_too_few_fields(self):
        r = self.post("/api/predict", json={"inputs": {"age": 40}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("at least 5", r.get_json()["error"]["message"])

    def test_bad_bodies(self):
        self.assertEqual(self.post("/api/predict", data="hello").status_code, 400)
        self.assertEqual(self.post("/api/predict", json=[1, 2]).status_code, 400)
        self.assertEqual(self.post("/api/predict", json={}).status_code, 422)

    def test_unknown_routes_and_methods_return_json(self):
        missing = self.client.get("/api/nope")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["error"]["code"], "not_found")
        wrong = self.client.delete("/api/predict")
        self.assertEqual(wrong.status_code, 405)
        self.assertEqual(wrong.get_json()["error"]["code"], "method_not_allowed")

    # ----------------------------------------------------------- sensitivity
    def test_sensitivity(self):
        r = self.post("/api/sensitivity", json={"inputs": self.samples["mixed"], "feature": "hemo", "points": 9})
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(body["grid"]), 9)
        bad = self.post("/api/sensitivity", json={"inputs": self.samples["mixed"], "feature": "nope"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.post("/api/sensitivity", json={"inputs": self.samples["mixed"], "feature": "sc", "points": "x"}).status_code, 400)

    # ----------------------------------------------------------------- batch
    def upload(self, content, name="cohort.csv", client=None):
        return (client or self.client).post("/api/predict/batch", data={"file": (io.BytesIO(content), name)},
                                            content_type="multipart/form-data")

    def test_template_round_trips_through_batch(self):
        template = self.client.get("/api/template.csv")
        self.assertEqual(template.mimetype, "text/csv")
        r = self.upload(template.data)
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(body["summary"]["scored"], 3)
        self.assertEqual([row["id"] for row in body["rows"]], ["typical", "mixed", "advanced"])
        self.assertLess(body["rows"][0]["risk"], body["rows"][2]["risk"])

    def test_batch_accepts_semicolons_bom_and_latin1(self):
        text = "id;age;bp;sg;al;hemo\nA;50;80;1.015;1;12\nB;40;70;1.02;0;15\nC;30;;;;\n"
        for payload in (text.encode(), b"\xef\xbb\xbf" + text.encode(), text.replace("A;", "\xc9;").encode("latin-1")):
            body = self.upload(payload).get_json()
            self.assertEqual(body["summary"]["scored"], 2)
            self.assertEqual(body["summary"]["skipped"], 1)

    def test_batch_errors(self):
        self.assertEqual(self.upload(b"foo,bar\n1,2\n").status_code, 422)
        self.assertEqual(self.client.post("/api/predict/batch", data={}, content_type="multipart/form-data").status_code, 400)

    def test_upload_size_limit(self):
        small = create_app(replace(self.settings, max_upload_kb=1), self.service).test_client()
        r = self.upload(b"id,age\n" + b"1,40\n" * 5000, client=small)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.get_json()["error"]["code"], "file_too_large")

    def test_responses_never_contain_nan(self):
        # StrictJSONProvider raises on NaN, so a successful response proves there is none.
        r = self.post("/api/predict", json={"inputs": {"age": 50, "bp": 80, "sg": 1.01, "al": 3, "hemo": 9}})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"NaN", r.data)
        json.loads(r.data)


if __name__ == "__main__":
    unittest.main()
