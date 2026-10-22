import os
from flask import Flask, render_template, request, send_from_directory

from classifier.pipeline import SACAPipeline
from classifier.llm_extractor import extract_symptoms

# --- IMPORT THE VOICE BLUEPRINT ---
from voice_flask import voice_bp

app = Flask(__name__)

# --- REGISTER THE VOICE BLUEPRINT ---
app.register_blueprint(voice_bp)

# Create the SACA classification pipeline
pipeline = SACAPipeline(
    extractor=extract_symptoms
)
pipeline.classifier.train()


@app.route("/", methods=["GET", "POST"])
def dashboard():

    result = None
    symptom_text = ""

    if request.method == "POST":

        symptom_text = request.form.get(
            "symptom_text",
            ""
        )

        if symptom_text.strip():

            result = pipeline.classify(
                symptom_text
            )

    return render_template(
        "logistic_dashboard.html",
        result=result,
        symptom_text=symptom_text
    )


# --- ROUTE TO SERVE THE VOICE SCRIPT ---
@app.route('/voice.js')
def serve_voice_js():
    return send_from_directory(os.getcwd(), 'voice_input.js', mimetype='application/javascript')


if __name__ == "__main__":
    app.run(debug=True)