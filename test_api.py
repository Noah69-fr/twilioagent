
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_api():
    api_key = os.getenv('OPENAI_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        "https://api.openai.com/v1/models",
        headers=headers
    )
    
    if response.status_code == 200:
        print("API OpenAI fonctionne correctement!")
        return True
    else:
        print(f"Erreur API: {response.status_code}")
        print(response.text)
        return False

if __name__ == "__main__":
    test_api()
