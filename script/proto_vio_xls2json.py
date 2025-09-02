import pandas as pd
import json
import os

# Chiedi il percorso del file all'utente
file_path = input("Inserisci il percorso del file .xls: ").strip()

# Verifica che il file esista
if not os.path.isfile(file_path):
    print("Errore: il file non esiste.")
    exit()

# Leggi il file .xls
try:
    df = pd.read_excel(file_path)
except Exception as e:
    print(f"Errore durante la lettura del file: {e}")
    exit()

# Converte in una lista di dizionari
data = df.to_dict(orient="records")

# Crea il nome del file JSON
json_path = os.path.splitext(file_path)[0] + ".json"

# Scrivi su file JSON
try:
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Conversione completata. File salvato in: {json_path}")
except Exception as e:
    print(f"Errore durante il salvataggio del file JSON: {e}")
