from fastapi import FastAPI
from pydantic import BaseModel
from classifier.logistic_regression import LogisticRegressionClassifier

from database import (
    init_db,
    save_session,
    get_all_sessions,
    get_unsynced_sessions,
    mark_synced
)

from keywords import SYMPTOM_MAP, SYMPTOM_DESCRIPTIONS
from fastapi.middleware.cors import CORSMiddleware
from ammu_api import router as ammu_router
from fastapi.responses import FileResponse


app = FastAPI(title="SACA - Smart Adaptive Clinical Assistant")
app.include_router(ammu_router)


# Active classifier for this endpoint. Logistic Regression is the sole
# classifier per the team's 2026-09-11 decision (see the project handoff
# doc's "TEAM AND SCOPE CHANGE" section): SVM was dropped (predicts
# identically to LR, LR has a native confidence interface), Random Forest
# was cancelled, and rule_based.py was explicitly retired from the app --
# not kept even as a safety-net check, a tradeoff the team weighed and
# accepted. rule_based.py, rule_based_en.py and svm.py stay in classifier/
# for score_classifiers.py's comparison scoring (that's a real, separate
# purpose, not dead code), but this is the only classifier the live
# /classify endpoint (and the AMMU endpoint below) uses.
#
# NOTE (2026-09-23): this line was previously reverted back to
# RuleBasedClassifier() by a bad merge (commit a236f56) that pulled in
# Shayan's AMMU branch, which had forked from a commit predating this
# decision. Fixed again here -- if you're reading this while investigating
# another regression, check `git log --graph -- main.py` for a repeat.
#
# Trained eagerly here (not lazily on first request) so a missing/bad
# saca_train.csv fails loudly at startup instead of on someone's first
# API call.
active_classifier = LogisticRegressionClassifier()
active_classifier.train()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


init_db()


class SymptomInput(BaseModel):
    symptom_text: str


class SyncConfirmRequest(BaseModel):
    session_ids: list[int]


@app.post("/classify")
def classify_symptoms(data: SymptomInput):

    result = active_classifier.classify(data.symptom_text)

    save_session(
        symptom_text=data.symptom_text,
        symptoms=result["symptoms"],
        severity=result["severity"],
        severity_sw=result["severity_sw"],
        reason=result["reason"]
    )

    return result


@app.get("/sessions")
def get_sessions():

    rows = get_all_sessions()

    return [
        {
            "id": row[0],
            "symptom_text": row[1],
            "symptoms_detected": row[2],
            "severity": row[3],
            "severity_sw": row[4],
            "reason": row[5],
            "timestamp": row[6],
            "synced": bool(row[7]),
            "synced_at": row[8]
        }
        for row in rows
    ]


@app.get("/sync/pending")
def get_pending_sync():

    rows = get_unsynced_sessions()

    return [
        {
            "id": row[0],
            "symptom_text": row[1],
            "symptoms_detected": row[2],
            "severity": row[3],
            "severity_sw": row[4],
            "reason": row[5],
            "timestamp": row[6],
            "synced": bool(row[7]),
            "synced_at": row[8]
        }
        for row in rows
    ]


@app.post("/sync/confirm")
def confirm_sync(data: SyncConfirmRequest):

    mark_synced(data.session_ids)

    return {
        "synced_count": len(data.session_ids)
    }


@app.get("/keywords")
def get_keywords():

    seen = set()
    result = []

    for sw, code in SYMPTOM_MAP.items():

        if sw not in seen:

            seen.add(sw)

            result.append({
                "sw": sw,
                "en": SYMPTOM_DESCRIPTIONS.get(
                    code,
                    code.replace("_", " ")
                )
            })

    return sorted(result, key=lambda x: x["sw"])


@app.get("/")
def root():
    return {"message": "SACA API is running"}

@app.get("/ammu")
def ammu_page():
    return FileResponse("ammu.html")
