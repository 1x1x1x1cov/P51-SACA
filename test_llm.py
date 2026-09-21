# test_llm.py

from ammu_safety import make_llm_reply, check_reply

severity = "CRITICAL"
symptoms = ["convulsions", "fever"]
reason = "Dalili ya hatari imegunduliwa: convulsions"
facility_line = "Nearest facility: Mbinga District Hospital, about 12 km away."

reply = make_llm_reply(severity, symptoms, reason, facility_line)

print("LLM reply:")
print(reply)
print()
print("passed safety check?", check_reply(reply, severity, reason))