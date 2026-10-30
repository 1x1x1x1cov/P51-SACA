"""
The question-by-question assessment ("quiz") used by the Start assessment screen.

The screens are:
  1. Who is this for?            (guest: name, date of birth or age, sex; profile: already known)
  2. What symptoms?              big buttons, danger signs first; or type it; or the Body Map
  3. How long?                   used for advice only (the triage model does not use duration)
  4. Danger questions            yes / no; a "yes" adds the matching danger-sign code
  5. What happened?              injury, burn, bite, TB contact; adds codes
  6. Check and submit

Every button maps to a symptom code that the SACA reader already understands (checked in
tests/test_assessment_flow.py), so a tapped answer is never "not understood".
"""

SYMPTOM_BUTTONS = [
    # (code, icon, English label, Swahili label, danger?)
    ("breathlessness", "\U0001F4A8", "Trouble breathing", "Kupumua kwa shida", True),
    ("chest_pain", "\U0001F494", "Chest pain", "Maumivu ya kifua", True),
    ("convulsions", "⚡", "Fits / convulsions", "Degedege", True),
    ("altered_sensorium", "\U0001F635", "Very sleepy or confused", "Usingizi mwingi au kuchanganyikiwa", True),
    ("uncontrolled_bleeding", "\U0001FA78", "Heavy bleeding", "Kutokwa damu nyingi", True),
    ("stomach_bleeding", "\U0001F92E", "Vomiting blood", "Kutapika damu", True),
    ("high_fever", "\U0001F525", "High fever (very hot)", "Homa kali (joto sana)", False),
    ("mild_fever", "\U0001F321️", "Mild fever", "Homa kidogo", False),
    ("headache", "\U0001F915", "Headache", "Maumivu ya kichwa", False),
    ("cough", "\U0001F637", "Cough", "Kikohozi", False),
    ("throat_irritation", "\U0001F5E3️", "Sore throat", "Maumivu ya koo", False),
    ("runny_nose", "\U0001F927", "Runny nose", "Mafua", False),
    ("diarrhoea", "\U0001F6BD", "Diarrhoea", "Kuhara", False),
    ("vomiting", "\U0001F922", "Vomiting", "Kutapika", False),
    ("stomach_pain", "\U0001F61F", "Stomach pain", "Maumivu ya tumbo", False),
    ("chills", "\U0001F976", "Chills / shivering", "Kutetemeka kwa baridi", False),
    ("fatigue", "\U0001F634", "Tired / weak", "Uchovu / udhaifu", False),
    ("muscle_pain", "\U0001F4AA", "Body aches", "Maumivu ya mwili", False),
    ("joint_pain", "\U0001F9B5", "Joint pain", "Maumivu ya viungo", False),
    ("back_pain", "\U0001F64D", "Back pain", "Maumivu ya mgongo", False),
    ("dizziness", "\U0001F4AB", "Dizzy", "Kizunguzungu", False),
    ("skin_rash", "\U0001F534", "Rash", "Vipele", False),
    ("itching", "\U0001F90F", "Itching", "Kuwashwa", False),
    ("burning_micturition", "\U0001F4A7", "Burning when passing urine", "Kuungua wakati wa kukojoa", False),
    ("yellowing_of_eyes", "\U0001F441️", "Yellow eyes", "Macho ya njano", False),
    ("loss_of_appetite", "\U0001F37D️", "Not eating", "Kukosa hamu ya kula", False),
]

DURATIONS = [
    # (value, English, Swahili)
    ("today", "Started today", "Imeanza leo"),
    ("1-3d", "1 to 3 days", "Siku 1 hadi 3"),
    ("4-7d", "4 to 7 days", "Siku 4 hadi 7"),
    ("long", "More than a week", "Zaidi ya wiki moja"),
]

DANGER_QUESTIONS = [
    # (field, code(s) added on "yes", English, Swahili, only_for_young_child)
    ("q_breathing", ("breathlessness",), "Is it hard to breathe, or is the breathing very fast?",
     "Je, ni vigumu kupumua, au anapumua haraka sana?", False),
    ("q_fits", ("convulsions",), "Has there been a fit (convulsion) in this illness?",
     "Je, amepata degedege katika ugonjwa huu?", False),
    ("q_sleepy", ("altered_sensorium",), "Is the person very sleepy, confused, or hard to wake?",
     "Je, ana usingizi mwingi, amechanganyikiwa, au ni vigumu kumwamsha?", False),
    ("q_drink", ("unable_to_drink",), "Is the person unable to drink, or vomiting everything?",
     "Je, hawezi kunywa, au anatapika kila kitu?", False),
    ("q_neck", ("stiff_neck",), "Is the neck stiff (hard to bend the chin to the chest)?",
     "Je, shingo ni ngumu (vigumu kuinamisha kidevu hadi kifuani)?", False),
    ("q_breastfeed", ("unable_to_breastfeed",), "Is the baby unable to breastfeed?",
     "Je, mtoto hawezi kunyonya?", True),
]

CAUSES = [
    # (code, icon, English, Swahili)
    ("trauma", "\U0001F915", "Injury or accident", "Jeraha au ajali"),
    ("fall", "⬇️", "A fall", "Kuanguka"),
    ("head_injury", "\U0001F9E0", "Hit on the head", "Kugongwa kichwani"),
    ("burns", "\U0001F525", "A burn", "Kuungua"),
    ("snake_bite", "\U0001F40D", "Snake bite", "Kuumwa na nyoka"),
    ("wound", "\U0001FA79", "Animal bite or deep cut", "Kuumwa na mnyama au jeraha kubwa"),
    ("tb_contact", "\U0001F465", "Lives with someone who has TB", "Anaishi na mtu mwenye TB"),
]

BUTTON_CODES = {b[0] for b in SYMPTOM_BUTTONS}
CAUSE_CODES = {c[0] for c in CAUSES}
DURATION_VALUES = {d[0] for d in DURATIONS}
MAX_TYPED = 600


BABY_MAX_YEARS = 0  # baby-only questions are asked when the age in whole years is 0 (under 1 year)


def is_baby(age_years):
    return age_years is not None and age_years <= BABY_MAX_YEARS


def build_symptom_text(form, age_years=None):
    """
    Turn the submitted quiz into (text_for_classifier, picked_codes, context, input_mode).

    form: a dict-like with getlist() (Flask's request.form) or a plain dict of lists.
    age_years: the person's age in whole years if known. Baby-only questions (e.g. "unable to breastfeed")
               are ignored unless the person is under 1 year, so a stale answer cannot add a baby danger sign
               to an adult.
    Unknown codes are dropped, so a tampered form cannot inject text other than the typed box.
    """
    def getlist(key):
        if hasattr(form, "getlist"):
            return form.getlist(key)
        value = form.get(key, [])
        return value if isinstance(value, list) else [value]

    def get(key):
        values = getlist(key)
        return values[0] if values else ""

    picked = []
    for code in getlist("symptom"):
        if code in ALLOWED_SYMPTOM_CODES and code not in picked:
            picked.append(code)

    answers = {}
    for field, codes, _en, _sw, child_only in DANGER_QUESTIONS:
        if child_only and not is_baby(age_years):
            continue
        answer = (get(field) or "").strip().lower()
        if answer in ("yes", "no"):
            answers[field] = answer
        if answer == "yes":
            for code in codes:
                if code not in picked:
                    picked.append(code)

    causes = []
    for code in getlist("cause"):
        if code in CAUSE_CODES and code not in picked:
            picked.append(code)
            causes.append(code)

    typed = (get("typed_text") or "").strip()[:MAX_TYPED]
    duration = get("duration")
    duration = duration if duration in DURATION_VALUES else None

    parts = list(picked)
    if typed:
        parts.append(typed)
    text = " ".join(parts).strip()

    mode = get("input_mode")
    if mode == "voice" and not typed:
        mode = ""
    if mode not in ("typed", "bodymap", "pictures", "voice"):
        mode = "pictures" if picked and not typed else "typed"

    context = {
        "duration": duration,
        "danger_answers": answers,
        "causes": causes,
        "typed_text": typed or None,
        "buttons": [c for c in picked if c in ALLOWED_SYMPTOM_CODES],
    }
    return text, picked, context, mode


def duration_group(duration):
    """'long' when the symptoms have lasted more than a week (guidance uses this)."""
    return "long" if duration == "long" else None


# --------------------------------------------------------------------------------------------- Body Map
# Body part -> (code, English, Swahili). Carried over from the original Body Map page (same codes, same Swahili).
BODY_PARTS = [
    # (id, English, Swahili, fill colour) - every part a different colour so it is easy to tell apart
    ("head", "Head", "Kichwa", "#7cb7ff"),
    ("neck", "Neck", "Shingo", "#c4a5ff"),
    ("shoulders", "Shoulders", "Mabega", "#7ddfd0"),
    ("chest", "Chest", "Kifua", "#ff9eb0"),
    ("abdomen", "Belly", "Tumbo", "#ffc27a"),
    ("arm", "Arms", "Mikono", "#9be38f"),
    ("hand", "Hands", "Viganja", "#e3e37a"),
    ("leg", "Legs", "Miguu", "#a8b8ff"),
    ("foot", "Feet", "Nyayo", "#d9b38c"),
    ("general", "Whole body", "Mwili mzima", "#e0e0e0"),
]

BODY_COLORS = {pid: colour for pid, _en, _sw, colour in BODY_PARTS}

BODY_MAP = {
    "head": [("headache", "Headache", "Maumivu ya kichwa"), ("dizziness", "Dizziness", "Kizunguzungu"),
             ("blurred_and_distorted_vision", "Blurry vision", "Uoni hafifu"),
             ("redness_of_eyes", "Red eyes", "Macho mekundu"),
             ("pain_behind_the_eyes", "Pain behind the eyes", "Maumivu nyuma ya macho"),
             ("runny_nose", "Runny nose", "Pua inayotiririka"), ("sinus_pressure", "Sinus pressure", "Shinikizo kwenye sinasi"),
             ("loss_of_smell", "Loss of smell", "Kupoteza uwezo wa kunusa"),
             ("ulcers_on_tongue", "Ulcers on tongue", "Vidonda kwenye ulimi"),
             ("slurred_speech", "Slurred speech", "Usemi usio wazi")],
    "neck": [("neck_pain", "Neck pain", "Maumivu ya shingo"), ("stiff_neck", "Stiff neck", "Shingo kukakamaa"),
             ("throat_irritation", "Sore throat", "Maumivu ya koo"), ("patches_in_throat", "Patches in throat", "Mabaka kwenye koo"),
             ("swelled_lymph_nodes", "Swollen glands", "Tezi zilizovimba"),
             ("enlarged_thyroid", "Swelling at front of neck", "Uvimbe mbele ya shingo")],
    "shoulders": [("joint_pain", "Joint pain", "Maumivu ya viungo"), ("muscle_pain", "Muscle pain", "Maumivu ya misuli"),
                  ("movement_stiffness", "Stiffness", "Kukakamaa"), ("back_pain", "Upper back pain", "Maumivu ya sehemu ya juu ya mgongo")],
    "chest": [("chest_pain", "Chest pain", "Maumivu ya kifua"), ("breathlessness", "Hard to breathe", "Kupumua kwa shida"),
              ("cough", "Cough", "Kikohozi"), ("phlegm", "Phlegm", "Makohozi"),
              ("blood_in_sputum", "Coughing up blood", "Kukohoa damu"),
              ("fast_heart_rate", "Fast heart rate", "Mapigo ya moyo kwenda kasi"),
              ("palpitations", "Heart pounding", "Moyo kudunda kwa nguvu")],
    "abdomen": [("stomach_pain", "Stomach pain", "Maumivu ya tumbo"), ("abdominal_pain", "Belly pain", "Maumivu ya tumbo la chini"),
                ("vomiting", "Vomiting", "Kutapika"), ("nausea", "Feeling sick", "Kichefuchefu"),
                ("diarrhoea", "Diarrhoea", "Kuhara"), ("constipation", "Constipation", "Kufunga choo"),
                ("acidity", "Heartburn", "Kiungulia"), ("indigestion", "Indigestion", "Kukosa kumeng'enya chakula vizuri"),
                ("swelling_of_stomach", "Swollen stomach", "Tumbo kuvimba"),
                ("burning_micturition", "Burning when peeing", "Maumivu wakati wa kukojoa")],
    "arm": [("muscle_pain", "Muscle pain", "Maumivu ya misuli"), ("joint_pain", "Joint pain", "Maumivu ya viungo"),
            ("weakness_in_limbs", "Weakness", "Udhaifu"), ("skin_rash", "Skin rash", "Upele"), ("itching", "Itching", "Kuwashwa")],
    "hand": [("swelling_joints", "Swollen joints", "Viungo vilivyovimba"), ("cold_hands_and_feets", "Cold hands", "Mikono baridi"),
             ("weakness_in_limbs", "Weakness", "Udhaifu"), ("skin_peeling", "Peeling skin", "Ngozi kuchubuka"),
             ("brittle_nails", "Brittle nails", "Kucha zinazovunjika kwa urahisi")],
    "leg": [("knee_pain", "Knee pain", "Maumivu ya goti"), ("hip_joint_pain", "Hip pain", "Maumivu ya nyonga"),
            ("swollen_legs", "Swollen legs", "Miguu iliyovimba"), ("painful_walking", "Pain when walking", "Maumivu wakati wa kutembea"),
            ("muscle_weakness", "Muscle weakness", "Udhaifu wa misuli"), ("cramps", "Cramps", "Kukaza kwa misuli"),
            ("prominent_veins_on_calf", "Veins showing on calf", "Mishipa kuonekana kwenye muundi")],
    "foot": [("painful_walking", "Pain when walking", "Maumivu wakati wa kutembea"),
             ("swelling_joints", "Swollen joints", "Viungo vilivyovimba"), ("cold_hands_and_feets", "Cold feet", "Miguu baridi"),
             ("skin_peeling", "Peeling skin", "Ngozi kuchubuka"), ("loss_of_balance", "Loss of balance", "Kupoteza usawa")],
    "general": [("high_fever", "High fever", "Homa kali"), ("mild_fever", "Mild fever", "Homa ya kiwango cha chini"),
                ("chills", "Chills", "Kutetemeka kwa baridi"), ("fatigue", "Tiredness", "Uchovu"),
                ("sweating", "Sweating", "Kutokwa na jasho"), ("itching", "Itching", "Kuwashwa"), ("skin_rash", "Skin rash", "Upele"),
                ("weight_loss", "Weight loss", "Kupungua uzito"), ("dehydration", "Dehydration", "Upungufu wa maji mwilini")],
}

BODY_MAP_LABELS = {}
for _part, _items in BODY_MAP.items():
    for _code, _en, _sw in _items:
        BODY_MAP_LABELS.setdefault(_code, (_en, _sw))
BODY_MAP_CODES = set(BODY_MAP_LABELS)

# Every code a symptom tile may send: the quiz buttons plus the Body Map.
ALLOWED_SYMPTOM_CODES = BUTTON_CODES | BODY_MAP_CODES


def extra_prefill(prefill):
    """Body Map codes that are not quiz buttons, with labels, so the quiz can show them as already-picked tiles."""
    return [(c, BODY_MAP_LABELS[c][0], BODY_MAP_LABELS[c][1]) for c in prefill
            if c in BODY_MAP_CODES and c not in BUTTON_CODES]
