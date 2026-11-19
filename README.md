# SACA: Smart Adaptive Clinical Assistant

SACA is an offline triage app in English and Kiswahili, built for Mbinga District, Ruvuma Region, Tanzania.
A person describes symptoms by tapping buttons, typing, or using a Body Map. SACA returns an urgency level
(LOW, MEDIUM, HIGH or CRITICAL), what to do next, and who to call. It runs with no internet.

> **Student prototype, not a medical device.** SACA gives decision support, not a diagnosis. The danger-sign
> rules, the advice text, the medicine information and the Swahili wording are drafts. None of them has been
> reviewed by a clinician or checked by a native Swahili speaker. Do not use SACA for real patients before that
> review. See Part 3 of the handover documentation.

Built by Group P51 for Swinburne University of Technology ICT30017/ICT30018 (2026): Minh-Hieu Ong, Ryan Cheng,
Md Shayan Ibteshum, Abdullah Azzam and Hitesh Kumar.

## Documentation

Full documentation is in **[docs/SACA_Handover_Documentation.docx](docs/SACA_Handover_Documentation.docx)**, in four parts:

1. Overview: what SACA is, quick start, repository layout.
2. User Guide: signing in, running an assessment, reading the result, History, contacts, language.
3. Clinical and Safety: how SACA decides a level, the safety rules, test results and their limits, what must be reviewed before real use.
4. Technical and Debugging Guide: architecture, setup, tests, retraining, the Android build, troubleshooting.

How the training data was built: [dataset_v2/README_v2.md](dataset_v2/README_v2.md).

## Quick start (computer)

Needs Python 3.10 or newer.

```
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Mac or Linux
pip install -r requirements.txt
python logistic_regression.app.py
```

Open http://127.0.0.1:5000. On the first run the login screen offers **Set up the first staff account**, which
creates the administrator. After that, anyone can **Continue as guest** or create a profile.

No API key is needed. The optional online extras (voice input and the LLM symptom extractor) need a Groq API key
in a `.env` file; without one, the app works fully offline. See Part 4 of the handover documentation.

## Quick start (Android phone)

The Android app is the same SACA app running fully offline inside the phone, with no internet permission.
Open the `android/` folder in Android Studio, connect the phone with USB debugging on, and press **Run**.
Full steps are in [android/README.md](android/README.md) and Part 4, section 6 of the handover documentation.

## Run the tests

```
set GROQ_API_KEY=dummy           # Windows (cmd); on Mac or Linux: export GROQ_API_KEY=dummy
python -m pytest -q
```

Last full run (19 November 2026): 378 passed, 1 skipped. The dummy key is needed because a module creates its
Groq client when it is imported.

## Repository layout

| Path | What it is |
|---|---|
| `logistic_regression.app.py` | Starts the Flask app (`create_app`) |
| `saca_views.py`, `saca_auth.py` | Screens and routes; sign-in, sessions and security |
| `saca_store.py` | Local SQLite database: accounts, patients, assessments, contacts, audit log |
| `assessment_flow.py` | The step-by-step assessment (buttons, danger questions) |
| `guidance.py`, `conditions.py` | Result cards: next steps, medicine information, possible condition |
| `classifier/` | The triage pipeline: reader, logistic regression model, red-flag floor, portable model |
| `dataset_v2/` | Training data, red-flag rules, evaluation reports, clinician review pack |
| `templates/` | HTML screens (Jinja2) and the stylesheet |
| `i18n.py`, `i18n_sw.py`, `keywords.py` | English and Swahili interface text and Swahili symptom words |
| `speech.py` | Read-aloud audio, including an optional offline Swahili voice |
| `mobile/` | Builds the Android app's Python bundle |
| `android/` | The Android Studio project |
| `tests/` | Automated tests (pytest) |
| `main.py`, `ammu_*.py`, `database.py` | Earlier FastAPI prototype and the AMMU chat; kept for reference, not used by the app |
