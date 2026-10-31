"""Single source of truth for the 24 clinical measurements.

The same definitions drive input validation, the batch CSV importer, the
preprocessing pipeline, and the form the browser renders (via ``/api/schema``).
That is deliberate: the original Streamlit app encoded the form values by hand
and mapped appetite the wrong way round compared with training. Here the
encoding lives in exactly one place.

Convention: every binary measurement is encoded so that ``1`` is the adverse
finding (abnormal, present, yes, poor) and ``0`` is the benign one.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

MISSING_TOKENS = frozenset({"", "?", "nan", "none", "null", "na", "n/a", "-", "unknown"})
_TRUE_TOKENS = frozenset({"true", "1"})
_FALSE_TOKENS = frozenset({"false", "0"})

# A prediction made from fewer measurements than this is mostly imputation.
MIN_FIELDS = 5


class FieldError(ValueError):
    """A single value failed validation."""


class ValidationError(ValueError):
    """One or more fields of a request failed validation."""

    def __init__(self, details: list[dict[str, str]]):
        self.details = details
        super().__init__("; ".join(f"{d['field']}: {d['message']}" for d in details))


def _fmt(x: float) -> str:
    return f"{x:g}"


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    group: str
    kind: str  # "number" | "ordinal" | "binary"
    hint: str = ""
    unit: str = ""
    lo: float | None = None  # hard plausibility limits, enforced on input
    hi: float | None = None
    ui_lo: float | None = None  # scale used by sliders, range strips and curves
    ui_hi: float | None = None
    step: float = 1.0
    decimals: int = 0
    ref: tuple[float, float] | None = None  # typical adult reference interval (display only)
    scale: str = "linear"  # "linear" | "log" (display scale for skewed values)
    integer: bool = False
    levels: tuple[tuple[float, str], ...] = ()  # ordinal levels as (value, label)
    normal_levels: tuple[float, ...] = ()
    options: tuple[tuple[str, str], ...] = ()  # binary: (benign, adverse) as (value, label)
    aliases: tuple[tuple[str, int], ...] = ()  # extra accepted spellings -> code

    # ------------------------------------------------------------------ parsing
    def coerce(self, raw: Any) -> float:
        """Return the encoded value, ``nan`` when missing, or raise ``FieldError``."""
        text: str | None
        number: float | None
        if raw is None:
            return math.nan
        if isinstance(raw, (bool, np.bool_)):
            number, text = float(bool(raw)), ("true" if raw else "false")
        elif isinstance(raw, (int, float, np.integer, np.floating)):
            number, text = float(raw), None
            if math.isnan(number):
                return math.nan
        else:
            text = str(raw).strip().lower()
            if text in MISSING_TOKENS:
                return math.nan
            try:
                number = float(text)
            except ValueError:
                number = None

        if self.kind == "binary":
            return self._coerce_binary(text, number)
        return self._coerce_number(number)

    def _coerce_binary(self, text: str | None, number: float | None) -> float:
        if text is not None:
            for code, (value, _label) in enumerate(self.options):
                if text == value:
                    return float(code)
            for alias, code in self.aliases:
                if text == alias:
                    return float(code)
            if text in _TRUE_TOKENS:
                return 1.0
            if text in _FALSE_TOKENS:
                return 0.0
        if number in (0.0, 1.0):
            return float(number)
        benign, adverse = self.options[0][0], self.options[1][0]
        raise FieldError(f"{self.label} must be '{benign}' or '{adverse}'.")

    def _coerce_number(self, number: float | None) -> float:
        if number is None or not math.isfinite(number):
            raise FieldError(f"{self.label} must be a number.")
        if self.lo is not None and self.hi is not None and not (self.lo <= number <= self.hi):
            unit = f" {self.unit}" if self.unit else ""
            raise FieldError(
                f"{self.label} must be between {_fmt(self.lo)} and {_fmt(self.hi)}{unit}."
            )
        if self.integer and abs(number - round(number)) > 1e-9:
            raise FieldError(f"{self.label} must be a whole number.")
        return number

    # --------------------------------------------------------------- presenting
    def display(self, value: float) -> str:
        """Human-readable rendering of an encoded value."""
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "not provided"
        if self.kind == "binary":
            return self.options[int(round(value))][1]
        if self.kind == "ordinal":
            for level, label in self.levels:
                if abs(level - value) < 1e-9:
                    return label
        text = f"{value:.{self.decimals}f}"
        return f"{text} {self.unit}".strip()

    def public(self) -> dict[str, Any]:
        """JSON description of the feature for the browser."""
        out: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "group": self.group,
            "kind": self.kind,
            "hint": self.hint,
            "unit": self.unit,
        }
        if self.kind == "binary":
            out["options"] = [
                {"value": value, "label": label, "adverse": code == 1}
                for code, (value, label) in enumerate(self.options)
            ]
        else:
            out.update(
                lo=self.lo,
                hi=self.hi,
                step=self.step,
                decimals=self.decimals,
                integer=self.integer,
            )
            if self.kind == "ordinal":
                out["levels"] = [{"value": v, "label": label} for v, label in self.levels]
                out["normalLevels"] = list(self.normal_levels)
            else:
                out.update(
                    ui=[self.ui_lo, self.ui_hi],
                    ref=list(self.ref) if self.ref else None,
                    scale=self.scale,
                )
        return out


GROUPS: tuple[tuple[str, str, str], ...] = (
    ("vitals", "Vitals", "Taken at the bedside."),
    ("urine", "Urinalysis", "Dipstick and microscopy results from a urine sample."),
    ("blood", "Blood work", "Laboratory values from a blood sample."),
    ("history", "History and signs", "Known conditions and physical findings."),
)

_ABSENT = (("absent", 0), ("not present", 0), ("not_present", 0))
_DIPSTICK = tuple((float(i), str(i)) for i in range(6))

# Dataset column order (the order of the original CSV).
FEATURES: tuple[Feature, ...] = (
    Feature("age", "Age", "vitals", "number", unit="years", lo=0, hi=120, ui_lo=1, ui_hi=90,
            hint="Age in years."),
    Feature("bp", "Blood pressure", "vitals", "number", unit="mm Hg", lo=30, hi=260,
            ui_lo=40, ui_hi=180, ref=(60, 80),
            hint="A single reading. Values in the training data cluster around 80, "
                 "which matches diastolic pressure."),
    Feature("sg", "Urine specific gravity", "urine", "ordinal", lo=1.0, hi=1.05, step=0.005,
            decimals=3,
            levels=tuple((v, f"{v:.3f}") for v in (1.005, 1.010, 1.015, 1.020, 1.025)),
            hint="Dipstick reading of how concentrated the urine is."),
    Feature("al", "Albumin in urine", "urine", "ordinal", lo=0, hi=5, integer=True,
            levels=_DIPSTICK, normal_levels=(0.0,),
            hint="Protein on a urine dipstick: 0 is none, 5 is the highest reading."),
    Feature("su", "Sugar in urine", "urine", "ordinal", lo=0, hi=5, integer=True,
            levels=_DIPSTICK, normal_levels=(0.0,),
            hint="Glucose on a urine dipstick: 0 is none, 5 is the highest reading."),
    Feature("rbc", "Red blood cells in urine", "urine", "binary",
            options=(("normal", "Normal"), ("abnormal", "Abnormal")),
            hint="Red blood cells seen on urine microscopy."),
    Feature("pc", "Pus cells in urine", "urine", "binary",
            options=(("normal", "Normal"), ("abnormal", "Abnormal")),
            hint="White blood cells (pus cells) seen on urine microscopy."),
    Feature("pcc", "Pus cell clumps", "urine", "binary",
            options=(("notpresent", "Not present"), ("present", "Present")), aliases=_ABSENT,
            hint="Clumps of pus cells seen on urine microscopy."),
    Feature("ba", "Bacteria in urine", "urine", "binary",
            options=(("notpresent", "Not present"), ("present", "Present")), aliases=_ABSENT,
            hint="Bacteria seen on urine microscopy."),
    Feature("bgr", "Random blood glucose", "blood", "number", unit="mg/dL", lo=10, hi=900,
            ui_lo=40, ui_hi=500, ref=(70, 140),
            hint="Blood glucose measured at a random time, not fasting."),
    Feature("bu", "Blood urea", "blood", "number", unit="mg/dL", lo=1, hi=500,
            ui_lo=5, ui_hi=300, ref=(15, 40), hint="Urea in the blood."),
    Feature("sc", "Serum creatinine", "blood", "number", unit="mg/dL", lo=0.1, hi=40,
            ui_lo=0.3, ui_hi=15, step=0.1, decimals=1, ref=(0.6, 1.3), scale="log",
            hint="Creatinine in the blood, a waste product the kidneys clear."),
    Feature("sod", "Sodium", "blood", "number", unit="mEq/L", lo=80, hi=180,
            ui_lo=110, ui_hi=160, ref=(135, 145), hint="Sodium in the blood."),
    Feature("pot", "Potassium", "blood", "number", unit="mEq/L", lo=1.0, hi=10,
            ui_lo=2, ui_hi=8, step=0.1, decimals=1, ref=(3.5, 5.0),
            hint="Potassium in the blood."),
    Feature("hemo", "Hemoglobin", "blood", "number", unit="g/dL", lo=2, hi=25,
            ui_lo=3, ui_hi=18, step=0.1, decimals=1, ref=(12.0, 17.5),
            hint="Hemoglobin concentration in the blood."),
    Feature("pcv", "Packed cell volume", "blood", "number", unit="%", lo=5, hi=70,
            ui_lo=10, ui_hi=60, ref=(36, 52),
            hint="Share of the blood volume made up of red cells (hematocrit)."),
    Feature("wc", "White blood cell count", "blood", "number", unit="cells/cmm", lo=500,
            hi=60000, ui_lo=2000, ui_hi=26000, step=100, ref=(4000, 11000),
            hint="White blood cells per cubic millimetre."),
    Feature("rc", "Red blood cell count", "blood", "number", unit="million/cmm", lo=1.0, hi=10,
            ui_lo=2, ui_hi=8, step=0.1, decimals=1, ref=(4.2, 6.0),
            hint="Red blood cells, in millions per cubic millimetre."),
    Feature("htn", "Hypertension", "history", "binary",
            options=(("no", "No"), ("yes", "Yes")), hint="Diagnosed high blood pressure."),
    Feature("dm", "Diabetes mellitus", "history", "binary",
            options=(("no", "No"), ("yes", "Yes")), hint="Diagnosed diabetes."),
    Feature("cad", "Coronary artery disease", "history", "binary",
            options=(("no", "No"), ("yes", "Yes")), hint="Diagnosed coronary artery disease."),
    Feature("appet", "Appetite", "history", "binary",
            options=(("good", "Good"), ("poor", "Poor")), hint="Reported appetite."),
    Feature("pe", "Pedal edema", "history", "binary",
            options=(("no", "No"), ("yes", "Yes")), hint="Swelling of the feet or ankles."),
    Feature("ane", "Anemia", "history", "binary",
            options=(("no", "No"), ("yes", "Yes")), hint="Diagnosed anemia."),
)

FEATURE_MAP: dict[str, Feature] = {f.key: f for f in FEATURES}
KEYS: list[str] = [f.key for f in FEATURES]
NUMERIC_KEYS: list[str] = [f.key for f in FEATURES if f.kind in ("number", "ordinal")]
BINARY_KEYS: list[str] = [f.key for f in FEATURES if f.kind == "binary"]


def parse_inputs(raw: Any, *, min_fields: int = MIN_FIELDS) -> dict[str, float]:
    """Validate a request payload. Returns ``{key: encoded value or nan}``."""
    if not isinstance(raw, Mapping):
        raise ValidationError([{"field": "inputs", "message": "Expected an object of measurements."}])
    errors: list[dict[str, str]] = []
    values = {key: math.nan for key in KEYS}
    for key, cell in raw.items():
        feature = FEATURE_MAP.get(str(key))
        if feature is None:
            errors.append({"field": str(key), "message": "Unknown measurement."})
            continue
        try:
            values[feature.key] = feature.coerce(cell)
        except FieldError as exc:
            errors.append({"field": feature.key, "message": str(exc)})
    if not errors:
        provided = sum(not math.isnan(v) for v in values.values())
        if provided < min_fields:
            errors.append(
                {"field": "inputs",
                 "message": f"Provide at least {min_fields} measurements (received {provided})."}
            )
    if errors:
        raise ValidationError(errors)
    return values
