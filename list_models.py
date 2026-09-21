# list_models.py

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ask groq what models i can use
models = client.models.list()
for m in models.data:
    print(m.id)