"""
Rebuild the SACA Android app's web files from this repository.

    python mobile/build_android_assets.py "C:/Users/asus/AndroidStudioProjects/SACA"

Writes app/src/main/assets/www/{index.html, boot.js, app.zip} in that Android project. app.zip holds the
SACA Python app (only the files the phone needs), the trained model as JSON, and pure-Python copies of
Flask and its dependencies taken from this computer's Python. Run it after changing the app, then
rebuild the APK in Android Studio. The Python runtime (www/pyodide/, Pyodide 314.0.7 from npm) does not
change and is already in the Android project.
"""
import importlib.metadata as md
import os
import shutil
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FILES = [
    "logistic_regression.app.py", "saca_auth.py", "saca_store.py", "saca_views.py", "assessment_flow.py",
    "guidance.py", "conditions.py", "i18n.py", "i18n_sw.py", "speech.py", "keywords.py", "dataset.csv",
    "classifier/__init__.py", "classifier/base.py", "classifier/logistic_regression.py", "classifier/pipeline.py",
    "classifier/symptom_codes.py", "classifier/red_flags.py", "classifier/portable_model.py",
    "dataset_v2/saca_v2_model.json", "dataset_v2/red_flags.csv", "dataset_v2/code_crosswalk.csv",
    "dataset_v2/nonspecific_symptoms.csv", "dataset_v2/disease_urgency.csv",
]
SKIP_TEMPLATES = {"Full_SACA.html", "svm_dashboard.html", "logistic_dashboard.html", "history_detail.html"}
VENDOR = ["flask", "werkzeug", "jinja2", "markupsafe", "itsdangerous", "click", "blinker"]


def add_tree(z, src, arc):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith((".so", ".pyd", ".pyc")):
                continue  # compiled speed-ups do not run on the phone; the packages fall back to pure Python
            full = os.path.join(root, f)
            z.write(full, os.path.join(arc, os.path.relpath(full, src)).replace("\\", "/"))


def main(project):
    www = os.path.join(project, "app", "src", "main", "assets", "www")
    if not os.path.isdir(os.path.join(www, "pyodide")):
        sys.exit(f"{www}/pyodide is missing: get it with 'npm pack pyodide@314.0.7' and copy pyodide.js, "
                 "pyodide.mjs, pyodide.asm.mjs, pyodide.asm.wasm, python_stdlib.zip and pyodide-lock.json.")
    out = os.path.join(www, "app.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in APP_FILES:
            z.write(os.path.join(REPO, rel), rel)
        for f in os.listdir(os.path.join(REPO, "templates")):
            if f not in SKIP_TEMPLATES:
                z.write(os.path.join(REPO, "templates", f), "templates/" + f)
        z.write(os.path.join(REPO, "mobile", "mobile_main.py"), "mobile_main.py")
        for name in VENDOR:
            mod = __import__(name)
            add_tree(z, os.path.dirname(mod.__file__), "vendor/" + name)
            dist = md.distribution(name)
            for p in dist.files or []:
                if ".dist-info/" in str(p).replace("\\", "/"):
                    z.write(str(dist.locate_file(p)), "vendor/" + str(p).replace("\\", "/"))
    for f in ("index.html", "boot.js"):
        shutil.copy(os.path.join(REPO, "mobile", f), os.path.join(www, f))
    print("wrote", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
