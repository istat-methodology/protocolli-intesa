
import os
import re
import unicodedata
import json

import subprocess
import uuid
import spacy
import hashlib
import pandas as pd
import streamlit as st

from fuzzywuzzy import process, fuzz
from thefuzz import process

from difflib import SequenceMatcher


from proto_vio_lib import (
    rimuovi_cartella, 
    carica_categorie, 
    unisci_json, 
    carica_spacy, 
    carica_comuni, 
    carica_runts,
    estrai_codice_regione_da_nome,
    match_comune,
    trova_comune_nel_testo,
    normalizza_testo,
    deduplica_associazioni,
    verifica_organizzazione_con_spacy,
    trova_match,
    pulisci_nome,
    e_rumoroso,
    visualizza_contenuti_txt,
    evidenzia_parole_comuni,
    genera_key
    )
        

# === Configurazioni e cartelle ===
st.set_page_config(layout="wide")
DIR_INPUT_RUNTS = "input/runts"
DIR_INPUT_COMUNI = "input/comuni"
DIR_INPUT_TXT = "input/txt"
DIR_OUTPUT_JSON = "output/json"


for d in [DIR_INPUT_RUNTS, DIR_INPUT_COMUNI, DIR_INPUT_TXT, DIR_OUTPUT_JSON]:
    os.makedirs(d, exist_ok=True)

# === Caching per caricamenti ===
@st.cache_data
def carica_comuni_cached(path):
    return carica_comuni(path)

@st.cache_data
def carica_runts_cached(path):
    return carica_runts(path)

@st.cache_data
def carica_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def get_json_files():
    return sorted([f for f in os.listdir(DIR_OUTPUT_JSON) if f.endswith(".json")])

@st.cache_data
def get_txt_files():
    return [f.replace(".txt", "") for f in os.listdir(DIR_INPUT_TXT) if f.endswith(".txt")]

# === UI helper ===
def text_area_info(title, content):
    return st.text_area(title, content, height=50, disabled=True)

# === Stato di sessione ===
def init_session():
    defaults = {
        "json_data": [],
        "csv_data": [],
        "path_output": "",
        "fine_estrazione": False,
        "mostra_risultati_estrazione": False,
        "mostra_risultati_merge": False,
        "tutti_match": []
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# === Titolo ===
script_name = os.path.basename(__file__)
st.title(f"PROTO-VIO (`{script_name}`)")



# === Tabs ===
tab_carica_file, tab_estrazione, tab_merge, tab_matching,  tab_riepilogo = st.tabs([
    "📂 Carica Files", "🔍 Estrazione",  "🧹 Merge", "🌟 Matching", "📊 Riepilogo"
])


with tab_carica_file:
    
    
    col1, col2 = st.columns(2)
    with col1:
    # Caricamento file da uploader
        uploaded_comuni = st.file_uploader("🏘️ Carica file CSV con elenco comuni", type=["csv"])        
        uploaded_runts = st.file_uploader("📁 Carica file CSV RUNTS", type=["csv"])
        uploaded_protocolli = st.file_uploader("📄 Carica file TXT", type=["txt"], accept_multiple_files=True)

    # Visualizza file Caricati
    with col2:                
            
        if uploaded_comuni:
            path_comuni = "tmp_comuni.csv"
            with open(path_comuni, "wb") as f:
                f.write(uploaded_comuni.getbuffer())
            elenco_comuni = carica_comuni_cached(path_comuni)
            total_comuni = sum(len(v) for v in elenco_comuni.values())
            text_area_info("COMUNI", f"{total_comuni} comuni totali in {len(elenco_comuni)} regioni.")

        if uploaded_runts:
            path_runts = "tmp_runts.csv"
            with open(path_runts, "wb") as f:
                f.write(uploaded_runts.getbuffer())
            runts = carica_runts_cached(path_runts)
            text_area_info("RUNTS", f"{len(runts)} denominazioni RUNTS caricate.")

        if uploaded_protocolli:
            for file in uploaded_protocolli:
                path = os.path.join(DIR_INPUT_TXT, file.name)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
            text_area_info("PROTOCOLLI", f"{len(uploaded_protocolli)} protocolli caricati.")
            


with tab_estrazione:
    
    st.markdown("### Estrai dati dai protocolli")    
    estrai_dati = st.button("Avvia Estrazione")
    if estrai_dati:
        rimuovi_cartella("output")
        with st.spinner("Elaborazione in corso..."):
            try:
                result = subprocess.run(["python", "proto_vio_getdat.py"], check=True, capture_output=True, text=True)
                if result.stdout:
                    st.code(result.stdout)
                st.session_state.fine_estrazione = True
            except subprocess.CalledProcessError as e:
                st.error("Errore durante l'esecuzione di `proto_vio_getdat.py`")
                st.code(e.stderr)
                st.session_state.fine_estrazione = False


 # = Visualizzazione JSON = #
    if st.session_state.fine_estrazione:
        st.success("✅ Estrazione completata")        
        st.session_state["mostra_risultati_estrazione"] = st.toggle("Visualizza Risultati Estrazione", value=False)
        if st.session_state.get("mostra_risultati_estrazione", False):
            
            json_files = get_json_files()
            if json_files:
                selected_json = st.selectbox("📄 Seleziona file JSON da visualizzare", json_files)
                base_name = os.path.splitext(selected_json)[0]
                txt_file = f"{base_name}.txt"
                
                col3, col4 = st.columns(2)
                
                with col3:
                    dati = carica_json(os.path.join(DIR_OUTPUT_JSON, selected_json))                    
                    with st.expander(f"Contenuto di {selected_json}", expanded=True):
                        st.json(dati)
                with col4:
                    if txt_file.replace(".txt", "") in get_txt_files():                        
                        with st.expander(f"Contenuto di: {txt_file}", expanded=True):
                            with open(os.path.join(DIR_INPUT_TXT, txt_file), "r", encoding="utf-8") as f:
                                st.text_area("", f.read(), height=600, disabled=False)
							
                                
with tab_merge:

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
    
    mostra_output=""

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
            
            
with tab_matching:  

    st.markdown("### Applica Matching")
    avvia_matching = st.button("Avvia Matching")
    
  
    
    json_files = get_json_files() 
    runts = carica_runts_cached("tmp_runts.csv") if os.path.exists("tmp_runts.csv") else {}
    elenco_comuni = carica_comuni_cached("tmp_comuni.csv") if os.path.exists("tmp_comuni.csv") else {}

    applica_matching_comuni = st.checkbox("✅ Applica matching COMUNI", value=False)    
    soglia_comuni = st.slider("Soglia di similarità minima - Comuni ", 50, 100, 80)
    
    
    applica_matching_associazioni = st.checkbox("✅ Applica matching ASSOCIAZIONI", value=False)  
    
    if applica_matching_associazioni:
        applica_matching_associazioni_1 = st.checkbox("✅ Applica matching tipo 1 ", value=False, key="match_assoc_1")
        applica_matching_associazioni_2 = st.checkbox("✅ Applica matching tipo 2 ", value=False, key="match_assoc_2")
   
    
    solo_associazioni_org = st.checkbox("✅ Considera solo entità ORG (spaCy)", value=False)
    mostra_associazioni_rumorosi = st.checkbox("⚠️ Mostra anche match rumorosi", value=False)
    mostra_associazioni_debug = st.checkbox("🩵 Mostra debug info per ogni match", value=False)
    mostra_match_associazioni = st.checkbox("👁️‍🗨️ Visualizza i match trovati per ogni estratto", value=False)
    mostra_tutti_i_match_associazioni = st.checkbox("📊 Mostra tabella completa con tutti i match trovati", value=False) 
    
    soglia_associazioni = st.slider("Soglia di similarità minima - Associazioni", 70, 100, 85)    
        
    if avvia_matching:
    
        if json_files:
            
            tutti_i_match_associazioni = []
            selezioni_finali = []
            risultati_per_file = {}
            totale_file = len(json_files)   

            for i, json_file in enumerate(json_files, start=1):
            
                dati = {}


                #st.markdown(f"### 📄 File {i}/{totale_file}: `{json_file}` ")
                json_path = os.path.join(DIR_OUTPUT_JSON, json_file)
                with open(json_path, "r", encoding="utf-8") as f:
                   dati = json.load(f)
                  
                codice_regione = estrai_codice_regione_da_nome(json_file)
                comuni_della_regione = elenco_comuni.get(codice_regione, set())     
                st.write("➡️ Codice regione estratto:", codice_regione)
                st.write("➡️ Numero comuni in regione:", len(comuni_della_regione))
                
                        
                st.markdown(f"### 📄 File {i}/{totale_file}")
                #with st.expander(f"{json_file}", expanded=False):
                #   st.json(dati, expanded=True)
                
                
                associazioni_estratte = dati.get("associazioni", [])
                comuni_estratti = dati.get("comuni", [])
                
                com_match = []
                
                if applica_matching_comuni:             
                
                
                    com_match = [
                        (*match_comune(c, comuni_della_regione, soglia_comuni), c)
                            for c in comuni_estratti
                    ]

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
                    
                    if com_match:        
                        st.markdown(f"###  `{len(com_match)}` - Comuni estratti con match: ")
                        df_com = pd.DataFrame(com_match, columns=["Comune Match","Score","OK","Comune Estratto"])
                        st.dataframe(
                            df_com,
                            use_container_width=True,
                            #column_order=["Comune Match","Score","OK" , "Comune Estratto" ]
                        )
                        for comune, score, matched, frase in com_match:
                            if matched:
                                st.success(f"✅ Comune: `{comune}` score: {score}")
                    else:
                        st.info("Nessun Comune trovato.")
                
                if applica_matching_associazioni:              
                                    
                    if applica_matching_associazioni_1:                    
                    
                        #Step - Associazioni                                 
                        associazioni_estratte = deduplica_associazioni(associazioni_estratte, threshold=soglia_associazioni)
                        #if associazioni_estratte:
                        
                        st.success(f"`{associazioni_estratte}` ")
                    
                        st.markdown(f"### `{len(associazioni_estratte)}` - Associazioni estratte")
                        df_ass = pd.DataFrame(associazioni_estratte, columns=["Nome Associazione"])
                        
                        st.dataframe(
                            df_ass,
                            use_container_width=True,
                            #column_order=["a","b" , "c" ]
                        )
                            
                        #else:
                        #    st.info("Nessuna associazione trovata.")
                    
                    
                    if applica_matching_associazioni_2:
                    
                        for nome in associazioni_estratte:
                            if solo_associazioni_org and not verifica_organizzazione_con_spacy(nome):
                                continue

                            if not mostra_match_associazioni:
                                continue

                            matches, debug_matches = trova_match(nome, comuni_della_regione, threshold=soglia_associazioni)

                            if not matches:
                                nome_fallback = " ".join(pulisci_nome(nome).split()[:3])
                                matches, debug_matches = trova_match(nome_fallback, comuni_della_regione, threshold=soglia_associazioni - 5)

                            if not matches:
                                st.warning("❌ Nessun match trovato.")
                                continue

                            for m, (match_nome, score) in enumerate(matches):
                                rumoroso = e_rumoroso(nome, match_nome)
                                if rumoroso and not mostra_associazioni_rumorosi:
                                    continue

                                evidenziato = evidenzia_parole_comuni(nome, match_nome)
                                label = f"{evidenziato} (score: {score})"
                                if rumoroso:
                                    label = f"⚠️ {label}"

                                # ✅ chiave deterministica
                                key_unique = genera_key(json_file, nome, match_nome)
                                checked = st.checkbox(label, key=key_unique)

                                if checked:
                                    selezioni_finali.append({
                                        "file": json_file,
                                        "estratto": nome,
                                        "match_runts": match_nome,
                                        "score": score
                                    })

                                tutti_i_match_associazioni.append({
                                    "file": json_file,
                                    "estratto": nome,
                                    "match_runts": match_nome,
                                    "score": score,
                                    "rumoroso": rumoroso
                                })

                                if mostra_associazioni_debug:
                                    with st.expander(f"🔎 Dettagli debug per '{match_nome}'"):
                                        st.json(debug_matches[m])

                  
                
                risultati_per_file[json_file] = {
                
                    "comuni": comuni_estratti,
                    "comuni_matched":com_match,
                    "associazioni": associazioni_estratte,       
                    "associazioni_matched": [m for m in tutti_i_match_associazioni if m["file"] == json_file],
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



