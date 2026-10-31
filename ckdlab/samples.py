"""Example patients for one-click demos.

These are illustrative profiles, not records from the training data. The
descriptions say what the inputs look like and never what the model will
predict; the tests check that each sample lands where a reader would expect.
"""
from __future__ import annotations

_TYPICAL = {
    "age": 34, "bp": 70, "sg": 1.02, "al": 0, "su": 0, "rbc": "normal", "pc": "normal",
    "pcc": "notpresent", "ba": "notpresent", "bgr": 98, "bu": 28, "sc": 0.9, "sod": 141,
    "pot": 4.3, "hemo": 15.1, "pcv": 46, "wc": 7200, "rc": 5.3, "htn": "no", "dm": "no",
    "cad": "no", "appet": "good", "pe": "no", "ane": "no",
}

SAMPLES: list[dict] = [
    {
        "id": "typical",
        "title": "Typical adult",
        "description": "Normal vitals, clear urine, and blood values inside the usual ranges.",
        "inputs": dict(_TYPICAL),
    },
    {
        "id": "mixed",
        "title": "Mixed signals",
        "description": "Blood chemistry looks typical, but there is hypertension, swollen ankles, a "
                       "higher blood pressure reading and abnormal red cells in the urine.",
        "inputs": {**_TYPICAL, "bp": 90, "rbc": "abnormal", "htn": "yes", "pe": "yes"},
    },
    {
        "id": "advanced",
        "title": "Advanced findings",
        "description": "High creatinine and urea, low hemoglobin, heavy protein in the urine, with "
                       "hypertension, diabetes, edema and poor appetite.",
        "inputs": {
            "age": 62, "bp": 100, "sg": 1.01, "al": 4, "su": 1, "rbc": "abnormal", "pc": "abnormal",
            "pcc": "present", "ba": "notpresent", "bgr": 158, "bu": 112, "sc": 6.8, "sod": 134,
            "pot": 5.4, "hemo": 8.6, "pcv": 26, "wc": 9800, "rc": 3.1, "htn": "yes", "dm": "yes",
            "cad": "no", "appet": "poor", "pe": "yes", "ane": "yes",
        },
    },
]
