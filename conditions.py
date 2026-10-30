"""
"Possible conditions" for the SACA result screen.

WHAT IT DOES
Given the symptom codes SACA recognised, it scores each of the 41 diseases in the Kaggle "Disease Symptom
Prediction" file (dataset.csv) and returns the top matches with a match percentage.

HOW
  * Each disease's profile comes from dataset.csv (distinct rows only; the file repeats rows). Multinomial Naive
    Bayes: P(symptom | disease) = the symptom's share of all symptom mentions for that disease, Laplace-smoothed
    (ALPHA), so diseases with long symptom lists are not favoured.
  * Presence-only: only the symptoms the person HAS are scored. Symptoms they did not mention are ignored,
    because a person tapping 2-3 buttons has not said "no" to everything else.
  * Uniform prior over the 41 diseases (the file has the same number of rows per disease, so it carries no real
    prevalence information).
  * The scores go through a softmax with a temperature (TEMPERATURE). The temperature was tuned on simulated partial
    presentations (see evaluate()) so the percentages are not wildly over-confident.

WHAT IT IS NOT
  * NOT a diagnosis. The list is fixed (41 adult-oriented diseases from a public Kaggle dataset of unknown clinical
    provenance). It has no knowledge of anything outside that list, of age, sex, season, or local prevalence.
  * The match percentage means "how well these symptoms fit this disease's profile compared with the other 40". It is
    not the chance that the person has the disease.
  * It does NOT change the triage level. Severity comes only from the triage pipeline (model + safety rules).
"""
import csv
import math
import os
import random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.csv")
URGENCY = os.path.join(HERE, "dataset_v2", "disease_urgency.csv")

ALPHA = 0.5          # Laplace smoothing
MODEL_KIND = "multinomial"
TEMPERATURE = 1.0    # softmax temperature, chosen on purpose ABOVE the simulation optimum (see below)
# Evaluation (python conditions.py), 6,080 simulated partial presentations, 2-4 symptoms from the disease's own
# profile plus one random unrelated symptom 30 % of the time, leave-one-row-out (checked 2026-10-29):
#   multinomial: top-1 0.841, top-3 0.972 (temperature does not change the ranking)
#                T=0.5 ECE 0.030 (best calibrated on the simulation), T=1.0 ECE 0.156 (UNDER-confident there)
#   bernoulli:   top-1 0.800, top-3 0.951
# The simulation draws symptoms from the same 41 profiles, so it is far easier than real patients. We use T=1.0 so
# that the percentages lean low rather than high on real input. These numbers are NOT real-world accuracy.
TOP_N = 3
MIN_SHOW = 0.05      # do not show matches under 5 %

# Clean display names (the source file has typos) and draft Swahili names (NOT native-speaker checked).
DISPLAY = {
    "(vertigo) Paroymsal  Positional Vertigo": ("Positional vertigo (dizziness when moving the head)", "Kizunguzungu cha mkao"),
    "AIDS": ("HIV / AIDS", "VVU / UKIMWI"),
    "Acne": ("Acne", "Chunusi"),
    "Alcoholic hepatitis": ("Alcoholic hepatitis (liver damage from alcohol)", "Homa ya ini kutokana na pombe"),
    "Allergy": ("Allergy", "Mzio"),
    "Arthritis": ("Arthritis (joint inflammation)", "Baridi yabisi"),
    "Bronchial Asthma": ("Asthma", "Pumu"),
    "Cervical spondylosis": ("Neck arthritis (cervical spondylosis)", "Uchakavu wa mifupa ya shingo"),
    "Chicken pox": ("Chickenpox", "Tetekuwanga"),
    "Chronic cholestasis": ("Chronic cholestasis (bile flow problem)", "Tatizo la mtiririko wa nyongo"),
    "Common Cold": ("Common cold", "Mafua"),
    "Dengue": ("Dengue fever", "Homa ya dengue"),
    "Diabetes": ("Diabetes", "Kisukari"),
    "Dimorphic hemmorhoids(piles)": ("Haemorrhoids (piles)", "Bawasiri"),
    "Drug Reaction": ("Reaction to a medicine", "Mzio wa dawa"),
    "Fungal infection": ("Fungal skin infection", "Maambukizi ya fangasi kwenye ngozi"),
    "GERD": ("Acid reflux (GERD)", "Kiungulia sugu"),
    "Gastroenteritis": ("Gastroenteritis (stomach and gut infection)", "Maambukizi ya tumbo na utumbo"),
    "Heart attack": ("Heart attack", "Shambulio la moyo"),
    "Hepatitis B": ("Hepatitis B", "Homa ya ini B"),
    "Hepatitis C": ("Hepatitis C", "Homa ya ini C"),
    "Hepatitis D": ("Hepatitis D", "Homa ya ini D"),
    "Hepatitis E": ("Hepatitis E", "Homa ya ini E"),
    "Hypertension": ("High blood pressure", "Shinikizo la juu la damu"),
    "Hyperthyroidism": ("Overactive thyroid", "Tezi dundumio inayofanya kazi kupita kiasi"),
    "Hypoglycemia": ("Low blood sugar", "Sukari ya chini mwilini"),
    "Hypothyroidism": ("Underactive thyroid", "Tezi dundumio isiyofanya kazi vya kutosha"),
    "Impetigo": ("Impetigo (skin infection)", "Maambukizi ya ngozi (impetigo)"),
    "Jaundice": ("Jaundice (yellow skin or eyes)", "Homa ya manjano"),
    "Malaria": ("Malaria", "Malaria"),
    "Migraine": ("Migraine", "Kipandauso"),
    "Osteoarthristis": ("Osteoarthritis (worn joints)", "Uchakavu wa viungo"),
    "Paralysis (brain hemorrhage)": ("Stroke (bleeding in the brain)", "Kiharusi (kuvuja damu kwenye ubongo)"),
    "Peptic ulcer diseae": ("Stomach ulcer", "Vidonda vya tumbo"),
    "Pneumonia": ("Pneumonia", "Nimonia"),
    "Psoriasis": ("Psoriasis", "Psoriasis (ugonjwa wa ngozi)"),
    "Tuberculosis": ("Tuberculosis (TB)", "Kifua kikuu (TB)"),
    "Typhoid": ("Typhoid", "Homa ya matumbo"),
    "Urinary tract infection": ("Urinary tract infection (UTI)", "Maambukizi ya njia ya mkojo (UTI)"),
    "Varicose veins": ("Varicose veins", "Mishipa ya damu iliyovimba miguuni"),
    "hepatitis A": ("Hepatitis A", "Homa ya ini A"),
}

# A person reporting "fever" or "stomach ache" cannot tell which of the dataset's near-duplicate codes applies, so a
# near-synonym gets partial credit (SYNONYM_WEIGHT) when the disease profile has the other code but not this one.
SYNONYMS = {
    "mild_fever": ("high_fever",),
    "high_fever": ("mild_fever",),
    "abdominal_pain": ("stomach_pain", "belly_pain"),
    "stomach_pain": ("abdominal_pain", "belly_pain"),
    "belly_pain": ("abdominal_pain", "stomach_pain"),
}
SYNONYM_WEIGHT = 0.5

TIER_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

_MODEL = None


def _norm(code):
    return code.strip().replace(" ", "")


def _load_rows(path=DATASET):
    """Distinct (disease, frozenset(symptoms)) rows. The file repeats each row many times."""
    seen = set()
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for r in reader:
            if not r:
                continue
            disease = r[0].strip()
            syms = frozenset(_norm(x) for x in r[1:] if x.strip())
            key = (disease, syms)
            if syms and key not in seen:
                seen.add(key)
                rows.append(key)
    return rows


def _load_urgency(path=URGENCY):
    out = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[r["disease"].strip()] = r["tier"].strip()
    return out


def fit(rows, kind=None):
    """
    Return a model dict: per-disease log P(symptom|disease) and the log-prob for symptoms outside the profile.

    kind="multinomial" (default): P(s|d) = (count(s,d) + ALPHA) / (total symptom mentions for d + ALPHA * |vocab|).
        Each reported symptom is treated as one draw from the disease's symptom list, so a disease with a long list
        is not favoured just because it lists more symptoms.
    kind="bernoulli": P(s|d) = (rows of d with s + ALPHA) / (rows of d + 2 * ALPHA). Kept for comparison: it
        favours diseases with long symptom lists (e.g. typhoid over gastroenteritis for diarrhoea + vomiting).
    """
    kind = kind or MODEL_KIND
    counts = defaultdict(lambda: defaultdict(int))
    n_rows = defaultdict(int)
    vocab = set()
    for disease, syms in rows:
        n_rows[disease] += 1
        for s in syms:
            counts[disease][s] += 1
            vocab.add(s)
    logp, unseen = {}, {}
    for d, n in n_rows.items():
        if kind == "bernoulli":
            denom = n + 2 * ALPHA
        else:
            denom = sum(counts[d].values()) + ALPHA * len(vocab)
        logp[d] = {s: math.log((c + ALPHA) / denom) for s, c in counts[d].items()}
        unseen[d] = math.log(ALPHA / denom)
    return {"logp": logp, "unseen": unseen, "vocab": vocab, "diseases": sorted(n_rows), "kind": kind}


def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = fit(_load_rows())
        _MODEL["urgency"] = _load_urgency()
    return _MODEL


def _code_logp(m, disease, code):
    table = m["logp"][disease]
    best = table.get(code, m["unseen"][disease])
    for syn in SYNONYMS.get(code, ()):
        if syn in table:
            best = max(best, table[syn] + math.log(SYNONYM_WEIGHT))
    return best


def scores(codes, model=None, temperature=None):
    """Softmax match scores for all diseases, highest first. Returns [] if no code is in the vocabulary."""
    m = model or _model()
    t = temperature or TEMPERATURE
    known = [c for c in set(codes or []) if c in m["vocab"]]
    if not known:
        return []
    raw = {d: sum(_code_logp(m, d, c) for c in known) for d in m["diseases"]}
    top = max(raw.values())
    exp = {d: math.exp((v - top) / t) for d, v in raw.items()}
    total = sum(exp.values())
    return sorted(((d, exp[d] / total) for d in m["diseases"]), key=lambda x: -x[1])


def possible_conditions(codes, top_n=TOP_N):
    """
    The result-screen list. Each item: disease (source name), name {en, sw}, match (0-1), percent (int),
    tier (draft urgency of the disease), serious (tier HIGH/CRITICAL).
    """
    m = _model()
    known = sorted(c for c in set(codes or []) if c in m["vocab"])
    ranked = scores(codes, m)
    items = []
    for disease, p in ranked[:top_n]:
        if p < MIN_SHOW:
            continue
        en, sw = DISPLAY.get(disease, (disease, disease))
        tier = m["urgency"].get(disease, "")
        items.append({
            "disease": disease,
            "name": {"en": en, "sw": sw},
            "match": p,
            "percent": max(1, int(round(p * 100))),
            "tier": tier,
            "serious": tier in ("HIGH", "CRITICAL"),
        })
    return {"items": items, "used_codes": known, "ignored_codes": sorted(set(codes or []) - set(known))}


def mismatch_warning(conditions, severity):
    """True when a listed condition is usually MORE urgent than the triage result (and has a real share of the match)."""
    level = TIER_ORDER.get(severity, 3)
    for it in conditions.get("items", []):
        if it["match"] >= 0.25 and TIER_ORDER.get(it["tier"], -1) > level:
            return True
    return False


# ---------------------------------------------------------------------------------------------------------------
# Evaluation: simulated partial presentations. Run:  python conditions.py
# ---------------------------------------------------------------------------------------------------------------
def _simulate(rows, n_per_row=20, ks=(2, 3, 4), noise=0.3, seed=7):
    rng = random.Random(seed)
    vocab = sorted({s for _, syms in rows for s in syms})
    cases = []
    for i, (disease, syms) in enumerate(rows):
        syms = sorted(syms)
        for _ in range(n_per_row):
            k = min(rng.choice(ks), len(syms))
            pick = set(rng.sample(syms, k))
            if rng.random() < noise:               # one unrelated symptom, like a real person adds
                pick.add(rng.choice(vocab))
            cases.append((i, disease, pick))
    return cases


def evaluate(temperatures=(0.5, 1.0, 1.5, 2.0, 3.0), kind=None):
    """Leave-one-row-out: the row a case is drawn from is removed from the profile before scoring."""
    rows = _load_rows()
    cases = _simulate(rows)
    by_row = defaultdict(list)
    for case in cases:
        by_row[case[0]].append(case)
    results = {}
    for t in temperatures:
        top1 = top3 = 0
        nll = 0.0
        bins = defaultdict(lambda: [0, 0.0, 0])  # bucket -> [n, sum_conf, correct]
        for i, cs in by_row.items():
            model = fit(rows[:i] + rows[i + 1:], kind)
            for _, disease, pick in cs:
                ranked = scores(pick, model, t)
                names = [d for d, _ in ranked]
                probs = dict(ranked)
                top1 += names[0] == disease
                top3 += disease in names[:3]
                nll -= math.log(max(probs.get(disease, 1e-12), 1e-12))
                conf = ranked[0][1]
                b = min(int(conf * 10), 9)
                bins[b][0] += 1
                bins[b][1] += conf
                bins[b][2] += names[0] == disease
        n = len(cases)
        ece = sum(abs(v[1] / v[0] - v[2] / v[0]) * v[0] / n for v in bins.values() if v[0])
        results[t] = {"n": n, "top1": top1 / n, "top3": top3 / n, "nll": nll / n, "ece": ece}
    return results


if __name__ == "__main__":
    for kind in ("multinomial", "bernoulli"):
        for t, r in evaluate(kind=kind).items():
            print(f"{kind:<11} T={t:<4} n={r['n']} top1={r['top1']:.3f} top3={r['top3']:.3f} "
                  f"NLL={r['nll']:.3f} ECE={r['ece']:.3f}")
