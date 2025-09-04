import time
import argparse
from openai import OpenAI
import httpx
import os
import json
import ast
import argparse
from openai import OpenAI
from dotenv import load_dotenv

# --- Configurazione client ---

# 🔐 Carica variabili da .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ Variabile OPENAI_API_KEY non trovata nel .env")
client = OpenAI(api_key=api_key)

# 🎛️ Argomenti da linea di comando
parser = argparse.ArgumentParser(description="Estrazione centri antiviolenza da file .txt")
parser.add_argument("--debug", action="store_true", help="Salva l'output grezzo del modello in debug_output.log")
args = parser.parse_args()


# --- Funzione wrapper per gestire rate limit ---
def safe_chat_completion(messages, model="gpt-4o-mini", temperature=0, retries=5, debug=False):
    for attempt in range(retries):
        try:
            if debug:
                print(f"📡 Chiamata API, tentativo {attempt+1}/{retries}")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"⚠️ Rate limit 429, attendo {wait_time}s prima di riprovare...")
                time.sleep(wait_time)
            else:
                raise
    print("❌ Troppe richieste, restituisco lista vuota.")
    return None

# --- Funzione principale per estrarre centri ---
def estrai_centri(testo, debug=False):
    if not testo.strip():
        return []

    messages = [
        {"role": "system", "content": "Estrai nomi di centri antiviolenza, associazioni e comuni dal testo."},
        {"role": "user", "content": testo}
    ]

    response = safe_chat_completion(messages, debug=debug)
    if response is None:
        return []

    try:
        # supponendo che la risposta sia in formato JSON testuale
        contenuto = response.choices[0].message.content
        if debug:
            print("📄 Contenuto ricevuto:", contenuto)
        # Qui puoi adattare la logica di parsing del contenuto
        # Per esempio, se restituisce lista JSON:
        import json
        estratti = json.loads(contenuto)
        if not isinstance(estratti, list):
            if debug:
                print("⚠️ Output non è una lista, restituisco lista vuota")
            return []
        return estratti
    except Exception as e:
        if debug:
            print("⚠️ Errore nel parsing:", e)
        return []

# --- Script eseguibile ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Percorso del file .txt da processare")
    parser.add_argument("--debug", action="store_true", help="Mostra log dettagliati")
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        testo = f.read()

    estratti = estrai_centri(testo, debug=args.debug)
    print("✅ Estratti:", estratti)
