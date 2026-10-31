"""Start CKD Risk Lab:  python run.py   (add --help for options)."""
from __future__ import annotations

import argparse
import logging

from ckdlab.api import create_app
from ckdlab.config import Settings


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Run the CKD Risk Lab web app.")
    parser.add_argument("--host", default=settings.host, help="interface to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=settings.port, help="port (default: %(default)s)")
    parser.add_argument("--retrain", action="store_true", help="train the models again before starting")
    parser.add_argument("--debug", action="store_true", help="Flask development server with auto-reload")
    args = parser.parse_args()

    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.retrain:
        from ckdlab.train import train

        train(settings)

    app = create_app(settings)  # trains automatically on first run if no model exists yet
    print(f"\n  CKD Risk Lab is running at http://{args.host}:{args.port}  (Ctrl+C to stop)\n")

    if args.debug:
        app.run(host=args.host, port=args.port, debug=True)
        return
    try:
        from waitress import serve
    except ImportError:
        logging.getLogger("ckdlab").warning(
            "waitress is not installed; using Flask's built-in server. "
            "Run `pip install waitress` for a production-grade one.")
        app.run(host=args.host, port=args.port, threaded=True)
    else:
        serve(app, host=args.host, port=args.port, threads=4)


if __name__ == "__main__":
    main()
