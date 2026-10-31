"""Flask application: a JSON API plus the static front end.

Endpoints
    GET  /api/health          liveness and model info
    GET  /api/schema          feature definitions, bands and sample patients (drives the form)
    GET  /api/models          cross-validated metrics, ROC curves, feature importance
    POST /api/predict         {"inputs": {...}, "explain": true}
    POST /api/sensitivity     {"inputs": {...}, "feature": "sc", "points": 41}
    POST /api/predict/batch   multipart upload, field "file" (CSV)
    GET  /api/template.csv    CSV template for batch uploads
"""
from __future__ import annotations

import csv
import io
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, Response, g, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from .config import Settings
from .samples import SAMPLES
from .schema import KEYS, ValidationError
from .service import PredictionService

log = logging.getLogger("ckdlab.api")
STATIC_DIR = Path(__file__).resolve().parent / "static"

CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


class StrictJSONProvider(DefaultJSONProvider):
    """Never emit NaN or Infinity (invalid JSON); fail loudly instead."""

    sort_keys = False

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        kwargs.setdefault("allow_nan", False)
        return super().dumps(obj, **kwargs)


def _error(status: int, code: str, message: str, details: list | None = None) -> Response:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    response = jsonify(body)
    response.status_code = status
    return response


def _json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "bad_request", "Send a JSON object with Content-Type: application/json.")
    return data


def create_app(settings: Settings | None = None, service: PredictionService | None = None) -> Flask:
    settings = settings or Settings.from_env()
    if not logging.getLogger().handlers:
        logging.basicConfig(level=settings.log_level,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    service = service or PredictionService.load(settings)

    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.json = StrictJSONProvider(app)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_kb * 1024
    app.extensions["ckd_service"] = service

    # ------------------------------------------------------------------ pages
    @app.get("/")
    def index() -> Response:
        return send_from_directory(STATIC_DIR, "index.html")

    # -------------------------------------------------------------------- API
    @app.get("/api/health")
    def health() -> Response:
        return jsonify(service.health())

    @app.get("/api/schema")
    def schema() -> Response:
        return jsonify(service.schema())

    @app.get("/api/models")
    def models() -> Response:
        return jsonify(service.models_report())

    @app.post("/api/predict")
    def predict() -> Response:
        body = _json_body()
        return jsonify(service.predict(body.get("inputs"), explain=body.get("explain", True) is not False))

    @app.post("/api/sensitivity")
    def sensitivity() -> Response:
        body = _json_body()
        try:
            points = int(body.get("points", 41))
        except (TypeError, ValueError):
            raise ApiError(400, "bad_request", "'points' must be an integer.")
        return jsonify(service.sensitivity(body.get("inputs"), body.get("feature"), points))

    @app.post("/api/predict/batch")
    def predict_batch() -> Response:
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            raise ApiError(400, "bad_request", "Attach a CSV file in the 'file' field.")
        payload = upload.read()
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = payload.decode("latin-1")
        try:
            frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, sep=None,
                                engine="python", nrows=settings.max_batch_rows + 1)
        except Exception:
            raise ApiError(400, "bad_csv", "That file could not be read as CSV.")
        return jsonify(service.predict_batch(frame))

    @app.get("/api/template.csv")
    def template() -> Response:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", *KEYS])
        for sample in SAMPLES:
            writer.writerow([sample["id"], *[sample["inputs"].get(k, "") for k in KEYS]])
        return Response(buffer.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="ckd-template.csv"'})

    # ----------------------------------------------------------------- errors
    @app.errorhandler(ApiError)
    def api_error(exc: ApiError) -> Response:
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.errorhandler(ValidationError)
    def validation_error(exc: ValidationError) -> Response:
        first = exc.details[0]["message"] if exc.details else "Invalid input."
        extra = len(exc.details) - 1
        message = first if extra < 1 else f"{first} {extra} more {'problem' if extra == 1 else 'problems'} found."
        return _error(422, "validation_error", message, exc.details)

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException) -> Any:
        if not request.path.startswith("/api/"):
            return exc
        if exc.code == 413:
            return _error(413, "file_too_large", f"The file is larger than {settings.max_upload_kb} KB.")
        if exc.code == 404:
            return _error(404, "not_found", "No such endpoint.")
        if exc.code == 405:
            return _error(405, "method_not_allowed", "That method is not allowed for this endpoint.")
        code = (exc.name or "error").lower().replace(" ", "_")
        return _error(exc.code or 500, code, exc.description or exc.name or "Error")

    @app.errorhandler(Exception)
    def unexpected(exc: Exception) -> Response:
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return _error(500, "server_error", "Something went wrong on the server.")

    # ---------------------------------------------------------------- headers
    @app.before_request
    def start_timer() -> None:
        g.started = time.perf_counter()

    @app.after_request
    def finish(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", CSP)
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"  # patient data is never cached
            elapsed = (time.perf_counter() - g.get("started", time.perf_counter())) * 1000
            log.info("%s %s -> %s (%.0f ms)", request.method, request.path, response.status_code, elapsed)
        else:
            response.headers["Cache-Control"] = "no-cache"  # always revalidate (ETag) so edits show up
        return response

    return app
