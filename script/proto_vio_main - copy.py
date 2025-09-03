
import os
import re
import unicodedata
import json
import shutil
import subprocess
import uuid
import spacy
import hashlib
import pandas as pd
import streamlit as st


from fuzzywuzzy import process, fuzz
from thefuzz import process
from rapidfuzz import fuzz, process
from difflib import SequenceMatcher










from libprotocollo import rimuovi_cartella, carica_categorie, unisci_json

# === Funzioni di supporto ===
def visualizza_contenuti_txt(percorso_file):
    with open(percorso_file, "r", encoding="utf-8", errors="ignore") as f:
        contenuto = f.read()
        return unicodedata.normalize("NFC", contenuto)
        
        
        
# ========================= import from webmatch_reg ================================

@st.cache_resource
def carica_spacy():
    return spacy.load("it_core_news_sm")

nlp = carica_spacy()

def salva_parziale(nome_file, risultati):
    """Salva i risultati parziali in un file JSON."""
    with open(nome_file, 'w', encoding='utf-8') as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)
        
@st.cache_data
#Carica file comuni da cartella
def carica_comuni(percorso_csv, colonna_nome="Denominazione in italiano", colonna_codice_regione="Codice Regione"):
    comuni_per_regione = {}
    for encoding in ['utf-8', 'cp1252', 'latin1']:
        try:
            df = pd.read_csv(percorso_csv, encoding=encoding, sep=';', on_bad_lines='skip')
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("Impossibile leggere il file comuni.")

    for _, row in df.iterrows():
        codice_regione = str(int(row[colonna_codice_regione])).zfill(2)
        nome = unifica_nome(str(row[colonna_nome]))
        comuni_per_regione.setdefault(codice_regione, set()).add(nome)

    return comuni_per_regione

#Estrae codice regione da primi 2 caratteri nel nome file
def estrai_codice_regione_da_nome(nome_file):   
   
    match = nome_file[0:2]
    if match:
           
        print("Codice regione:", match)
        return match
    else:
        return 0
        print("Nessun match")

def trova_comune_nel_testo(estratto, comuni):
    comuni_trovati = []
    estratto_l = estratto.lower()

    for comune in comuni:
        comune_l = comune.lower()
        if comune_l in estratto_l:
            comuni_trovati.append((comune, 100, True))
        else:
            punteggio = fuzz.partial_ratio(comune_l, estratto_l)
            if punteggio > 60:
                comuni_trovati.append((comune, punteggio, False))

    comuni_trovati.sort(key=lambda x: x[1], reverse=True)
    return comuni_trovati
    
@st.cache_data
#Carica file runts da cartella
def carica_runts(percorso_csv, colonna_nome="Denominazione"):
    for encoding in ['utf-8', 'cp1252', 'latin1']:
        try:
            df = pd.read_csv(percorso_csv, encoding=encoding, sep=';', on_bad_lines='skip')
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("Impossibile leggere il file CSV.")
    if colonna_nome not in df.columns:
        raise ValueError(f"La colonna '{colonna_nome}' non esiste.")
    return set(unifica_nome(v) for v in df[colonna_nome].dropna())



def _unifica_nome(nome):
    return re.sub(r'\s+', ' ', nome.strip().title())

def __unifica_nome(nome: str) -> str:
    nome = nome.lower()
    nome = unicodedata.normalize('NFKC', nome)
    nome = nome.replace("’", "'").replace("‘", "'").replace("`", "'")
    nome = re.sub(r"'\s+", "'", nome)
    nome = re.sub(r"\bass\.?ne?\b", "associazione", nome)
    nome = re.sub(r"\bass\.?\b", "associazione", nome)
    nome = re.sub(r"\b([a-z](?:\.[a-z])+)", lambda m: m.group(1).replace('.', ''), nome)
    nome = re.sub(r"[^\w\s&'\-]", "", nome, flags=re.UNICODE)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome
    
def unifica_nome(nome: str) -> str:
    nome = unicodedata.normalize("NFKC", nome)
    nome = nome.lower()
    nome = nome.replace("’", "'").replace("‘", "'")
    nome = re.sub(r"[“”\"“]", "", nome)

    # Mantieni solo lettere, numeri, spazi e simboli utili nei nomi
    nome = re.sub(r"[^a-z0-9 +&'\\-]", "", nome)

    # Spazi multipli → uno solo
    nome = re.sub(r"\s+", " ", nome)

    # Rimuove doppie spaziature o terminazioni
    return nome.strip()    

def pulisci_nome(nome: str) -> str:
    nome = re.sub(r"\b\d{3,}\b", "", nome)
    nome = re.sub(r"\b(h24|soc|di|della|del|dei|cf)\b", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome

def suddividi_testo_in_blocchi(testo: str) -> list:
    testo = testo.replace("\n", ". ")
    blocchi = re.split(r"[.;]|\s+alla responsabile del\b", testo, flags=re.IGNORECASE)
    return [b.strip() for b in blocchi if len(b.strip()) > 5]


def verifica_organizzazione_con_spacy(testo):
    doc = nlp(testo)
    return any(ent.label_ == "ORG" for ent in doc.ents)


    
def estrai_associazioni(testo: str) -> list:
    blocchi = suddividi_testo_in_blocchi(testo)
    risultati = set()
    pattern = re.compile(
        r"""(
            (?:l[’']?\s*)?
            (?:
                ass(?:ociazione)?       # Ass o Associazione
                |
                ass\.*ne\.*             # Ass.ne o Ass.ne.
            )
            (?:\s+[A-Z][\w\.\-\+']+){1,6}  # Nome dell'associazione (es. MAI+SOLE)
            |
            (?:
                centri?\s+(?:antiviolenza|donna|di\s+ascolto)
                (?:\s+[\"“”]?[A-Z][\w\.\-\+']+(?:\s+[A-Z][\w\.\-\+']+)*[\"“”]?)?
                (?:\s+(?:di|della)\s+[A-Z][a-zàèéìòù]+)?
            )
            |
            \bCAV\b
        )""",
        re.IGNORECASE | re.VERBOSE
    )

    
    for blocco in blocchi:
        testo_pulito =unicodedata.normalize('NFKC', re.sub(r"\s+", " ", blocco))
        testo_pulito = testo_pulito.replace("’", "'").replace("‘", "'")
        testo_pulito = testo_pulito.replace("“", '"').replace("”", '"')
        estratti = pattern.findall(testo_pulito)
        for e in estratti:
            raw = e[0] if isinstance(e, tuple) else e
            n = unifica_nome(raw)

            # ✂️ escludi generici come "centro antiviolenza" o "centro donna"
            lower = n.lower()
            if lower in ("centro antiviolenza", "centro donna", 
                         "centro di ascolto", "centro donna provinciale"):
                continue

            if 10 < len(n) < 80 and len(n.split()) <= 10:
                risultati.add(n)
    return list(risultati)

def normalizza_testo(testo):
    return unicodedata.normalize("NFC", testo)

def normalize(text):
    return text.strip().title()

# Deduplicazione fuzzy intelligente
def deduplica_associazioni(lista, threshold=88):
    normalizzati = [(s, normalizza_nome_associazione(s)) for s in lista]
    unici = []
    normalizzati_unici = []

    for originale, norm in normalizzati:
        if norm in ["centri antiviolenza", "centro antiviolenza", "centro di ascolto"]:
            continue  # scarta generici

        if all(fuzz.token_sort_ratio(norm, other) < threshold for other in normalizzati_unici):
            unici.append(originale)
            normalizzati_unici.append(norm)

    return unici

# Normalizzazione nomi associazioni
def normalizza_nome_associazione(nome):
    nome = nome.lower()
    nome = re.sub(r"\bassociazione(di)?\b", "", nome)
    nome = re.sub(r"\bdi\s+(volontariato|promozione sociale)\b", "", nome)
    nome = re.sub(r"\bl'associazione\b", "", nome)
    nome = re.sub(r"\bsi impegna\b", "", nome)
    nome = re.sub(r"\bcon altri soggetti pubblici\b", "", nome)
    nome = re.sub(r"[^a-z\u00e0-\u00f90-9\s]", "", nome)
    nome = re.sub(r"\s+", " ", nome)
    return nome.strip()

    
# Evidenzia differenze tra stringhe simili
def evidenzia_differenze(base, variante):
    matcher = SequenceMatcher(None, base, variante)
    result = ""
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            result += variante[j1:j2]
        elif opcode in ("insert", "replace"):
            result += f"<mark>{variante[j1:j2]}</mark>"
    return result
   
# Matching contro elenco RUNTS
def match_runts(nome_estratto, elenco_runts, soglia=85):
    risultato = process.extractOne(nome_estratto, elenco_runts, scorer=fuzz.token_sort_ratio)
    if risultato is None:
        return "", 0, False
    match, score, _ = risultato
    return match, score, score >= soglia
    
    
# Raggruppamento per Comune / Provincia da DataFrame
def raggruppa_per_comune(df_match):
    grouped = df_match.groupby(["Provincia", "Comune"])["Estratto"].apply(list).reset_index()
    grouped.columns = ["Provincia", "Comune", "Associazioni"]
    return grouped

def estrai_comuni(text):
    
    PATTERNS = {
        "comuni": [
            r"\bComune\s+di\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\- ]+)",
            r"\bC\.\s*COMUNE\s+([A-ZÀ-Ú'][A-ZÀ-Ú'\s\-]+)",
            r"\bComuni\s+della\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)",
            r"\bComuni\s+del\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)"
        ],
        "unioni_montane": [
            r"\bUnione\s+Montana\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)"
        ],
        "unioni": [
            r"\bUnioni?\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)"
        ],
        "Zona Distretto": [
            r"\bZona\s+Distretto\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+(?:\s+e\s+[A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)*)"
        ]
    }
    
    risultati = {k: set() for k in PATTERNS}

    for categoria, patterns in PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                nome = " ".join(m) if isinstance(m, tuple) else m
                risultati[categoria].add(unifica_nome(nome))

    return sorted(risultati["comuni"])

def match_comune(c, elenco, soglia=80):
    c_clean = unifica_nome(c)

    risultato = process.extractOne(c_clean, elenco, scorer=fuzz.token_sort_ratio)
    if risultato is None:
        return "", 0, False

    best_match, raw_score, _ = risultato

    best_match_lower = best_match.lower()
    c_lower = c_clean.lower()

    # Match perfetto
    if best_match_lower == c_lower:
        adjusted_score = 100

    else:
        tokens_c = set(c_lower.split())
        tokens_match = set(best_match_lower.split())
        token_overlap = len(tokens_c & tokens_match)
        starts_with = best_match_lower.startswith(c_lower)

        if token_overlap < 1:
            adjusted_score = 0
        elif token_overlap == 1 and not starts_with:
            adjusted_score = int(raw_score * 0.5)
        elif starts_with:
            adjusted_score = int(raw_score * 0.9)
        else:
            adjusted_score = raw_score

    return best_match, adjusted_score, adjusted_score >= soglia

def e_rumoroso(nome_estratto, match_nome, max_parole_non_corrispondenti=1):
    parole_nome = set(nome_estratto.split())
    parole_match = set(match_nome.split())
    parole_comuni = {"associazione", "culturale", "sportiva", "onlus", "aps", "asd", "societa", "cooperativa"}
    differenza = parole_nome - parole_match - parole_comuni
    return len(differenza) > max_parole_non_corrispondenti

def trova_match(nome, dizionario, threshold=85):

    nome_pulito = unifica_nome(pulisci_nome(nome))
    # old risultati = process.extract(nome_pulito, diz_runts, scorer=fuzz.token_set_ratio, limit=20)
    
    #1 new 
    risultati = process.extract(nome_pulito, diz_runts, scorer=fuzz.partial_token_set_ratio, limit=20)

    #2 new 
    #risultati = process.extract(nome_pulito, diz_runts, scorer=fuzz.WRatio, limit=20)
    
    matches_buoni = []
    debug_info = []
    parole_nome = set(nome_pulito.split())
    parole_escluse = {"associazione", "culturale", "sportiva", "onlus", "aps", "asd", "societa", "cooperativa"}
    parole_utili = parole_nome - parole_escluse
    for match_nome, score, _ in risultati:
        parole_match = set(match_nome.split())
        comuni = parole_utili & (parole_match - parole_escluse)
        bonus = 5 if parole_utili and parole_utili.issubset(parole_match) else 0
        score += bonus
        score = min(score, 100)
        debug_info.append({
            "match_nome": match_nome,
            "score": score,
            "parole_utili": list(parole_utili),
            "parole_match": list(parole_match),
            "bonus": bonus,
            "comuni": list(comuni),
        })
        if (
            score >= threshold
            and len(match_nome.split()) >= 2
            and len(match_nome) >= 15
            and len(comuni) >= 1
        ):
            matches_buoni.append((match_nome, score))
    return matches_buoni, debug_info

def evidenzia_parole_comuni(estratto, match):
    parole_estratto = set(estratto.split())
    parole_match = set(match.split())
    return " ".join(
        f"**:green[{p}]**" if p in parole_estratto else f":red[{p}]" for p in match.split()
    )

def genera_key(file_name, estratto, match_nome):
    """Genera una chiave stabile e unica per ogni checkbox."""
    s = f"{file_name}__{estratto}__{match_nome}"
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def normalizza_nome_associazione(nome):
    nome = nome.lower()
    nome = re.sub(r"\bassociazione(di)?\b", "", nome)
    nome = re.sub(r"\bdi\s+(volontariato|promozione sociale)\b", "", nome)
    nome = re.sub(r"\bl'associazione\b", "", nome)
    nome = re.sub(r"\bsi impegna\b", "", nome)
    nome = re.sub(r"\bcon altri soggetti pubblici\b", "", nome)
    nome = re.sub(r"[^a-zà-ù0-9\s]", "", nome)
    nome = re.sub(r"\s+", " ", nome)
    return nome.strip()

def deduplica_estratti(lista, threshold=90):
    unici = []
    for item in lista:
        item_clean = item.strip().lower()
        # Aggiungi solo se non è troppo simile a nessuno dei già presenti
        if all(fuzz.token_sort_ratio(item_clean, altro.lower()) < threshold for altro in unici):
            unici.append(item)
    return unici

def deduplica_associazioni(lista, threshold=88):
    normalizzati = [(s, normalizza_nome_associazione(s)) for s in lista]

    unici = []
    normalizzati_unici = []

    for originale, norm in normalizzati:
        if norm in ["centri antiviolenza", "centro antiviolenza", "centro di ascolto"]:
            continue  # salta generici

        if all(fuzz.token_sort_ratio(norm, other) < threshold for other in normalizzati_unici):
            unici.append(originale)
            normalizzati_unici.append(norm)

    return unici
    
def evidenzia_differenze(base, variante):
    matcher = SequenceMatcher(None, base, variante)
    result = ""
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            result += variante[j1:j2]
        elif opcode in ("insert", "replace"):
            result += f"<mark>{variante[j1:j2]}</mark>"
    return result
    
 # Visualizza su mappa interattiva (richiede lat/lon nel dataframe)

def mostra_mappa_con_marker(df_comuni):
    mappa = folium.Map(location=[42.5, 12.5], zoom_start=6)
    for _, row in df_comuni.iterrows():
        if 'Lat' in row and 'Lon' in row and pd.notnull(row['Lat']) and pd.notnull(row['Lon']):
            popup_text = f"{row['Comune']} ({row['Provincia']})<br>" + "<br>".join(row['Associazioni'])
            folium.Marker(
                location=[row['Lat'], row['Lon']],
                popup=popup_text,
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mappa)
    return mappa  
        
        
        
        

# === Cartelle ===
DIR_INPUT_RUNTS = "input/runts"
DIR_INPUT_COMUNI = "input/comuni"
DIR_INPUT_TXT = "input/txt"
DIR_OUTPUT_JSON = "output/json"

os.makedirs(DIR_INPUT_RUNTS, exist_ok=True)
os.makedirs(DIR_INPUT_COMUNI, exist_ok=True)
os.makedirs(DIR_INPUT_TXT, exist_ok=True)
os.makedirs(DIR_OUTPUT_JSON, exist_ok=True)

default_session_state = {
    "json_data": [],
    "csv_data": [],
    "path_output": "",
    "visualizza_txt": False,
    "fine_estrazione": False,
    "mostra_risultati_estrazione": False,
    "mostra_risultati_merge": False
    
}


for k, v in default_session_state.items():
    if k not in st.session_state:
        st.session_state[k] = v

# === Interfaccia utente ===

script_name = os.path.basename(__file__)
st.title(f"Analisi Protocollo ** `{script_name}` **")

uploaded_comuni = st.file_uploader("🏘️ Carica file CSV con elenco comuni", type=["csv"])
    
uploaded_csv = st.file_uploader("📁 Carica file CSV RUNTS", type=["csv"])

uploaded_txt_files = st.file_uploader("📄 Carica file TXT", type=["txt"], accept_multiple_files=True)

json_files = []

# === Caricamento file ===
if uploaded_csv and uploaded_comuni and uploaded_txt_files:
    
    st.markdown("### Elenco dei File da elaborare")

    runts_path = os.path.join(DIR_INPUT_RUNTS, uploaded_csv.name)
    comuni_path = os.path.join(DIR_INPUT_COMUNI, uploaded_comuni.name)

    #with open(runts_path, "wb") as f:
    #    f.write(uploaded_csv.getbuffer())

    with st.spinner("Caricamento RUNTS ..."):
        with open("tmp_runts.csv", "wb") as f:
            f.write(uploaded_csv.getbuffer())
        diz_runts = carica_runts("tmp_runts.csv")
        st.markdown(f" - Associazioni caricate con {len(diz_runts)} denominazioni.")

    

    #with open(comuni_path, "wb") as f:
    #    f.write(uploaded_comuni.getbuffer())

    with st.spinner("Caricamento elenco comuni..."):
        with open("tmp_comuni.csv", "wb") as f:
            f.write(uploaded_comuni.getbuffer())
        elenco_comuni = carica_comuni("tmp_comuni.csv")        
             
        total_comuni = sum(len(v) for v in elenco_comuni.values())
        st.markdown(f" - Elenco comuni caricato: {total_comuni} comuni totali in {len(elenco_comuni)} regioni.")        


    for file in uploaded_txt_files:
        txt_path = os.path.join(DIR_INPUT_TXT, file.name)
        with open(txt_path, "wb") as f:
            f.write(file.getbuffer())
            
 
        
 

# === Visualizzazione TXT ===
st.session_state["visualizza_txt"] = st.toggle("Visualizza File TXT", value=False)
if st.session_state.get("visualizza_txt", False):
    txt_filenames = sorted([f for f in os.listdir(DIR_INPUT_TXT) if f.endswith(".txt")])
    if txt_filenames:
        selected_txt = st.selectbox("Seleziona un file TXT da visualizzare", txt_filenames, key="txt_select")
        if selected_txt:
            txt_path = os.path.join(DIR_INPUT_TXT, selected_txt)
            contenuto = visualizza_contenuti_txt(txt_path)
            with st.expander(f"Contenuto di: {selected_txt}", expanded=True):
                st.text_area("Testo", contenuto, height=400, disabled=True)


if st.button("Inizio Estrazione"):
    rimuovi_cartella("output")
    with st.spinner("In elaborazione..."):
        try:
            result = subprocess.run(["python", "getdat.py"], check=True, capture_output=True, text=True)
            if result.stdout:
                st.code(result.stdout)
            st.session_state["fine_estrazione"] = True
            
        except subprocess.CalledProcessError as e:
            st.error("Errore durante l'esecuzione di `getdat.py`")
            st.code(e.stderr)
            st.session_state["fine_estrazione"] = False


# === Visualizzazione JSON ===


if st.session_state.get("fine_estrazione", False):
    
    st.markdown("▶️ Estrazione completata")
   
    st.session_state["mostra_risultati_estrazione"] = st.toggle("Visualizza Risultati Estrazione", value=False)

    json_files = sorted([f for f in os.listdir(DIR_OUTPUT_JSON) if f.endswith(".json")])

if st.session_state.get("mostra_risultati_estrazione", False):
    
    if json_files:
        selected_json = st.selectbox("Seleziona un file JSON da visualizzare", json_files, key="json_select")
        if selected_json:
            json_path = os.path.join(DIR_OUTPUT_JSON, selected_json)
            with open(json_path, "r", encoding="utf-8") as f:
                dati = json.load(f)
            with st.expander(f"Contenuto di: {selected_json}", expanded=True):
                st.json(dati, expanded=True)
    else:
        st.info("Nessun file JSON trovato.")


if json_files:

    st.markdown("### Applica Matching")
    soglia_comuni = st.slider("Soglia di similarità minima - Comuni ", 50, 100, 80)
    soglia_associazioni = st.slider("Soglia di similarità minima - Associazioni", 70, 100, 85)

    solo_associazioni_org = st.checkbox("✅ Considera solo entità ORG (spaCy)", value=True)
    mostra_associazioni_rumorosi = st.checkbox("⚠️ Mostra anche match rumorosi", value=False)
    mostra_associazioni_debug = st.checkbox("🩵 Mostra debug info per ogni match", value=False)
    mostra_match_associazioni = st.checkbox("👁️‍🗨️ Visualizza i match trovati per ogni estratto", value=True)
    mostra_tutti_i_match_associazioni = st.checkbox("📊 Mostra tabella completa con tutti i match trovati", value=False)   
 

# ============================== import from webmatch_reg ======================

if json_files:
    
    tutti_i_match_associazioni = []
    selezioni_finali = []
    risultati_per_file = {}
    totale_file = len(json_files)   

    for i, json_file in enumerate(json_files, start=1):
       
        st.write("Nome file ricevuto:", json_file)        
        codice_regione = estrai_codice_regione_da_nome(json_file)
        comuni_della_regione = elenco_comuni.get(codice_regione, set())     
        st.write("➡️ Codice regione estratto:", codice_regione)
        st.write("➡️ Numero comuni in regione:", len(comuni_della_regione))
        
        
                
        json_path = os.path.join(DIR_OUTPUT_JSON, json_file)
        with open(json_path, "r", encoding="utf-8") as f:
           dati = json.load(f)
        st.markdown(f" {dati}")   
        #with st.expander(f"Contenuto di: {json_file}", expanded=True):
        #   st.json(dati, expanded=True)
        
        
        associazioni_estratte = dati.get("associazioni", [])
        comuni_estratti = dati.get("comuni", [])
        
        
        com_match = [
            (*match_comune(c, comuni_della_regione, soglia_comuni), c)
                for c in comuni_estratti
        ]
                
        #visualizza nome del file n/n
        st.markdown(f"### 📄 File {i}/{totale_file}: `{json_file}` ")
        
        #visualizza il contenuto del file.
        with st.expander(f"📄 Visualizza file: {json_file}", expanded=False):
            st.text(dati)

        #COMUNI     
        st.markdown(f"`{len(comuni_estratti)}` - Trova Comune Estratto = Comune Caricato")
        risultati = []
        for estratto in comuni_estratti:
            estratto = normalizza_testo(estratto.strip())
            comuni_possibili = trova_comune_nel_testo(estratto, comuni_della_regione)

            if comuni_possibili:
                best = comuni_possibili[0]
                risultati.append({
                    "Comune Match": best[0],
                    "Score": best[1],
                    "Esatto": best[2],
                    "Frase estratta": estratto
                })
            else:
                risultati.append({
                    "Comune Match": "", "Score": 0, "Esatto": False,
                    "Frase estratta": estratto
                })

        df = pd.DataFrame(risultati)
        st.dataframe(df, use_container_width=True)
        
        # Download
        #csv = df.to_csv(index=False).encode('utf-8')
        #st.download_button("📥 Scarica CSV", csv, "risultati_comuni.csv", "text/csv")

  
        st.markdown("---")
        
        risultati_per_file[json_file] = {
        
            "comuni": comuni_estratti,
            "comuni_matched":com_match,
            "estratti": associazioni_estratte,       
            "match": [m for m in tutti_i_match_associazioni if m["file"] == json_file],
            "match_selezionati": [s for s in selezioni_finali if s["file"] == json_file]
        }
        

    if selezioni_finali:
        df = pd.DataFrame(selezioni_finali)
        st.markdown("---")
        st.markdown("## ✅ Match selezionati manualmente")
        st.dataframe(df)
        st.download_button("⬇️ Scarica selezioni in CSV", df.to_csv(index=False), "match_selezionati.csv", "text/csv")
        st.download_button("⬇️ Scarica selezioni in JSON", json.dumps(selezioni_finali, ensure_ascii=False, indent=2), "match_selezionati.json", "application/json")

    if tutti_i_match_associazioni and mostra_tutti_i_match_associazioni:
        st.markdown("## 🗂️ Tutti i match trovati")
        df_all = pd.DataFrame(tutti_i_match_associazioni)
        st.dataframe(df_all)
        st.download_button("⬇️ Scarica tutti i match (CSV)", df_all.to_csv(index=False), "tutti_i_match_associazioni.csv", "text/csv")

    output_finale = {
        "dati": risultati_per_file,
        "parametri": {
            "soglia_similarità": soglia_associazioni,
            "solo_associazioni_org": solo_associazioni_org,
            "mostra_associazioni_rumorosi": mostra_associazioni_rumorosi,
            "mostra_associazioni_debug": mostra_associazioni_debug,
            "mostra_associazioni_match": mostra_match_associazioni,
            "mostra_tutti_i_match_associazioni": mostra_tutti_i_match_associazioni
        }
    }
    json_str = json.dumps(output_finale, ensure_ascii=False, indent=2)
    st.download_button("⬇️ Scarica risultati completi JSON", json_str, file_name="risultati_completi.json", mime="application/json")




# === Unione file ===
PATH_CATEGORIE = os.path.join("categorie", "categorie.json")
categorie_rilevanti = carica_categorie(PATH_CATEGORIE)

if categorie_rilevanti:
    categorie_scelte = st.multiselect("Seleziona una o più categorie da unificare", categorie_rilevanti)

tipo_merge = st.selectbox("Seleziona tipo di merge", ["file", "categoria"])


st.session_state["mostra_risultati_merge"] = st.toggle("Visualizza Risultati Merge", value=False)
esegui_merge_multi = st.button("Esegui merge multiplo")

json_data = {}
csv_data = []
path_output = f"output/merge_per_{tipo_merge}"


if esegui_merge_multi and categorie_scelte:
    with st.spinner("Unione dei file in corso..."):
        json_data, csv_data = unisci_json(
            DIR_OUTPUT_JSON,
            categorie_scelte,
            tipo_merge="file",
            path_output=path_output,
            mostra_output=st.session_state["mostra_risultati_merge"]
        )
        st.session_state.json_data = json_data
        st.session_state.csv_data = csv_data
        st.session_state.path_output = path_output
        

    # === Download unificati ===
    if st.session_state.json_data:
        json_path = f"{st.session_state.path_output}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(st.session_state.json_data, f, ensure_ascii=False, indent=2)
        with open(json_path, "rb") as f:
            st.download_button("Scarica JSON", f, file_name=os.path.basename(json_path), mime="application/json")

    if st.session_state.csv_data:
        df = pd.DataFrame(st.session_state.csv_data)
        csv_path = f"{st.session_state.path_output}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        with open(csv_path, "rb") as f:
            st.download_button("Scarica CSV", f, file_name=os.path.basename(csv_path), mime="text/csv")
    
    elif mostra_output:
        st.info("Nessun contenuto da salvare.")
