"""
SACA app (Flask). Run:  python logistic_regression.app.py   then open http://127.0.0.1:5000

First run: the login screen offers "Set up the first staff account" (an administrator). After that:
  * anyone can "Continue as guest" or create their own profile (name, date of birth, sex, PIN);
  * family members sign in with their name and PIN and see only their own history;
  * staff sign in with a username and password and see every patient on this device.

Data is kept in one SQLite file on this computer (see saca_store.py for the location and privacy notes).
Set SACA_DEBUG=1 only on a developer machine: the debugger must never run where real patient data is stored.
"""
import os
import sys

from flask import Flask

import i18n
import saca_auth
import saca_store as store
import saca_views


def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def build_pipeline():
    from classifier.llm_extractor import extract_symptoms
    from classifier.pipeline import SACAPipeline

    pipeline = SACAPipeline(extractor=extract_symptoms)
    pipeline.classifier.train()
    return pipeline


def create_app(pipeline=None, config=None):
    app = Flask(__name__, template_folder=resource_path("templates"))
    if config:
        app.config.update(config)

    store.init_db()
    i18n.init_app(app)
    saca_auth.init_app(app)
    saca_views.init_app(app)

    # Voice input: POST /transcribe and GET /voice.js (see voice_flask.py). Needs internet (Groq).
    from voice_flask import voice_bp
    app.register_blueprint(voice_bp)

    app.config["SACA_PIPELINE"] = pipeline or build_pipeline()
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=os.environ.get("SACA_HOST", "127.0.0.1"),
        port=int(os.environ.get("SACA_PORT", "5000")),
        debug=os.environ.get("SACA_DEBUG") == "1",
    )
