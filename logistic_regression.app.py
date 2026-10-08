import os
import sys

from flask import Flask, render_template, request

from classifier.pipeline import SACAPipeline
from classifier.llm_extractor import extract_symptoms


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
    app.run(
        debug=True
    )