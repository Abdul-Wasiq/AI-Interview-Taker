import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api = os.getenv("brainAPI")
url = "https://api.groq.com/openai/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api}"
}
data = {
    "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": "Hi can you answer me? just testing"}]
}

response = requests.post(url, headers=headers, json=data)
jsonOutput = json.dumps(response.json(), indent=4)
print(jsonOutput)