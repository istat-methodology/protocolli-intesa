import os
import re
import json
from unidecode import unidecode
import pandas as pd
from rapidfuzz import process, fuzz

# === PARAMETRI ===
fld_out = "output"
file_tmp = "comuni_out_tmp.json"
file_end = "comuni_out_end.json"
elenco_comuni_csv = "elenco comuni.csv"

geo_file=os.path.join("gi_comuni.json")
out_tmp_file = os.path.join(fld_out, file_tmp)
out_end_file = os.path.join(fld_out, file_end)

# === CARICAMENTO COMUNI UFFICIALI ===
df_comuni = pd.read_csv(elenco_comuni_csv, encoding="latin1", sep=";")
#comuni_ufficiali = df_comuni["Denominazione in italiano"].dropna().str.strip().unique().tolist()

# Normalizza il codice regione a 2 cifre stringa
#df_comuni["Codice Regione"] = df_comuni["Codice Regione"].apply(lambda x: str(int(x)).zfill(2))
# Mappa codice regione (es. "16") → set di comuni
#regioni_to_comuni = df_comuni.groupby("Codice Regione")["Denominazione in italiano"].apply(set).to_dict()


# Pulisce l'elenco dei comuni: solo stringhe
df_comuni["Denominazione in italiano"] = df_comuni["Denominazione in italiano"].astype(str).str.strip()
df_comuni = df_comuni[df_comuni["Denominazione in italiano"].str.isalpha() | df_comuni["Denominazione in italiano"].str.contains(" ")]

#denom_to_codice = df_comuni.set_index("Denominazione in italiano")["Codice Comune formato alfanumerico"].to_dict()
denom_to_codice = df_comuni.set_index("Denominazione in italiano")["Codice Comune formato alfanumerico"].dropna().apply(lambda x: str(int(x)).zfill(6)).to_dict()

# Crea dizionario: codice comune (stringa a 6 cifre) → codice provincia (come stringa)
codice_comune_to_provincia = (
    df_comuni[["Codice Comune formato alfanumerico", "Codice Provincia (Storico)(1)"]]
    .dropna()
    .assign(
        codice_comune=lambda df: df["Codice Comune formato alfanumerico"].apply(lambda x: str(int(x)).zfill(6)),
        codice_provincia=lambda df: df["Codice Provincia (Storico)(1)"].apply(lambda x: str(int(x)).zfill(3))
    )
    .set_index("codice_comune")["codice_provincia"]
    .to_dict()
)

# Rende il codice regione a due cifre
df_comuni["Codice Regione"] = df_comuni["Codice Regione"].apply(lambda x: str(int(x)).zfill(2))

# Crea mapping codice → set di comuni
regioni_to_comuni = df_comuni.groupby("Codice Regione")["Denominazione in italiano"].apply(set).to_dict()

# Lista globale dei comuni validi (solo stringhe)
comuni_ufficiali = df_comuni["Denominazione in italiano"].dropna().unique().tolist()


with open(geo_file, "r", encoding="utf-8") as gf:
    geo_data = json.load(gf)


geo_lookup = {str(g["codice_istat"]).zfill(6): g for g in geo_data if "codice_istat" in g}


# Mappa codice ISTAT regione → nome
codice_regione = {
    "01": "Piemonte", "02": "Valle d'Aosta/Vallée d'Aoste", "03": "Lombardia", "04": "Trentino-Alto Adige/Südtirol",
    "05": "Veneto", "06": "Friuli-Venezia Giulia", "07": "Liguria", "08": "Emilia-Romagna", "09": "Toscana",
    "10": "Umbria", "11": "Marche", "12": "Lazio", "13": "Abruzzo", "14": "Molise", "15": "Campania",
    "16": "Puglia", "17": "Basilicata", "18": "Calabria", "19": "Sicilia", "20": "Sardegna"
}

# === UTILS ===
def find_comuni_nel_testo(estratto, comuni_list):
    estratto_lower = estratto.lower()
    trovati = []
    for comune in comuni_list:
        if not isinstance(comune, str):
            continue
        # Cerca solo comuni che coincidono come parole intere
        pattern = r'\b' + re.escape(comune.lower()) + r'\b'
        if re.search(pattern, estratto_lower):
            trovati.append((comune, estratto_lower.find(comune.lower())))
    return trovati

def find_comuni_nel_testo(estratto, comuni_list):
    
    estratto_clean = unidecode(estratto.lower())
    
    trovati = []
    for comune in comuni_list:
        if not isinstance(comune, str):
            continue
        comune_clean = unidecode(comune.lower())
        pattern = r'\b' + re.escape(comune_clean) + r'\b'
        if re.search(pattern, estratto_clean):
            trovati.append((comune, estratto_clean.find(comune_clean)))
    return trovati

def get_codice_regione(file):
    return file[:2]
    
    
def get_nome_regione(codice):
   
    codice_str = str(int(codice)).zfill(2)
    return codice_regione.get(codice_str, None)

# Parole generiche da escludere come match validi
generici = {"Re", "San", "Comune", "Residenza", "Minore", "Bambino", "Vittima"}

# === ELABORAZIONE ===
with open(out_tmp_file, "r", encoding="utf-8") as f:
    data = json.load(f)

output_migliorato = {}

for file, matches in data.items():
    
    print(f"nome del file: '{file}'")

    codice = get_codice_regione(file)
    nome_regione = get_nome_regione(codice)
    comuni_da_usare = regioni_to_comuni.get(codice, set())
    

    migliorati = []
    for m in matches:
        estratto = m["estratto"]
        comuni_trovati = find_comuni_nel_testo(estratto, comuni_da_usare)
        comuni_trovati.sort(key=lambda x: x[1])  # ordina per posizione
        comuni_validi = [c for c, _ in comuni_trovati if c not in generici]
        
        codice_comune = denom_to_codice.get(comuni_validi[0]) if comuni_validi else None
        
        migliorato = {
            
            "estratto": estratto,
            "comuni_trovati": comuni_validi,
            "regione": nome_regione,            
            "match_finale": comuni_validi[0] if comuni_validi else None,
            "codice_comune": denom_to_codice.get(comuni_validi[0]) if comuni_validi else None,            
            "codice_provincia": codice_comune_to_provincia.get(codice_comune) if codice_comune else None,
            "lat": geo_lookup.get(denom_to_codice.get(comuni_validi[0]), {}).get("lat") if comuni_validi else None,
            "lon": geo_lookup.get(denom_to_codice.get(comuni_validi[0]), {}).get("lon") if comuni_validi else None,
        }

        migliorati.append(migliorato)
    output_migliorato[file] = migliorati

# === SALVA ===
with open(out_end_file, "w", encoding="utf-8") as f:
    json.dump(output_migliorato, f, ensure_ascii=False, indent=2)

print(f"✅ Completato: comuni estratti salvati in '{out_end_file}'")
