# ammu_api.py

from fastapi import APIRouter
from pydantic import BaseModel
from classifier.logistic_regression import LogisticRegressionClassifier
from ammu_safety import make_llm_reply, check_reply, write_log

# this is my own router just for AMMU
router = APIRouter()

# AMMU uses the same classifier as /classify -- Logistic Regression is the
# team's sole classifier as of the 2026-09-11 decision (see main.py's
# active_classifier comment / the project handoff doc). This used to be
# RuleBasedClassifier(); switched to LogisticRegressionClassifier() on
# 2026-09-23 so AMMU isn't running a retired classifier independently of
# the rest of the app.
#
# KNOWN BEHAVIOR CHANGE vs. rule_based: LogisticRegressionClassifier.classify()
# returns symptoms as symptom_text.split() -- i.e. every raw whitespace-
# separated token from the input, not a filtered list of matched symptom
# keywords the way rule_based's extract_symptoms() did. Two concrete effects:
#   1. list_symptoms() below will now read out ordinary Swahili words
#      (conjunctions, stopwords, etc.) as if they were symptoms, since
#      nothing filters the token list down to a known vocabulary.
#   2. The "len(result['symptoms']) == 0" checks further down, which used
#      to trigger AMMU's "I didn't catch that, can you say more" retry
#      flow whenever rule_based found no recognizable keyword, are now
#      effectively unreachable -- LR's .split() means any non-blank input
#      produces a non-empty symptoms list, so that retry path no longer
#      fires for genuinely unclear input.
# Neither is a safety issue (severity still comes from the trained model,
# and ammu_safety.check_reply() still gates the LLM phrasing), but both
# are real UX regressions worth a follow-up pass once the team has bandwidth.
classifier = LogisticRegressionClassifier()

# ammu replies for each level
replies = {
    "LOW": "This looks minor. Try to rest and drink some water, and keep an eye on how you feel.",
    "MEDIUM": "This is something to watch. Take it easy today. If it gets worse, go see a health worker.",
    "HIGH": "This needs attention. You should see a doctor soon.",
    "CRITICAL": "This looks serious. Please go to a medical facility right away."
}

facility = "Nearest facility: Mbinga District Hospital, about 12 km away."

# these two words should not come together (hot and cold)
bad_pairs = [["joto", "baridi"]]

# memory for the chat
empty_count = 0
confirm_asked = False


def has_contradiction(text):
    text = text.lower()
    for pair in bad_pairs:
        if pair[0] in text and pair[1] in text:
            return True
    return False


def list_symptoms(items):
    # make the words look nicer
    words = []
    for s in items:
        words.append(s.replace("_", " "))

    if len(words) == 1:
        return words[0]

    last = words[-1]
    rest = ", ".join(words[:-1])
    return rest + " and " + last


class UserText(BaseModel):
    user_text: str


@router.post("/ammu/respond")
def ammu_respond(data: UserText):
    global empty_count, confirm_asked

    text = data.user_text.strip()

    # nothing typed
    if text == "":
        empty_count = empty_count + 1
        if empty_count >= 2:
            empty_count = 0
            return {"reply": "Okay, I will wait. Say Hi AMMU when you are ready.", "severity": None}
        return {"reply": "Sorry, I did not catch that. Can you tell me how you are feeling?", "severity": None}

    # hot and cold at the same time
    if has_contradiction(text):
        if confirm_asked == False:
            confirm_asked = True
            return {"reply": "Just to make sure I understood, you said you feel hot and also cold? Can you say that again for me?", "severity": None}
        confirm_asked = False
        return {"reply": "I want to make sure you are okay. Since I am not fully sure what is going on, it is best to see a health worker.", "severity": None}

    confirm_asked = False

    # ask the classifier
    result = classifier.classify(text)

    # no symptoms found
    if len(result["symptoms"]) == 0:
        empty_count = empty_count + 1
        if empty_count >= 2:
            empty_count = 0
            return {"reply": "It is okay if it is hard to explain. If you keep feeling bad, please rest, and see a health worker if it does not get better.", "severity": None}
        return {"reply": "Sorry, I did not catch that. Can you tell me more? For example, do you have a fever, a cough, or pain somewhere?", "severity": None}

    empty_count = 0

    severity = result["severity"]

    # this is the fixed reply. we always build it, and use it as the backup.
    fixed_reply = ""
    if len(result["symptoms"]) >= 2:
        fixed_reply = "Okay, so you have " + list_symptoms(result["symptoms"]) + ". Let me check that for you.\n\n"

    fixed_reply = fixed_reply + replies[severity]
    fixed_reply = fixed_reply + "\n\nReason: " + result["reason"]

    if severity == "HIGH" or severity == "CRITICAL":
        fixed_reply = fixed_reply + "\n\n" + facility

    fixed_reply = fixed_reply + "\n\nRemember, I am not a doctor. For serious problems please see a real health worker."

    # now try the llm. if anything goes wrong, we use the fixed reply.
    final_reply = fixed_reply

    try:
        llm_reply = make_llm_reply(severity, result["symptoms"], result["reason"], facility)
        passed = check_reply(llm_reply, severity, result["reason"])
        write_log(text, llm_reply, passed)
        if passed == True:
            final_reply = llm_reply
    except:
        final_reply = fixed_reply

    return {"reply": final_reply, "severity": severity}
