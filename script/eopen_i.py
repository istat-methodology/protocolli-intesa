import os
import json
import ast
from openai import OpenAI
from dotenv import load_dotenv

# 🔐 Carica variabili da .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Funzione per estrarre centri antiviolenza dal testo
def estrai_centri(testo):
    prompt = f"""
Estrai l'elenco dei nomi di centri antiviolenza (esclusivamente i nomi) dal seguente testo.
Restituisci una lista JSON come questa:
["Centro Donna Massa", "Associazione Luna Livorno", "Telefono Rosa Roma"]

Testo:
{testo}
    """.strip()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    contenuto = response.choices[0].message.content.strip()
    try:
        return json.loads(contenuto)
    except json.JSONDecodeError:
        return ast.literal_eval(contenuto)  # fallback se GPT restituisce una lista tipo Python

# 📂 Legge tutti i file .txt nella cartella "txtokut"
cartella_txt = "txtokut"
file_txt = [f for f in os.listdir(cartella_txt) if f.endswith(".txt")]

risultati = []
for nome_file in file_txt:
    percorso = os.path.join(cartella_txt, nome_file)
    with open(percorso, "r", encoding="utf-8") as f:
        testo = f.read()
        try:
            estratti = estrai_centri(testo)
            risultati.extend(estratti)
        except Exception as e:
            print(f"❌ Errore durante l'elaborazione di {nome_file}: {e}")

# Rimuove duplicati e salva
risultati = sorted(set(risultati))
with open("centri_antiviolenza.json", "w", encoding="utf-8") as f:
    json.dump(risultati, f, ensure_ascii=False, indent=2)

print("✅ Estrazione completata! Centri trovati:")
print(json.dumps(risultati, indent=2, ensure_ascii=False))
