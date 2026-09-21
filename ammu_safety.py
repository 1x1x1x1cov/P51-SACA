# ammu_safety.py

# words we expect to see for each severity level.
# if the reply has at least one of these, that part is okay.
severity_words = {
    "LOW": ["minor", "rest", "water"],
    "MEDIUM": ["watch", "take it easy", "health worker"],
    "HIGH": ["attention", "see a doctor", "soon"],
    "CRITICAL": ["serious", "right away", "medical facility"]
}

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))




def check_reply(reply, severity, reason):

    # this checks if a generated reply is safe to show.
    # it returns True if the reply passes all the rules,
    # and False if anything is missing.

    text = reply.lower()

    # rule 1: reply must mention the right severity level (by keyword)
    words = severity_words[severity]
    found_one = False
    for w in words:
        if w in text:
            found_one = True
    if found_one == False:
        return False

    # rule 2: for HIGH and CRITICAL, it must tell them to seek care
    if severity == "HIGH" or severity == "CRITICAL":
        if "doctor" not in text and "health worker" not in text and "medical facility" not in text:
            return False

    # rule 3: for CRITICAL, it must mention a facility
    if severity == "CRITICAL":
        if "facility" not in text:
            return False

    # rule 4: it must have the "i am not a doctor" line
    if "not a doctor" not in text:
        return False

    # if we got here, the reply passed everything
    return True



def make_llm_reply(severity, symptoms, reason, facility_line):
    prompt = "You are AMMU, a health helper. Say this in a short kind way for the user. "
    prompt = prompt + "Do not change how serious it is. Do not add any new medical info. "
    prompt = prompt + "Say the line 'I am not a doctor'.\n\n"
    prompt = prompt + "Severity: " + severity + "\n"
    prompt = prompt + "Symptoms: " + ", ".join(symptoms) + "\n"
    prompt = prompt + "Reason: " + reason + "\n"

    if severity == "HIGH" or severity == "CRITICAL":
        prompt = prompt + "Tell them to see a health worker or doctor.\n"
    if severity == "CRITICAL":
        prompt = prompt + "Also say this: " + facility_line + "\n"

    result = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-20b"
    )

    return result.choices[0].message.content


def write_log(user_text, llm_reply, passed):
    # save every llm reply to a text file so we can check it later
    line = ""
    line = line + "USER: " + user_text + "\n"
    line = line + "LLM: " + llm_reply + "\n"
    line = line + "PASSED SAFETY CHECK: " + str(passed) + "\n"
    line = line + "-----\n"

    f = open("ammu_log.txt", "a", encoding="utf-8")
    f.write(line)
    f.close()