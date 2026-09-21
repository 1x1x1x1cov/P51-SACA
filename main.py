from fastapi import FastAPI
from pydantic import BaseModel
from classifier.rule_based import RuleBasedClassifier

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


# Active classifier for this endpoint.
active_classifier = RuleBasedClassifier()


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
