import os
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# 📁 Imposta il nome della directory e del modello
CARTELLA_TXT = "txtokut"
MODEL_NAME = "google/gemma-7b-it"

# 🚀 Verifica dispositivo disponibile
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 🔄 Caricamento modello e tokenizer
print("🔄 Caricamento modello Gemma...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32)
pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=0 if DEVICE == "cuda" else -1)

# 🧠 Funzione di estrazione
def estrai_centri_gemma(testo):
    prompt = f"""Estrai l'elenco dei nomi dei centri antiviolenza (solo i nomi) da questo testo.
Restituisci solo una lista JSON come questa:
["Centro Donna Massa", "Telefono Rosa Roma", "Associazione Luna Livorno"]

Testo:
{testo}
"""
    output = pipe(prompt, max_new_tokens=512, do_sample=False, temperature=0)[0]["generated_text"]

    # 🧼 Estrai solo la parte con la lista JSON
    try:
        json_start = output.index("[")
        json_end = output.index("]", json_start) + 1
        json_str = output[json_start:json_end]
        return json.loads(json_str)
    except Exception as e:
        print("⚠️ Parsing fallito:", e)
        print("📄 Output generato:\n", output)
        return []

# 📂 Legge tutti i file .txt
file_txt = [f for f in os.listdir(CARTELLA_TXT) if f.endswith(".txt")]

risultati = []
for nome_file in file_txt:
    percorso = os.path.join(CARTELLA_TXT, nome_file)
    with open(percorso, "r", encoding="utf-8") as f:
        testo = f.read()
        print(f"📑 Elaborazione file: {nome_file}")
        try:
            estratti = estrai_centri_gemma(testo)
            risultati.extend(estratti)
        except Exception as e:
            print(f"❌ Errore con {nome_file}: {e}")

# 🧹 Deduplicazione e salvataggio
risultati = sorted(set(risultati))
with open("centri_antiviolenza_gemma.json", "w", encoding="utf-8") as f:
    json.dump(risultati, f, ensure_ascii=False, indent=2)

print("\n✅ Estrazione completata! Centri trovati:")
print(json.dumps(risultati, indent=2, ensure_ascii=False))
