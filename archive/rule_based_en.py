"""
SACA - English rule-based classifier (interim/demo pipeline)

IMPORTANT: This is an English-language classifier built to work with
the current dataset.csv/saca_dataset.csv, which contains English
symptom terms. This is NOT SACA's production classifier - the real
product classifies Swahili input (see classifier/rule_based.py).

This exists to let the team validate the plug-and-play classifier
architecture and run a fair five-way comparison (rule-based + 4 ML
approaches) against a dataset that's already in a usable state,
while the Swahili translation pipeline is built out separately.

Logic: uses a small set of individually dangerous symptoms as
CRITICAL overrides (coma, chest pain, high fever, etc - mirroring
how classifier/rule_based.py uses CRITICAL_OVERRIDE_KEYWORDS), then
falls back to a symptom-count-based tier for everything else.

Deliberately does NOT use Symptom-severity.csv's weight table or
prepare_dataset.py's scoring thresholds (40/25/13) - reusing that
exact formula would make this classifier trivially recover the
dataset's own label-generation logic rather than making an
independent prediction, which would produce a meaningless 100%
accuracy score rather than a genuine measure of this approach.
"""

from classifier.base import BaseClassifier

# Individually severe symptoms that should push a case to CRITICAL
# regardless of what else is present - chosen for plausible clinical
# urgency (altered consciousness, cardiac/respiratory danger signs),
# independent of the dataset's own weight table.
CRITICAL_OVERRIDES = {
    "coma",
    "chest_pain",
    "high_fever",
    "breathlessness",
    "stomach_bleeding",
    "acute_liver_failure",
    "fluid_overload",
}

HIGH_OVERRIDES = {
    "diarrhoea",
    "vomiting",
    "dehydration",
    "malaise",
    "weakness_in_limbs",
    "spinning_movements",
}


class RuleBasedClassifierEN(BaseClassifier):
    name = "rule_based_en"

    def classify(self, symptom_text: str) -> dict:
        if not symptom_text or not symptom_text.strip():
            return self.build_result(
                "LOW", [], "No symptoms provided - please enter patient symptoms."
            )

        tokens = set(symptom_text.strip().lower().split())

        critical_hits = tokens & CRITICAL_OVERRIDES
        if critical_hits:
            return self.build_result(
                "CRITICAL",
                sorted(tokens),
                f"Critical symptom(s) detected: {', '.join(sorted(critical_hits))}",
            )

        high_hits = tokens & HIGH_OVERRIDES
        if high_hits:
            return self.build_result(
                "HIGH",
                sorted(tokens),
                f"Concerning symptom(s) detected: {', '.join(sorted(high_hits))}",
            )

        # Fall back to symptom count as a rough proxy for severity
        # when no individually dangerous symptom is present - more
        # symptoms reported together suggests a more significant
        # presentation, independent of any per-symptom weight table.
        symptom_count = len(tokens)
        if symptom_count >= 6:
            severity = "MEDIUM"
            reason = f"Multiple symptoms reported ({symptom_count}) - warrants review"
        else:
            severity = "LOW"
            reason = f"Few symptoms reported ({symptom_count})"

        return self.build_result(severity, sorted(tokens), reason)


if __name__ == "__main__":
    classifier = RuleBasedClassifierEN()

    test_inputs = [
        "itching vomiting yellowish_skin nausea loss_of_appetite abdominal_pain yellowing_of_eyes",
        "vomiting breathlessness sweating chest_pain",
        "joint_pain skin_peeling silver_like_dusting small_dents_in_nails",
        "",
        "made_up_symptom_not_real",
    ]

    for text in test_inputs:
        result = classifier.classify(text)
        print(f"Input:    {text}")
        print(f"Severity: {result['severity']}")
        print(f"Reason:   {result['reason']}")
        print()
