import os
import re
import json
import pandas as pd
from rapidfuzz import process, fuzz

fld_comuni="comuni", 
fld_out="output", 
fld_json="json",

file_comuni = os.path.join("elenco comuni.csv")
path_json = os.path.join(fld_out, fld_json)
file_protocolli_estratti = os.path.join(path_json, "match_comuni_output_tmp.json")


# Carica elenco ufficiale comuni
df_comuni = pd.read_csv(file_comuni, encoding="latin1", sep=";")
comuni_ufficiali = df_comuni["Denominazione in italiano"].dropna().str.strip().unique().tolist()


# Carica il file con i match iniziali
with open(file_protocolli_estratti, "r", encoding="utf-8") as f:
    data = json.load(f)

# Funzione: cerca submatch più puliti da parole con maiuscola
def find_best_submatch(text, comuni_list):
    parole = [w.strip(",.()") for w in text.split() if w and w[0].isupper()]
    candidati = list(set(parole))
    best_match, score, _ = process.extractOne(" ".join(candidati), comuni_list, scorer=fuzz.partial_ratio)
    return best_match, score

# Funzione alternativa
def find_best_submatch_2(text, comuni_list):
    parole = [w.strip(",.()") for w in text.split() if w[0].isupper()]
    candidati = list(set(parole))
    best_match, score, _ = process.extractOne(" ".join(candidati), comuni_list, scorer=fuzz.partial_ratio)
    return best_match, score

# Funzione: match diretto nel testo
def exact_match_from_text(text, comuni_list):
    for comune in comuni_list:
        if comune.lower() in text.lower():
            return comune
    return None

# ✅ Nuova funzione: trova tutti i comuni presenti nel testo
def _comuni_presenti_nel_testo(estratto, comuni_list):
    trovati = []
    for comune in comuni_list:
        if comune.lower() in estratto.lower():
            trovati.append(comune)
    return trovati
    
def __comuni_presenti_nel_testo(estratto, comuni_list):
    trovati = []
    estratto_lower = estratto.lower()
    for comune in comuni_list:
        idx = estratto_lower.find(comune.lower())
        if idx != -1:
            trovati.append((comune, idx))
    # Ordina i comuni in base alla loro posizione nel testo
    trovati.sort(key=lambda x: x[1])
    return [comune for comune, _ in trovati]
def comuni_presenti_nel_testo(estratto, comuni_list):
    trovati = []
    estratto_lower = estratto.lower()
    for comune in comuni_list:
        # Usa regex per trovare solo parole intere (match precisi)
        pattern = r'\b' + re.escape(comune.lower()) + r'\b'
        match = re.search(pattern, estratto_lower)
        if match:
            trovati.append((comune, match.start()))
    # Ordina per posizione nel testo
    trovati.sort(key=lambda x: x[1])
    return [comune for comune, _ in trovati]

# Applica i miglioramenti
output_migliorato = {}

for file, matches in data.items():
    migliorati = []
    for m in matches:
        estratto = m["estratto"]
        match_attuale = m["match"]
        punteggio = m["punteggio"]

        migliorato = {
            "estratto": estratto,
            "match_iniziale": match_attuale,
            "punteggio_iniziale": punteggio,
            "
            ": None,
            "punteggio_migliorato": None,
            "tipo_miglioramento": None,
            "match_migliorato_2": None,
            "punteggio_migliorato_2": None,
            "tipo_miglioramento_2": None,
            "match_finale": None  # nuovo campo
        }

        if punteggio < 50:
            submatch, subscore = find_best_submatch(estratto, comuni_ufficiali)
            submatch_2, subscore_2 = find_best_submatch_2(estratto, comuni_ufficiali)
            direct_match = exact_match_from_text(estratto, comuni_ufficiali)

            if subscore >= 60:
                migliorato["match_migliorato"] = submatch
                migliorato["punteggio_migliorato"] = subscore
                migliorato["tipo_miglioramento"] = "submatch"

                migliorato["match_migliorato_2"] = submatch_2
                migliorato["punteggio_migliorato_2"] = subscore_2
                migliorato["tipo_miglioramento_2"] = "submatch_2"

            elif direct_match:
                migliorato["match_migliorato"] = direct_match
                migliorato["punteggio_migliorato"] = 100
                migliorato["tipo_miglioramento"] = "direct_match"

        # ✅ Scegli il match finale
        comuni_trovati = comuni_presenti_nel_testo(estratto, comuni_ufficiali)
        if comuni_trovati:
            migliorato["match_finale"] = comuni_trovati[0]  # ora il primo effettivo nel testo
        elif migliorato["match_migliorato"]:
            migliorato["match_finale"] = migliorato["match_migliorato"]
        else:
            migliorato["match_finale"] = match_attuale

        migliorati.append(migliorato)
    output_migliorato[file] = migliorati

# Salva il nuovo file JSON
with open("match_comuni_migliorato.json", "w", encoding="utf-8") as f:
    json.dump(output_migliorato, f, ensure_ascii=False, indent=2)

print("✅ Match migliorato salvato in 'match_comuni_migliorato.json'")
