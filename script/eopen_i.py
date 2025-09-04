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

    OPENAI_MODEL = "gpt-4o-mini" #gpt-5-mini
    SYSTEM_PROMPT = (
        "Sei un estrattore di informazioni. "
        "Devi rispondere SOLO in formato json valido (oggetto JSON), senza testo extra, "
        "senza markdown e senza code fences. "
        "La risposta deve essere un unico oggetto json."
    )

    USER_INSTRUCTIONS = """Estrai l'elenco strutturato dei centri/sportelli/case citati nel testo qui sotto.
    Regole:
    - 'tipo' ∈ {Centro Antiviolenza, Sportello collegato, Casa Rifugio, Altro}
    - Compila comuni/indirizzi solo se esplicitamente presenti.
    - Indica in 'ente_capofila' se dal testo emerge (es. “Comune di Bra”).
    - In 'note' aggiungi contesto utile (es. “sportelli decentrati del CAV n.10/A del Cuneese”, “collegamento al 1522”, “nuovo centro”).
    Testo:
    """

    resp = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=USER_INSTRUCTIONS + testo + "\n---"
    )
        
    data = json.loads(resp.output_text)
    return json.dumps(data, indent=4, ensure_ascii=False)


# 📂 Legge tutti i file .txt nella cartella "txtokut"
cartella_txt = "txtoren"
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
