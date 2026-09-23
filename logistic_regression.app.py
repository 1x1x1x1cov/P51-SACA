from flask import Flask, render_template, request

from classifier.pipeline import SACAPipeline
from classifier.llm_extractor import extract_symptoms


app = Flask(__name__)

# Create the SACA classification pipeline
pipeline = SACAPipeline(
    extractor=extract_symptoms
)


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


if __name__ == "__main__":
    app.run(debug=True)