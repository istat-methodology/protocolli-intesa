import os
import json
import pandas as pd
from rapidfuzz import process, fuzz


# Caricamento CSV con separatore
df_comuni = pd.read_csv("elenco comuni.csv", encoding="latin1", sep=";")
comuni_ufficiali = df_comuni["Denominazione in italiano"].dropna().str.strip().unique().tolist()

fld_out="output" 
file_merge="merge_per_file.json"
file_tmp="comuni_out_tmp.json"

merge_per_file = os.path.join(fld_out, file_merge)
out_tmp_file = os.path.join(fld_out, file_tmp)

# Caricamento JSON
with open(merge_per_file, "r", encoding="utf-8") as f:
    data = json.load(f)

risultati_comune = {}

for filename, contenuto in data.items():
    comuni_estratti = contenuto.get("comuni", [])
    comune_estratto_file = []
    for comune in comuni_estratti:
        comune_estratto_file.append({
            "estratto": comune
        })

    risultati_comune[filename] = comune_estratto_file

# Salva i risultati
with open(out_tmp_file, "w", encoding="utf-8") as f:
    json.dump(risultati_comune, f, ensure_ascii=False, indent=2)

print(f"✅ Match completato. Risultati salvati in '{out_tmp_file}'")
