# test_groq.py

import os
from dotenv import load_dotenv
from groq import Groq

# load my key from the .env file
load_dotenv()
my_key = os.environ.get("GROQ_API_KEY")

# connect to groq
client = Groq(api_key=my_key)

# send a test message
reply = client.chat.completions.create(
    messages=[
        {"role": "user", "content": "Say hello in one sentence."}
    ],
    model="openai/gpt-oss-20b"
)

# print what groq said back
print("got a reply back:")
print(reply.choices[0].message.content)
print("done")