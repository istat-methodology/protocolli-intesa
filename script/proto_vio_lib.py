import re
import os
import shutil
import unicodedata
import json
import streamlit as st
import pandas as pd
import spacy
from rapidfuzz import fuzz, process
#from thefuzz import fuzz
import hashlib


 

# Frasi inutili comuni da escludere
FRASI_INUTILI = [
    "coinvolti nel seguente accordo",
    "firmatari del presente accordo",
    "presenti sul territorio",
    "si impegna a",
    "garantire l’informazione",
    "realizzazione di un nuovo centro antiviolenza",
    "l’a.s.l",
    "con",  # usato da solo o alla fine: ", Con"
]
FRASI_INUTILI_COMUNI = [
    "partecipera", "si impegna", "con gli altri membri", "firmatari", 
    "il sindaco", "sindaco", "comune di", "gestore", "oggetto del presente protocollo"
]

def pulisci_comune(nome: str) -> str:
    nome = re.sub(r"\s*(il|la)?\s*sindaco\b.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\bcomune di\b", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\bsi impegna.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\bpartecipera.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\s+", " ", nome).strip(", ")
    return nome.strip()

def è_comune_generico(nome: str) -> bool:
    nome = nome.lower()
    return any(frase in nome for frase in FRASI_INUTILI_COMUNI)

def deduplica_comuni(lista, threshold=85):
    normalizzati = [(s, unifica_nome(pulisci_comune(s))) for s in lista]
    unici = []
    normalizzati_unici = []

    for originale, norm in normalizzati:
        if è_comune_generico(norm):
            continue
        if all(not sono_simili(norm, other, threshold) for other in normalizzati_unici):
            unici.append(originale.strip(", "))
            normalizzati_unici.append(norm)

    return unici
# Rimuove ruoli, riferimenti legali, sedi, e frasi inutili
def pulisci_descrizione_extra(nome: str) -> str:
    nome = re.sub(r"\b(il|la)?\s*(presidente|dr\.?ssa?|dott\.?ssa?|dottore|dr\.?|legale rappresentante)\b.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\bl’a\.?s\.?l\b.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\bcon sede (legale )?(a|in).*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\s*,?\s*con\s*$", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\ssi impegna a.*", "", nome, flags=re.IGNORECASE)    
    return nome.strip()

def è_generico(nome: str) -> bool:
    nome = nome.lower()
    return any(frase in nome for frase in FRASI_INUTILI)

def unifica_nome(nome: str) -> str:
    nome = pulisci_descrizione_extra(nome)
    nome = nome.lower()
    nome = unicodedata.normalize('NFKC', nome)
    nome = nome.replace("’", "'").replace("‘", "'").replace("`", "'")
    nome = re.sub(r"'\s+", "'", nome)
    nome = re.sub(r"\bass\.ne?\b", "associazione", nome)
    nome = re.sub(r"\bass\.\b", "associazione", nome)
    nome = re.sub(r"\b([a-z](?:\.[a-z])+)", lambda m: m.group(1).replace('.', ''), nome)
    nome = re.sub(r"[^\w\s&'\-]", "", nome, flags=re.UNICODE)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome

def sono_simili(a: str, b: str, threshold=88):
    return (
        fuzz.token_sort_ratio(a, b) >= threshold
        or fuzz.partial_ratio(a, b) >= threshold
    )

def deduplica_associazioni(lista, threshold=88):
    normalizzati = [(s, unifica_nome(s)) for s in lista]
    unici = []
    normalizzati_unici = []

    for originale, norm in normalizzati:
        if norm in ["centro antiviolenza", "centri antiviolenza", "centro di ascolto"]:
            continue
        if è_generico(norm):
            continue
        if all(not sono_simili(norm, other, threshold) for other in normalizzati_unici):
            unici.append(originale.strip(', '))
            normalizzati_unici.append(norm)

    return unici

def deduplica_consorzi(lista, threshold=88):
    normalizzati = [(s, unifica_nome(s)) for s in lista]
    unici = []
    normalizzati_unici = []

    for originale, norm in normalizzati:
        if è_generico(norm):
            continue
        if all(not sono_simili(norm, other, threshold) for other in normalizzati_unici):
            unici.append(originale.strip(', '))
            normalizzati_unici.append(norm)

    return unici
    
    import os
import shutil

def rimuovi_cartella(cartella: str):
    """
    Rimuove una cartella e tutto il suo contenuto (file e sottocartelle).
    
    :param cartella: Percorso della cartella da eliminare.
    """
    if os.path.exists(cartella):
        shutil.rmtree(cartella)
        print(f"✅ Cartella '{cartella}' rimossa.")
    else:
        print(f"⚠️ La cartella '{cartella}' non esiste.")

def carica_categorie(path="categorie/categorie.json"):
    """
    Carica la lista di categorie da un file JSON.
    Restituisce una lista di categorie, oppure una lista vuota in caso di errore.
    Mostra messaggi di errore tramite Streamlit.
    """
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("categorie", [])
        except json.JSONDecodeError:
            st.error("❌ Errore nella lettura del file categorie.json")
            return []
    else:
        st.error(f"❌ File delle categorie non trovato: {path}")
        return []
        
def estrai_contenuti_da_json(path_json):
    if not os.path.exists(path_json):
        print(f"❌ File non trovato: {path_json}")
        return

    with open(path_json, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("❌ Errore nella lettura del JSON.")
            return

    for categoria, elementi in data.items():
        print(f"\n📂 Categoria: {categoria.upper()}")
        print("-" * (len(categoria) + 12))
        for item in elementi:
            if item.strip():  # ignora voci vuote
                print(f"- {item.strip()}")
            else:
                print("- ⚠️ Vuoto")
                
def unisci_json(cartella_json, categorie_scelte, tipo_merge="file", path_output=None, mostra_output=True):
    """
    Unisce i contenuti dei file JSON in una cartella, salvandoli in un unico JSON e CSV.

    Args:
        cartella_json (str): Percorso alla cartella contenente i JSON da processare.
        categorie_scelte (list): Categorie da estrarre.
        tipo_merge (str): 'file' o 'categoria' (modo di aggregazione).
        path_output (str): Prefisso del file di output (senza estensione).
        mostra_output (bool): Se True, mostra i risultati in Streamlit.

    Returns:
        dict: Risultato aggregato come dizionario Python.
    """
    if tipo_merge not in ["file", "categoria"]:
        st.error("❌ tipo_merge deve essere 'file' o 'categoria'")
        return {}

    if not os.path.isdir(cartella_json):
        st.error(f"❌ Cartella non trovata: `{cartella_json}`")
        return {}

    json_files = sorted([f for f in os.listdir(cartella_json) if f.endswith(".json")])
    if not json_files:
        st.warning("📭 Nessun file JSON trovato.")
        return {}

    if not path_output:
        path_output = f"output/merge_per_{tipo_merge}"

    risultato = {} if tipo_merge == "file" else {cat: [] for cat in categorie_scelte}
    righe_csv = []

    for filename in json_files:
        filepath = os.path.join(cartella_json, filename)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            if mostra_output:
                st.warning(f"⚠️ Errore nel file {filename}: {e}")
            continue

        if mostra_output:
            st.markdown(f"📄 File: `{filename}`")

        if tipo_merge == "file":
            file_entry = {}
            for categoria in categorie_scelte:
                elementi = data.get(categoria, [])
                if elementi:
                    file_entry[categoria] = elementi
                    for item in elementi:
                        righe_csv.append({
                            "file": filename,
                            "categoria": categoria,
                            "estratto": item.strip()
                        })
                    if mostra_output:
                        st.markdown(f"**📂 Categoria: {categoria.upper()}**")
                        for item in elementi:
                            st.markdown(f"- {item.strip() if item.strip() else '⚠️ Vuoto'}")
                else:
                    if mostra_output:
                        st.markdown(f"📭 Nessun elemento trovato per categoria `{categoria}`")

            if file_entry:
                risultato[filename] = file_entry

        elif tipo_merge == "categoria":
            for categoria in categorie_scelte:
                elementi = data.get(categoria, [])
                if elementi:
                    risultato[categoria].append({
                        "file": filename,
                        "estratto": elementi
                    })
                    for item in elementi:
                        righe_csv.append({
                            "file": filename,
                            "categoria": categoria,
                            "estratto": item.strip()
                        })
                    if mostra_output:
                        st.markdown(f"**📂 Categoria: {categoria.upper()}**")
                        for item in elementi:
                            st.markdown(f"- {item.strip() if item.strip() else '⚠️ Vuoto'}")
                else:
                    if mostra_output:
                        st.markdown(f"📭 Nessun elemento trovato per categoria `{categoria}`")


    return risultato, righe_csv
    
    
    
def mostra_file_txt(uploaded_txt_files):
    if not uploaded_txt_files:
        return

    file_nomi = [file.name for file in uploaded_txt_files]
    file_scelto = st.radio("📄 Seleziona un file TXT da visualizzare", file_nomi, key="file_txt_attivo")

    if file_scelto:
        file = next((f for f in uploaded_txt_files if f.name == file_scelto), None)
        if file:
            st.markdown(f"### Contenuto di `{file.name}`")
            st.text(visualizza_contenuti_txt(file))
            # Optional: download
            st.download_button(
                label="⬇️ Scarica TXT",
                data=file.getvalue(),
                file_name=file.name,
                mime="text/plain"
            )
            
def mostra_file_json_generati(directory_output="output/json"):
    if not st.session_state.get("mostra_risultati", False):
        return

    if not os.path.isdir(directory_output):
        st.warning("❌ Cartella `output/json` non trovata.")
        return

    json_files = sorted([f for f in os.listdir(directory_output) if f.endswith(".json")])

    if not json_files:
        st.info("📭 Nessun file JSON trovato.")
        return

    file_scelto_json = st.radio("📄 Seleziona un file JSON da visualizzare", json_files, key="file_json_attivo")

    if file_scelto_json:
        filepath = os.path.join(directory_output, file_scelto_json)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.markdown(f"### Contenuto di `{file_scelto_json}`")
                st.json(data, expanded=True)
        except json.JSONDecodeError:
            st.warning("⚠️ JSON non valido")

        with open(filepath, "rb") as f:
            st.download_button(
                label="⬇️ Scarica JSON",
                data=f,
                file_name=file_scelto_json,
                mime="application/json"
            )
def visualizza_file_txt_singolo(uploaded_txt_files):
    if not uploaded_txt_files:
        return

    file_nomi = [file.name for file in uploaded_txt_files]
    file_scelto = st.radio("📄 Seleziona un file TXT da visualizzare", file_nomi, key="file_txt_attivo")

    if file_scelto:
        file = next((f for f in uploaded_txt_files if f.name == file_scelto), None)
        if file:
            st.markdown(f"### Contenuto di `{file.name}`")
            st.text(visualizza_contenuti_txt(file))

def visualizza_file_json_singolo(dir_output_json):
    if not st.session_state.get("mostra_risultati", False):
        return

    json_files = sorted([f for f in os.listdir(dir_output_json) if f.endswith(".json")])
    
    if json_files:
        file_scelto_json = st.radio("📄 Seleziona un file JSON da visualizzare", json_files, key="file_json_attivo")

        if file_scelto_json:
            filepath = os.path.join(dir_output_json, file_scelto_json)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    st.markdown(f"### Contenuto di `{file_scelto_json}`")
                    st.json(data, expanded=True)
            except json.JSONDecodeError:
                st.warning("⚠️ JSON non valido")
    else:
        st.info("📭 Nessun file JSON trovato.")

# === Funzioni di supporto ===
def visualizza_contenuti_txt(percorso_file):
    with open(percorso_file, "r", encoding="utf-8", errors="ignore") as f:
        contenuto = f.read()
        return unicodedata.normalize("NFC", contenuto)
        
        
        
# ========================= import from webmatch_reg ================================

@st.cache_resource

def carica_spacy():
    
    return spacy.load("it_core_news_sm")



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
    nlp = carica_spacy()   
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

def trova_match(nome, comuni_della_regione, threshold=85):

    nome_pulito = unifica_nome(pulisci_nome(nome))
    # old risultati = process.extract(nome_pulito, comuni_della_regione, scorer=fuzz.token_set_ratio, limit=20)    
    #1 new 
    risultati = process.extract(nome_pulito, comuni_della_regione, scorer=fuzz.partial_token_set_ratio, limit=20)
    #2 new 
    #risultati = process.extract(nome_pulito, comuni_della_regione, scorer=fuzz.WRatio, limit=20)
    
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
