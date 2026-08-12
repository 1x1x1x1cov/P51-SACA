import pandas as pd
import csv

# Load files
df = pd.read_csv("dataset.csv")
severity_df = pd.read_csv("Symptom-severity.csv")

# Build symptom weight lookup
weight_map = dict(zip(severity_df["Symptom"].str.strip(), severity_df["weight"]))

# Symptom columns
symptom_cols = [c for c in df.columns if "Symptom" in c]

def score_to_severity(score):
    if score >= 40:
        return "CRITICAL"
    elif score >= 25:
        return "HIGH"
    elif score >= 13:
        return "MEDIUM"
    else:
        return "LOW"

rows = []
for _, row in df.iterrows():
    disease = str(row["Disease"]).strip()
    symptoms = []
    total_weight = 0

    for col in symptom_cols:
        val = str(row[col]).strip() if pd.notna(row[col]) else ""
        if val and val != "nan":
            clean = val.strip().lower()
            symptoms.append(clean)
            total_weight += weight_map.get(clean, 0)

    if not symptoms:
        continue

    symptom_text = " ".join(symptoms)
    severity = score_to_severity(total_weight)

    rows.append({
        "symptom_text": symptom_text,
        "severity": severity,
        "disease": disease,
        "total_weight": total_weight
    })

with open("saca_dataset.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["symptom_text", "severity", "disease", "total_weight"])
    writer.writeheader()
    writer.writerows(rows)

# Print distribution
result_df = pd.DataFrame(rows)
print(f"Total rows: {len(rows)}")
print(result_df["severity"].value_counts())
print(result_df.head())