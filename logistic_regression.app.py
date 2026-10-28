import os
import sys
from flask import Flask, render_template, request, send_from_directory

from classifier.pipeline import SACAPipeline
from classifier.llm_extractor import extract_symptoms
from history import save_analysis, get_history, get_analysis


def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


template_folder = resource_path("templates")


app = Flask(
    __name__,
    template_folder=template_folder
)

# --- IMPORT AND REGISTER THE VOICE BLUEPRINT ---
from voice_flask import voice_bp
app.register_blueprint(voice_bp)

# Create the SACA classification pipeline
pipeline = SACAPipeline(
pipeline = SACAPipeline(
    extractor=extract_symptoms
)
pipeline.classifier.train()


@app.route("/", methods=["GET", "POST"])
def dashboard():
    result = None

    # GET: symptoms imported from the body map
    if request.method == "GET":
        symptom_text = request.args.get(
            "symptom_text",
            ""
        ).strip()

    # POST: symptoms entered into the dashboard form
    else:
        symptom_text = request.form.get(
            "symptom_text",
            ""
        ).strip()

    if symptom_text:
        result = pipeline.classify(symptom_text)

        # Automatically save successful analyses to local history
        if result:
            save_analysis(symptom_text, result)

    return render_template(
        "logistic_dashboard.html",
        result=result,
        symptom_text=symptom_text
    )


# --- ROUTE TO SERVE THE VOICE SCRIPT ---
@app.route('/voice.js')
def serve_voice_js():
    return send_from_directory(os.getcwd(), 'voice_input.js', mimetype='application/javascript')

@app.route("/body-map")
def body_map():
    return render_template("body_map.html")


@app.route("/history")
def history():
    records = get_history()

    return render_template(
        "history.html",
        records=records
    )


@app.route("/history/<int:record_id>")
def history_detail(record_id):
    record = get_analysis(record_id)

    if record is None:
        return "History record not found", 404

    return render_template(
        "history_detail.html",
        record=record
    )

if __name__ == "__main__":
    app.run(
        debug=True
    )
