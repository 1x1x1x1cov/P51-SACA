"""
SACA - Rule-based keyword classifier

Approach 1 of 5. Uses Swahili keyword matching (via keywords.py) and
a hand-authored decision tree to assign a severity tier. No ML.
This is the baseline against which the other four approaches are
compared.
"""

from classifier.base import BaseClassifier
from keywords import extract_symptoms, CRITICAL_OVERRIDE_KEYWORDS


class RuleBasedClassifier(BaseClassifier):
    name = "rule_based"

    def classify(self, symptom_text: str) -> dict:
        if not symptom_text or not symptom_text.strip():
            return self.build_result(
                "LOW", [], "Hakuna dalili zilizoingizwa — tafadhali ingiza dalili za mgonjwa."
            )

        symptoms = extract_symptoms(symptom_text)

        if not symptoms:
            return self.build_result(
                "LOW", [], "Dalili hazikutambuliwa — tafadhali eleza dalili kwa undani zaidi."
            )

        # Critical overrides
        for s in symptoms:
            if s in CRITICAL_OVERRIDE_KEYWORDS:
                return self.build_result(
                    "CRITICAL", symptoms, f"Dalili ya hatari imegunduliwa: {s}"
                )

        # Condition-specific CRITICAL
        if "fever" in symptoms and "stiff_neck" in symptoms:
            return self.build_result(
                "CRITICAL", symptoms, "Homa na shingo ngumu — meningitis inashukiwa"
            )
        if "fever" in symptoms and "altered_consciousness" in symptoms:
            return self.build_result(
                "CRITICAL", symptoms, "Homa na kupoteza fahamu — malaria ya ubongo inashukiwa"
            )
        if "fever" in symptoms and "severe_pallor" in symptoms:
            return self.build_result(
                "CRITICAL", symptoms, "Homa na udhaifu mkubwa — upungufu wa damu unaohusiana na malaria"
            )
        if "diarrhoea" in symptoms and "sunken_eyes" in symptoms:
            return self.build_result(
                "CRITICAL", symptoms, "Kuhara na macho yaliyozama — ukosefu mkubwa wa maji"
            )
        if "snake_bite" in symptoms and any(
            s in symptoms for s in ["neurotoxic_envenomation", "coagulopathy"]
        ):
            return self.build_result(
                "CRITICAL", symptoms, "Kuumwa na nyoka na sumu kali — dharura ya kimatibabu"
            )
        if "pregnancy" in symptoms and any(
            s in symptoms for s in ["antepartum_bleeding", "eclampsia", "uncontrolled_bleeding"]
        ):
            return self.build_result(
                "CRITICAL", symptoms, "Dharura ya uzazi — tafadhali piga simu hospitali mara moja"
            )

        # Stiff neck alone
        if "stiff_neck" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Shingo ngumu — meningitis haiwezi kutengwa, peleka hospitali"
            )

        # Fast breathing
        if "fast_breathing" in symptoms and "cough" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Kupumua haraka na kikohozi — nimonia inashukiwa"
            )
        if "fast_breathing" in symptoms:
            return self.build_result("HIGH", symptoms, "Kupumua haraka — tatizo la kupumua")

        # HIGH conditions
        if "fever" in symptoms and "fast_breathing" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Homa na kupumua haraka — nimonia inashukiwa"
            )
        if "fever" in symptoms and "malaria_confirmed" in symptoms:
            return self.build_result("HIGH", symptoms, "Malaria iliyothibitishwa na homa")
        if (
            "chronic_cough" in symptoms
            and "weight_loss" in symptoms
            and "night_sweats" in symptoms
        ):
            return self.build_result(
                "HIGH", symptoms, "Dalili tatu za TB — peleka kwa kipimo cha makohozi"
            )
        if "diarrhoea" in symptoms and "restless_irritable" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Kuhara na wasiwasi — upungufu wa maji wa wastani"
            )
        if "bloody_stool" in symptoms and "fever" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Kuhara damu na homa — kuhara damu (dysentery)"
            )
        if "snake_bite" in symptoms and "bite_site_swelling" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Kuumwa na nyoka na uvimbe — sumu ya eneo"
            )
        if "pregnancy" in symptoms and "severe_headache" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Maumivu makali ya kichwa ukiwa mjamzito — pre-eclampsia inashukiwa"
            )
        if "head_injury" in symptoms and "confusion" in symptoms:
            return self.build_result(
                "HIGH", symptoms, "Jeraha la kichwa na mkanganyiko — tatizo la kichwa"
            )

        # MEDIUM conditions
        if "fever" in symptoms and "headache" in symptoms:
            return self.build_result(
                "MEDIUM", symptoms, "Homa na maumivu ya kichwa — chunguza malaria au typhoid"
            )
        if "diarrhoea" in symptoms and "vomiting" in symptoms:
            return self.build_result(
                "MEDIUM", symptoms, "Kuhara na kutapika — angalia upungufu wa maji"
            )
        if "cough" in symptoms and "fever" in symptoms:
            return self.build_result(
                "MEDIUM", symptoms, "Kikohozi na homa — uwezekano wa maambukizi ya chini ya njia ya hewa"
            )
        if "chronic_cough" in symptoms:
            return self.build_result("MEDIUM", symptoms, "Kikohozi cha muda mrefu — chunguza TB")
        if "abdominal_pain" in symptoms and "fever" in symptoms:
            return self.build_result(
                "MEDIUM", symptoms, "Maumivu ya tumbo na homa — chunguza zaidi"
            )
        if "bloody_stool" in symptoms:
            return self.build_result(
                "MEDIUM", symptoms, "Damu kwenye kinyesi — mgonjwa thabiti, chunguza"
            )
        if "snake_bite" in symptoms:
            return self.build_result(
                "MEDIUM", symptoms, "Kuumwa na nyoka — angalia kwa masaa 6-24"
            )

        # LOW conditions
        if "fever" in symptoms:
            return self.build_result("LOW", symptoms, "Homa tu — fuatilia hali ya mgonjwa")
        if "cough" in symptoms:
            return self.build_result(
                "LOW", symptoms, "Kikohozi tu — uwezekano wa maambukizi ya juu ya njia ya hewa"
            )
        if "headache" in symptoms:
            return self.build_result("LOW", symptoms, "Maumivu ya kichwa tu — fuatilia")
        if "diarrhoea" in symptoms:
            return self.build_result(
                "LOW", symptoms, "Kuhara bila dalili za hatari — mpe ORS na zinki"
            )

        return self.build_result("LOW", symptoms, "Hakuna dalili kubwa zilizogunduliwa")


if __name__ == "__main__":
    classifier = RuleBasedClassifier()

    test_inputs = [
        "mgonjwa ana homa na degedege",
        "ana kikohozi na kupumua haraka",
        "ana kuhara na macho yaliyozama",
        "maumivu ya kichwa na shingo ngumu",
        "kuumwa na nyoka na uvimbe mkubwa",
        "mjamzito ana damu nyingi",
        "ana homa tu",
        "ana kikohozi kidogo",
        "ana kukohoa zaidi ya wiki mbili na jasho usiku na uzito kupotea",
        "",
        "random gibberish text here",
    ]

    for text in test_inputs:
        result = classifier.classify(text)
        print(f"Input:    {text}")
        print(f"Severity: {result['severity']} ({result['severity_sw']})")
        print(f"Reason:   {result['reason']}")
        print(f"Disclaimer: {result['disclaimer']}")
        print()