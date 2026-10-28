"""
Swahili text -> v2 symptom codes, and the red-flag floor.

The v2 training data (dataset_v2/saca_v2_train.csv) is made of symptom *codes*
("high_fever", "chest_pain", ...), not sentences. keywords.py turns Swahili
phrases into the team's own codes (124 of them); dataset_v2/code_crosswalk.csv
maps those to the v2 vocabulary. dataset_v2/red_flags.csv holds the red-flag
rules (WHO ETAT / IMCI danger signs, DRAFT -- clinician review needed).

read_swahili() consumes each matched phrase so the words it explained are not
later reported as "not understood". A phrase whose team code has no v2
equivalent (e.g. "nyoka" = snake) is returned in `unmapped`: the system knows
the word but cannot rate it, so the caller must treat it as not understood.

read_input() reads English as well (ENGLISH_PHRASES below), because the LLM
extractor that was meant to turn English text into codes is still a placeholder.
English is matched on whole words only, phrase by phrase, longest first. It does
NOT understand negation: "no fever" and "no chest pain" are still read as fever and
chest pain. That errs towards a higher severity, never a lower one.
"""

import csv
import os
import re
import sys
from collections import namedtuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from keywords import SYMPTOM_MAP  # noqa: E402

DATASET_V2_DIR = os.path.join(_ROOT, "dataset_v2")
CROSSWALK_PATH = os.path.join(DATASET_V2_DIR, "code_crosswalk.csv")
RED_FLAGS_PATH = os.path.join(DATASET_V2_DIR, "red_flags.csv")
NONSPECIFIC_PATH = os.path.join(DATASET_V2_DIR, "nonspecific_symptoms.csv")
NONSPECIFIC_MAX_CODES = 3  # same limit the dataset builder uses for partial presentations

RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# positions: {code: index in the (lower-cased) input where it was first found}. Matched
# phrases are blanked with spaces of the same length, so indexes stay valid.
Reading = namedtuple("Reading", "codes unmapped residual positions")

_crosswalk = None
_rules = None
_nonspecific = None


def _load_crosswalk():
    global _crosswalk
    if _crosswalk is None:
        with open(CROSSWALK_PATH, newline="", encoding="utf-8") as f:
            _crosswalk = {
                r["team_code"]: [c for c in r["v2_codes"].split("+") if c]
                for r in csv.DictReader(f)
            }
    return _crosswalk


def _load_rules():
    global _rules
    if _rules is None:
        with open(RED_FLAGS_PATH, newline="", encoding="utf-8") as f:
            _rules = [
                (r["rule_id"], frozenset(r["codes"].split(";")), r["min_tier"])
                for r in csv.DictReader(f)
            ]
    return _rules


def only_nonspecific(codes):
    """True when `codes` is a short list (<= 3) made only of symptoms that fit very
    many conditions (dataset_v2/nonspecific_symptoms.csv). The same rule the
    dataset builder applies to its labels: such a set is capped at MEDIUM."""
    global _nonspecific
    if _nonspecific is None:
        with open(NONSPECIFIC_PATH, newline="", encoding="utf-8") as f:
            _nonspecific = {r["code"] for r in csv.DictReader(f)}
    return 0 < len(codes) <= NONSPECIFIC_MAX_CODES and set(codes) <= _nonspecific


def crosswalk_targets():
    """Every v2 code the crosswalk can emit."""
    return {c for cs in _load_crosswalk().values() for c in cs}


def red_flag_codes():
    """Every code that appears in a red-flag rule."""
    return {c for _, cs, _ in _load_rules() for c in cs}


def read_swahili(text):
    """Match Swahili phrases in `text`.

    Returns Reading(codes, unmapped, residual):
      codes     v2 codes found (order of discovery, no duplicates)
      unmapped  matched phrases whose team code has no v2 equivalent
      residual  `text` with every matched phrase blanked out
    Longer phrases are matched first and consume their text, so
    "kukohoa damu" yields haemoptysis only, not cough + blood.
    """
    xw = _load_crosswalk()
    residual = text.lower()
    codes, unmapped, positions = [], [], {}
    for phrase in sorted(SYMPTOM_MAP, key=len, reverse=True):
        at = residual.find(phrase)
        if at >= 0:
            residual = residual.replace(phrase, " " * len(phrase))
            mapped = xw.get(SYMPTOM_MAP[phrase], [])
            if not mapped:
                unmapped.append(phrase)
            for c in mapped:
                if c not in codes:
                    codes.append(c)
                    positions[c] = at
    return Reading(codes, unmapped, residual, positions)


def red_flag_floor(codes):
    """Highest-tier red-flag rule satisfied by `codes`.

    Returns (severity or None, [rule_ids of every matching rule]).
    """
    have = set(codes)
    hit = [(RANK[t], rid) for rid, cs, t in _load_rules() if cs <= have]
    if not hit:
        return None, []
    top = max(r for r, _ in hit)
    severity = next(k for k, v in RANK.items() if v == top)
    return severity, [rid for _, rid in sorted(hit, reverse=True)]


# --------------------------------------------------------------------------
# English phrases -> v2 codes.  Longest phrase wins and consumes its text.
# Every target must be a v2 vocabulary code (tests/test_v2_normalisation.py checks).
# --------------------------------------------------------------------------
ENGLISH_PHRASES = {
    # emergency / danger signs
    "unconscious": ["coma"], "unresponsive": ["coma"], "passed out": ["coma"],
    "not waking up": ["coma"], "will not wake up": ["coma"], "won't wake up": ["coma"],
    "cannot be woken": ["coma"], "can't be woken": ["coma"], "in a coma": ["coma"],
    "collapsed": ["altered_sensorium"], "confused": ["altered_sensorium"],
    "confusion": ["altered_sensorium"], "disoriented": ["altered_sensorium"],
    "delirious": ["altered_sensorium"], "hallucinating": ["altered_sensorium"],
    "not making sense": ["altered_sensorium"],
    "convulsion": ["convulsions"], "convulsions": ["convulsions"], "convulsing": ["convulsions"],
    "seizure": ["convulsions"], "seizures": ["convulsions"], "having a fit": ["convulsions"],
    "having fits": ["convulsions"], "fitting": ["convulsions"],
    "blue lips": ["cyanosis"], "bluish lips": ["cyanosis"], "turning blue": ["cyanosis"],
    "blue skin": ["cyanosis"], "cyanosis": ["cyanosis"],
    "severe difficulty breathing": ["severe_respiratory_distress"],
    "struggling to breathe": ["severe_respiratory_distress"], "gasping": ["severe_respiratory_distress"],
    "not breathing": ["severe_respiratory_distress"], "stopped breathing": ["severe_respiratory_distress"],
    "chest indrawing": ["severe_respiratory_distress"], "grunting": ["severe_respiratory_distress"],
    "stridor": ["stridor"], "noisy breathing": ["stridor"],
    "purpuric rash": ["purpuric_rash"], "purple spots": ["purpuric_rash"],
    "non-blanching rash": ["purpuric_rash"],
    "heavy bleeding": ["uncontrolled_bleeding"], "bleeding heavily": ["uncontrolled_bleeding"],
    "bleeding a lot": ["uncontrolled_bleeding"], "uncontrolled bleeding": ["uncontrolled_bleeding"],
    "bleeding that won't stop": ["uncontrolled_bleeding"], "bleeding that will not stop": ["uncontrolled_bleeding"],
    "haemorrhage": ["uncontrolled_bleeding"], "hemorrhage": ["uncontrolled_bleeding"],
    "heavy vaginal bleeding": ["uncontrolled_bleeding"], "bleeding after delivery": ["uncontrolled_bleeding"],
    "bleeding after birth": ["uncontrolled_bleeding"], "bleeding in pregnancy": ["uncontrolled_bleeding"],
    "cold hands and feet": ["cold_extremities"], "cold hands": ["cold_extremities"],
    "cold feet": ["cold_extremities"], "cold extremities": ["cold_extremities"],
    "cannot drink": ["unable_to_drink"], "can't drink": ["unable_to_drink"],
    "unable to drink": ["unable_to_drink"], "not able to drink": ["unable_to_drink"],
    "refusing to drink": ["unable_to_drink"], "not drinking": ["unable_to_drink"],
    "won't drink": ["unable_to_drink"],
    "cannot breastfeed": ["unable_to_breastfeed"], "can't breastfeed": ["unable_to_breastfeed"],
    "unable to breastfeed": ["unable_to_breastfeed"], "not breastfeeding": ["unable_to_breastfeed"],
    "not feeding": ["unable_to_breastfeed"],
    "vomiting everything": ["vomits_everything"], "vomits everything": ["vomits_everything"],
    "cannot keep anything down": ["vomits_everything"], "can't keep anything down": ["vomits_everything"],
    "vomiting blood": ["stomach_bleeding"], "vomit blood": ["stomach_bleeding"],
    "vomited blood": ["stomach_bleeding"], "blood in vomit": ["stomach_bleeding"],
    "black stools": ["stomach_bleeding"], "black stool": ["stomach_bleeding"],
    "black tarry stool": ["stomach_bleeding"],
    "weakness on one side": ["weakness_of_one_body_side"], "weak on one side": ["weakness_of_one_body_side"],
    "one side weak": ["weakness_of_one_body_side"], "one-sided weakness": ["weakness_of_one_body_side"],
    "face drooping": ["weakness_of_one_body_side"], "drooping face": ["weakness_of_one_body_side"],
    "facial droop": ["weakness_of_one_body_side"],
    "slurred speech": ["slurred_speech"], "slurring": ["slurred_speech"],
    "difficulty speaking": ["slurred_speech"], "trouble speaking": ["slurred_speech"],
    "stiff neck": ["stiff_neck"], "neck stiffness": ["stiff_neck"], "neck is stiff": ["stiff_neck"],
    "rigid abdomen": ["abdominal_rigidity"], "hard abdomen": ["abdominal_rigidity"],
    # breathing / chest / heart
    "cannot breathe": ["breathlessness"], "can't breathe": ["breathlessness"], "cant breathe": ["breathlessness"],
    "unable to breathe": ["breathlessness"], "difficulty breathing": ["breathlessness"],
    "trouble breathing": ["breathlessness"], "hard to breathe": ["breathlessness"],
    "short of breath": ["breathlessness"], "shortness of breath": ["breathlessness"],
    "out of breath": ["breathlessness"], "breathless": ["breathlessness"],
    "breathlessness": ["breathlessness"], "fast breathing": ["breathlessness"],
    "rapid breathing": ["breathlessness"], "breathing fast": ["breathlessness"],
    "wheezing": ["breathlessness"], "wheeze": ["breathlessness"],
    "slow breathing": ["slow_breathing"], "breathing slowly": ["slow_breathing"],
    "chest pain": ["chest_pain"], "pain in the chest": ["chest_pain"], "pain in my chest": ["chest_pain"],
    "pain in chest": ["chest_pain"], "chest tightness": ["chest_pain"], "tight chest": ["chest_pain"],
    "crushing chest pain": ["chest_pain"], "severe chest pain": ["chest_pain"],
    "fast heart rate": ["fast_heart_rate"], "racing heart": ["fast_heart_rate"], "heart racing": ["fast_heart_rate"],
    "rapid heartbeat": ["fast_heart_rate"], "fast heartbeat": ["fast_heart_rate"], "rapid pulse": ["fast_heart_rate"],
    "palpitations": ["palpitations"], "heart pounding": ["palpitations"], "heart fluttering": ["palpitations"],
    "weak pulse": ["weak_pulse"],
    "coughing up blood": ["blood_in_sputum"], "coughing blood": ["blood_in_sputum"],
    "cough with blood": ["blood_in_sputum"], "blood in sputum": ["blood_in_sputum"],
    "blood in phlegm": ["blood_in_sputum"], "spitting blood": ["blood_in_sputum"],
    "bloody sputum": ["blood_in_sputum"], "bloody cough": ["blood_in_sputum"],
    "coughed up blood": ["blood_in_sputum"], "coughed blood": ["blood_in_sputum"],
    "coughs up blood": ["blood_in_sputum"], "cough up blood": ["blood_in_sputum"],
    "cough": ["cough"], "coughing": ["cough"], "coughs": ["cough"], "coughed": ["cough"],
    "phlegm": ["phlegm"], "mucus": ["phlegm"], "sore throat": ["throat_irritation"],
    "runny nose": ["runny_nose"], "sneezing": ["continuous_sneezing"],
    "blocked nose": ["congestion"], "nasal congestion": ["congestion"],
    # fever and general
    "high fever": ["high_fever"], "high temperature": ["high_fever"], "very high temperature": ["high_fever"],
    "burning up": ["high_fever"],
    "mild fever": ["mild_fever"], "low grade fever": ["mild_fever"], "fever": ["mild_fever"],
    "feverish": ["mild_fever"], "temperature": ["mild_fever"],
    "chills": ["chills"], "shivering": ["shivering"], "rigors": ["shivering"],
    "sweating": ["sweating"], "night sweats": ["sweating"], "sweats": ["sweating"],
    "headache": ["headache"], "head ache": ["headache"], "head pain": ["headache"],
    "photophobia": ["photophobia"], "sensitive to light": ["photophobia"], "light hurts": ["photophobia"],
    "neck pain": ["neck_pain"],
    "lethargic": ["lethargy"], "lethargy": ["lethargy"], "very sleepy": ["lethargy"], "drowsy": ["lethargy"],
    "floppy": ["lethargy"], "limp": ["lethargy"], "too weak to move": ["lethargy"],
    "fatigue": ["fatigue"], "tired": ["fatigue"], "tiredness": ["fatigue"], "exhausted": ["fatigue"],
    "malaise": ["malaise"], "weakness": ["muscle_weakness"],
    "weak arms": ["weakness_in_limbs"], "weak legs": ["weakness_in_limbs"],
    "weakness in arms": ["weakness_in_limbs"], "weakness in legs": ["weakness_in_limbs"],
    "weak limbs": ["weakness_in_limbs"], "limb weakness": ["weakness_in_limbs"],
    "loss of balance": ["loss_of_balance"], "losing balance": ["loss_of_balance"],
    "unsteady": ["unsteadiness"], "dizzy": ["dizziness"], "dizziness": ["dizziness"],
    "lightheaded": ["dizziness"], "light-headed": ["dizziness"],
    "spinning": ["spinning_movements"], "vertigo": ["spinning_movements"],
    "cannot sit": ["unable_to_sit"], "unable to sit": ["unable_to_sit"],
    "cannot stand": ["unable_to_stand"], "unable to stand": ["unable_to_stand"],
    "cannot walk": ["unable_to_walk"], "unable to walk": ["unable_to_walk"],
    # stomach / gut / urine
    "vomiting": ["vomiting"], "vomit": ["vomiting"], "vomits": ["vomiting"], "vomited": ["vomiting"],
    "throwing up": ["vomiting"], "threw up": ["vomiting"],
    "nausea": ["nausea"], "nauseous": ["nausea"], "feel sick": ["nausea"], "feeling sick": ["nausea"],
    "bloody diarrhoea": ["bloody_stool", "diarrhoea"], "bloody diarrhea": ["bloody_stool", "diarrhoea"],
    "blood in stool": ["bloody_stool"], "blood in stools": ["bloody_stool"],
    "bloody stool": ["bloody_stool"], "bloody stools": ["bloody_stool"],
    "diarrhoea": ["diarrhoea"], "diarrhea": ["diarrhoea"], "loose stools": ["diarrhoea"],
    "loose stool": ["diarrhoea"], "watery stools": ["diarrhoea"],
    "constipation": ["constipation"], "constipated": ["constipation"],
    "abdominal pain": ["abdominal_pain"], "stomach pain": ["stomach_pain"], "stomach ache": ["stomach_pain"],
    "stomachache": ["stomach_pain"], "pain in my stomach": ["stomach_pain"],
    "belly pain": ["belly_pain"], "tummy pain": ["belly_pain"], "tummy ache": ["belly_pain"],
    "pain in the belly": ["belly_pain"],
    "loss of appetite": ["loss_of_appetite"], "no appetite": ["loss_of_appetite"],
    "poor appetite": ["loss_of_appetite"], "not eating": ["loss_of_appetite"],
    "weight loss": ["weight_loss"], "losing weight": ["weight_loss"], "lost weight": ["weight_loss"],
    "dehydrated": ["dehydration"], "dehydration": ["dehydration"], "dry mouth": ["dehydration"],
    "very thirsty": ["dehydration"], "extreme thirst": ["dehydration"], "no urine": ["dehydration"],
    "not passing urine": ["dehydration"], "passing little urine": ["dehydration"],
    "sunken eyes": ["sunken_eyes"], "eyes sunken": ["sunken_eyes"],
    "dark urine": ["dark_urine"], "blood in urine": ["haematuria"],
    "burning urination": ["burning_micturition"], "burning when urinating": ["burning_micturition"],
    "painful urination": ["burning_micturition"], "pain when urinating": ["burning_micturition"],
    "frequent urination": ["polyuria"], "passing a lot of urine": ["polyuria"],
    "yellow eyes": ["yellowing_of_eyes"], "yellow skin": ["yellowish_skin"], "jaundice": ["yellowish_skin"],
    # skin / eyes / body
    "itching": ["itching"], "itchy": ["itching"], "skin rash": ["skin_rash"], "rash": ["skin_rash"],
    "red spots on skin": ["red_spots_over_body"], "red eyes": ["redness_of_eyes"],
    "watery eyes": ["watering_from_eyes"], "blurred vision": ["blurred_and_distorted_vision"],
    "blurry vision": ["blurred_and_distorted_vision"], "visual disturbance": ["visual_disturbances"],
    "seeing spots": ["visual_disturbances"],
    "swollen legs": ["swollen_legs"], "swollen feet": ["swollen_legs"], "swelling of legs": ["swollen_legs"],
    "puffy face": ["puffy_face_and_eyes"], "swollen face": ["puffy_face_and_eyes"],
    "joint pain": ["joint_pain"], "painful joints": ["joint_pain"],
    "muscle pain": ["muscle_pain"], "body aches": ["muscle_pain"], "body pain": ["muscle_pain"],
    "muscle aches": ["muscle_pain"], "myalgia": ["muscle_pain"],
    "back pain": ["back_pain"], "backache": ["back_pain"],
    "low blood sugar": ["irregular_sugar_level"], "high blood sugar": ["irregular_sugar_level"],
    "severe pallor": ["severe_pallor"], "very pale": ["severe_pallor"], "pale palms": ["severe_pallor"],
    "low blood pressure": ["low_blood_pressure"], "high blood pressure": ["high_blood_pressure"],
    "hypertension": ["high_blood_pressure"],
    "gangrene": ["necrosis"], "necrosis": ["necrosis"], "bleeding disorder": ["coagulopathy"],
    "bulging fontanelle": ["bulging_fontanelle"], "soft spot bulging": ["bulging_fontanelle"],
    "kwashiorkor": ["kwashiorkor_signs"], "not growing": ["failure_to_thrive"],
    # injury
    "snake bite": ["snake_bite"], "snakebite": ["snake_bite"], "bitten by a snake": ["snake_bite"],
    "bitten by snake": ["snake_bite"],
    "head injury": ["head_injury"], "hit my head": ["head_injury"], "hit his head": ["head_injury"],
    "hit her head": ["head_injury"], "blow to the head": ["head_injury"],
    "open fracture": ["compound_fracture"], "broken bone": ["fracture"], "broken leg": ["fracture"],
    "broken arm": ["fracture"], "fracture": ["fracture"],
    "burns": ["burns"], "burn": ["burns"], "burnt": ["burns"], "scald": ["burns"],
    "deep wound": ["significant_wound"], "large wound": ["significant_wound"], "gaping wound": ["significant_wound"],
    "minor wound": ["minor_wound"], "small cut": ["minor_wound"], "scratch": ["minor_wound"],
    "wound": ["wound"], "fell down": ["fall"], "fell": ["fall"],
    "assaulted": ["assault"], "beaten": ["assault"], "attacked": ["assault"],
    "road accident": ["trauma"], "accident": ["trauma"], "injured": ["trauma"], "injury": ["trauma"],
    "trauma": ["trauma"],
    # pregnancy / TB / malaria
    "pregnant": ["pregnancy"], "pregnancy": ["pregnancy"],
    "prolonged labour": ["prolonged_labour"], "prolonged labor": ["prolonged_labour"],
    "retained placenta": ["retained_placenta"], "eclampsia": ["eclampsia"],
    "pre-eclampsia": ["pre_eclampsia"], "preeclampsia": ["pre_eclampsia"],
    "contact with tb": ["tb_contact"], "tb contact": ["tb_contact"], "exposed to tuberculosis": ["tb_contact"],
    "confirmed malaria": ["malaria_confirmed"], "malaria positive": ["malaria_confirmed"],
    "positive malaria test": ["malaria_confirmed"],
}

# Words that carry no symptom meaning in English; ignored when listing words "not understood".
EN_FILLER_WORDS = frozenset({
    "patient", "complains", "complaining", "complaint", "suffering", "feeling", "feels",
    "felt", "also", "since", "today", "yesterday", "child", "baby", "man", "woman",
    "please", "help", "has", "had", "having", "been", "get", "getting", "got",
    "just", "only", "mild", "slight", "slightly", "little", "bit", "keeps", "morning", "evening",
})

_EN_ORDER = sorted(ENGLISH_PHRASES, key=len, reverse=True)
_EN_RE = {p: re.compile(r"(?<![a-z_])" + re.escape(p) + r"(?![a-z_])") for p in ENGLISH_PHRASES}


def read_english(text):
    """Whole-word English phrase matching. Returns Reading(codes, [], residual)."""
    residual = text.lower().replace("\u2019", "'")
    codes, positions = [], {}
    for phrase in _EN_ORDER:
        m = _EN_RE[phrase].search(residual)
        if m:
            at = m.start()
            residual = _EN_RE[phrase].sub(lambda mm: " " * len(mm.group(0)), residual)
            for c in ENGLISH_PHRASES[phrase]:
                if c not in codes:
                    codes.append(c)
                    positions[c] = at
    return Reading(codes, [], residual, positions)


def read_input(text):
    """English phrases first (whole-word, precise), then Swahili on what is left.

    Returns Reading(codes, unmapped, residual); `residual` is the text with every
    matched phrase blanked out, for the caller to tokenise.
    """
    en = read_english(text)
    sw = read_swahili(en.residual)
    codes = list(en.codes)
    positions = dict(en.positions)
    for c in sw.codes:
        if c not in codes:
            codes.append(c)
            positions[c] = sw.positions[c]
    return Reading(codes, sw.unmapped, sw.residual, positions)
