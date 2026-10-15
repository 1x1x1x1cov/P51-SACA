#!/usr/bin/env python3
"""
Build the SACA v2 training / test data.

Run from inside dataset_v2/.   Inputs:
    ../dataset.csv         Kaggle disease -> symptom rows (4,920)
    disease_urgency.csv    DRAFT urgency tier per disease   (editable)
    red_flags.csv          DRAFT red-flag rules             (editable)
Outputs:
    saca_v2_train.csv / saca_v2_test.csv   columns: symptom_text,severity,source,n_symptoms
    saca_v2_all.csv                        every distinct symptom set with its label + reason
    build_report_v2.txt                    counts, checks, label-policy sensitivity

Label of a symptom set S  =  max( red-flag floor(S), disease tier(S) )
  red-flag floor  : highest min_tier of any rule in red_flags.csv whose codes are all in S
  disease tier    : S equals an observed Kaggle row-set  -> max tier of the diseases that produced it
                    otherwise S is a partial presentation -> LOWEST tier among the diseases whose symptom
                    pool contains S (policy 'min': a vague symptom set is only as urgent as the least
                    urgent thing it could be; danger comes from red_flags.csv). 'median' (lower median)
                    and 'max' are reported as sensitivity. Run `python build_dataset_v2.py median` to switch.
                    no disease contains S                 -> LOW (only the red-flag floor applies)

Nothing here reads or writes saca_train.csv / saca_test.csv.
"""
import itertools, os, random, re, sys
from collections import defaultdict
import pandas as pd

SEED = 42
DATASET = "../dataset.csv" if os.path.exists("../dataset.csv") else "dataset.csv"
RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
NAME = {v: k for k, v in RANK.items()}
ALIAS = {"dischromic__patches": "dischromic_patches",
         "spotting__urination": "spotting_urination",
         "foul_smell_of_urine": "foul_smell_ofurine"}
NOT_SYMPTOMS = {"prognosis"}
MAX_SUBSET = 3          # partial presentations of up to 3 symptoms
NOISE_CODES = ["headache", "nausea", "fatigue", "cough", "vomiting", "abdominal_pain",
               "back_pain", "dizziness", "malaise", "loss_of_appetite", "muscle_pain", "joint_pain"]


def norm(x):
    x = re.sub(r"\s+", "_", str(x).strip().lower())
    return ALIAS.get(x, x)


def canon(codes):
    return tuple(sorted(set(codes)))


def lower_median(tiers):
    t = sorted(RANK[x] for x in tiers)
    return NAME[t[(len(t) - 1) // 2]]


def main(policy="min"):
    random.seed(SEED)
    df = pd.read_csv(DATASET)
    tiers = pd.read_csv("disease_urgency.csv")
    rules = pd.read_csv("red_flags.csv")
    sym_cols = [c for c in df.columns if c.startswith("Symptom")]
    tier_of = {d.strip(): t for d, t in zip(tiers.disease, tiers.tier)}
    df["Disease"] = df["Disease"].str.strip()
    missing = set(df.Disease) - set(tier_of)
    assert not missing, f"diseases without a tier: {missing}"

    # ---- observed combos and disease pools --------------------------------
    observed = defaultdict(set)        # canonical combo -> diseases that produced it
    pool = defaultdict(set)            # disease -> union of its symptoms
    for _, r in df.iterrows():
        s = canon(norm(v) for v in r[sym_cols].dropna() if norm(v) not in NOT_SYMPTOMS)
        if not s:
            continue
        observed[s].add(r.Disease)
        pool[r.Disease] |= set(s)

    rule_list = [(frozenset(c.split(";")), t, rid) for rid, c, t in zip(rules.rule_id, rules.codes, rules.min_tier)]
    kaggle_codes = {c for p in pool.values() for c in p}
    rule_codes = {c for cs, _, _ in rule_list for c in cs}
    added_codes = sorted(rule_codes - kaggle_codes)

    def floor_of(s):
        fs = set(s)
        hit = [(RANK[t], rid) for cs, t, rid in rule_list if cs <= fs]
        return (max(hit) if hit else (0, ""))

    def disease_component(s, how):
        if s in observed:
            return NAME[max(RANK[tier_of[d]] for d in observed[s])], "observed"
        fs = set(s)
        compat = [d for d, p in pool.items() if fs <= p]
        if not compat:
            return "LOW", "no_disease"
        ts = [tier_of[d] for d in compat]
        if how == "median":
            return lower_median(ts), "partial"
        if how == "min":
            return NAME[min(RANK[t] for t in ts)], "partial"
        return NAME[max(RANK[t] for t in ts)], "partial"

    def label(s, how=policy):
        dt, kind = disease_component(s, how)
        fl, rid = floor_of(s)
        lab = NAME[max(RANK[dt], fl)]
        return lab, kind, rid if fl >= RANK[dt] and fl > 0 else ""

    # ---- candidate symptom sets -------------------------------------------
    cands = {}
    for s in observed:
        cands[s] = "observed"
    for d, p in pool.items():
        for k in range(1, MAX_SUBSET + 1):
            for sub in itertools.combinations(sorted(p), k):
                cands.setdefault(sub, "partial")
    # synthetic red-flag rows (needed for codes absent from Kaggle, and for noise-robustness)
    for cs, t, rid in rule_list:
        base = sorted(cs)
        cands.setdefault(canon(base), "redflag")
        for _ in range(25):
            extra = random.sample(NOISE_CODES, random.choice([1, 2]))
            cands.setdefault(canon(base + extra), "redflag")
        for c in sorted(kaggle_codes):                      # each rule with every other single code once
            if len(base) + 1 <= 5 and random.random() < 0.15:
                cands.setdefault(canon(base + [c]), "redflag")

    rows = []
    for s, src in cands.items():
        lab, kind, rid = label(s)
        rows.append(dict(symptom_text=" ".join(s), severity=lab, source=src if src != "partial" else "partial",
                         n_symptoms=len(s), label_basis=("redflag:" + rid) if rid else kind))
    allr = pd.DataFrame(rows).sort_values("symptom_text").reset_index(drop=True)
    assert allr.symptom_text.is_unique

    # ---- split on distinct symptom sets (no text appears in both files) ---
    rng = random.Random(SEED)
    train_idx, test_idx = [], []
    for sev, g in allr.groupby("severity"):
        idx = list(g.index)
        rng.shuffle(idx)
        cut = int(round(len(idx) * 0.8))
        train_idx += idx[:cut]
        test_idx += idx[cut:]
    train = allr.loc[sorted(train_idx)].reset_index(drop=True)
    test = allr.loc[sorted(test_idx)].reset_index(drop=True)
    assert not (set(train.symptom_text) & set(test.symptom_text))
    # make sure every vocabulary code is in >= 2 training rows (CountVectorizer min_df=2)
    from collections import Counter
    cnt = Counter(c for t in train.symptom_text for c in t.split())
    thin = sorted(c for c in (kaggle_codes | rule_codes) if cnt[c] < 2)
    assert not thin, f"codes in <2 training rows: {thin}"

    train[["symptom_text", "severity", "source", "n_symptoms"]].to_csv("saca_v2_train.csv", index=False)
    test[["symptom_text", "severity", "source", "n_symptoms"]].to_csv("saca_v2_test.csv", index=False)
    allr.to_csv("saca_v2_all.csv", index=False)

    # ---- sensitivity of labels to the partial-presentation policy ----------
    sens = {}
    for how in ("min", "median", "max"):
        sens[how] = pd.Series([label(tuple(t.split()), how)[0] for t in allr.symptom_text]).value_counts().reindex(NAME.values(), fill_value=0)
    diff = sum(label(tuple(t.split()), "min")[0] != label(tuple(t.split()), "max")[0] for t in allr.symptom_text)

    out = []
    out.append(f"distinct symptom sets: {len(allr)}  (train {len(train)}, test {len(test)})")
    out.append(f"vocabulary: {len(kaggle_codes)} Kaggle codes + {len(added_codes)} added red-flag codes: {added_codes}")
    out.append("source counts:\n" + allr.source.value_counts().to_string())
    out.append("label counts (policy=%s):\n%s" % (policy, allr.severity.value_counts().reindex(NAME.values(), fill_value=0).to_string()))
    out.append("train labels:\n" + train.severity.value_counts().reindex(NAME.values(), fill_value=0).to_string())
    out.append("test labels:\n" + test.severity.value_counts().reindex(NAME.values(), fill_value=0).to_string())
    out.append("label counts by partial-presentation policy:\n" + pd.DataFrame(sens).to_string())
    out.append(f"sets whose label differs between 'min' and 'max' policy: {diff} of {len(allr)}")
    out.append("label basis:\n" + allr.label_basis.str.split(":").str[0].value_counts().to_string())
    # observed-combo conflicts (same symptom set, diseases of different tiers)
    conf = [(s, sorted(ds)) for s, ds in observed.items() if len({tier_of[d] for d in ds}) > 1]
    out.append(f"observed combos produced by diseases of different tiers: {len(conf)} of {len(observed)}")
    for s, ds in conf[:15]:
        out.append("   " + " ".join(s) + "  <-  " + ", ".join(f"{d}({tier_of[d]})" for d in ds))
    open("build_report_v2.txt", "w").write("\n\n".join(out) + "\n")
    print("\n\n".join(out))


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
