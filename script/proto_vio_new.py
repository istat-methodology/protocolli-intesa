# webmatch_reg_fast.py

import os
import re
import json
import subprocess
import streamlit as st
import pandas as pd
from rapidfuzz import process

from proto_vio_lib import (
    rimuovi_cartella,
    carica_categorie,
    unisci_json,
    carica_comuni,
    carica_runts,
    estrai_codice_regione_da_nome,
    match_comune,
    normalizza_testo,
    deduplica_associazioni,
    verifica_organizzazione_con_spacy,
    trova_match,
    pulisci_nome,
    e_rumoroso,
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
st.title(f"PROTO-VIO FAST 🏎️ (`{script_name}`)")



# === Tabs ===
tab_carica_file, tab_estrazione, tab_matching, tab_merge, tab_riepilogo = st.tabs([
    "📂 Carica Files", "🔍 Estrazione", "🌟 Matching", "🧹 Merge", "📊 Riepilogo"
])

# === Tab: Caricamento ===
with tab_carica_file:
    col1, col2 = st.columns(2)

    with col1:
        uploaded_comuni = st.file_uploader("🏘️ Carica file CSV con elenco comuni", type=["csv"])
        uploaded_runts = st.file_uploader("📁 Carica file CSV RUNTS", type=["csv"])
        uploaded_protocolli = st.file_uploader("📄 Carica file TXT", type=["txt"], accept_multiple_files=True)

    with col2:
        if uploaded_comuni:
            path_comuni = "tmp_comuni.csv"
            with open(path_comuni, "wb") as f:
                f.write(uploaded_comuni.getbuffer())
            comuni = carica_comuni_cached(path_comuni)
            total_comuni = sum(len(v) for v in comuni.values())
            text_area_info("COMUNI", f"{total_comuni} comuni totali in {len(comuni)} regioni.")

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

# === Tab: Estrazione ===
with tab_estrazione:
    st.markdown("### 🧠 Estrai dati dai protocolli")
    if st.button("🚀 Avvia Estrazione"):
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

    if st.session_state.fine_estrazione:
        st.success("✅ Estrazione completata")
        json_files = get_json_files()
        if json_files:
            selected_json = st.selectbox("📄 Seleziona file JSON da visualizzare", json_files)
            dati = carica_json(os.path.join(DIR_OUTPUT_JSON, selected_json))
            if st.toggle("🔍 Mostra contenuto JSON", value=False):
                with st.expander(f"Contenuto di {selected_json}", expanded=True):
                    st.json(dati)

            base_name = os.path.splitext(selected_json)[0]
            txt_file = f"{base_name}.txt"
            if txt_file.replace(".txt", "") in get_txt_files():
                if st.toggle("📜 Mostra file TXT originale", value=False):
                    with open(os.path.join(DIR_INPUT_TXT, txt_file), "r", encoding="utf-8") as f:
                        st.text_area("", f.read(), height=600, disabled=True)
            else:
                st.info("File TXT originale non trovato.")

# === Tab: Matching ===
with tab_matching:
    st.markdown("### 🎯 Matching associazioni con RUNTS")
    soglia = st.slider("Soglia di similarità", 70, 100, 85)
    solo_org = st.checkbox("✅ Solo entità ORG (spaCy)", value=True)

    runts = carica_runts_cached("tmp_runts.csv") if os.path.exists("tmp_runts.csv") else {}
    comuni = carica_comuni_cached("tmp_comuni.csv") if os.path.exists("tmp_comuni.csv") else {}

    tutti_match = []
    json_files = get_json_files()

    if json_files and runts:
        with st.spinner("🔎 Matching in corso..."):
            for jf in json_files:
                path = os.path.join(DIR_OUTPUT_JSON, jf)
                dati = carica_json(path)
                estratti = dati.get("associazioni", [])
                codice_regione = estrai_codice_regione_da_nome(jf)
                comuni_reg = comuni.get(codice_regione, set())

                for nome in estratti:
                    if solo_org and not verifica_organizzazione_con_spacy(nome):
                        continue

                    matches, _ = trova_match(nome, comuni_reg, threshold=soglia)
                    for m, (nome_match, score) in enumerate(matches):
                        if e_rumoroso(nome, nome_match):
                            continue
                        tutti_match.append({
                            "file": jf,
                            "estratto": nome,
                            "match_runts": nome_match,
                            "score": score
                        })

        #if tutti_match:
        #    df = pd.DataFrame(tutti_match)
        #    st.success(f"✅ Trovati {len(tutti_match)} match validi.")
        #    st.dataframe(df, use_container_width=True)
        #    st.download_button("⬇️ Scarica risultati (CSV)", df.to_csv(index=False), file_name="match_associazioni.csv", mime="text/csv")
        #    st.download_button("⬇️ Scarica risultati (JSON)", json.dumps(tutti_match, ensure_ascii=False, indent=2), file_name="match_associazioni.json", mime="application/json")
        #else:
        #    st.warning("Nessun match trovato.")
            
            
        if "tutti_match" in st.session_state and st.session_state["tutti_match"]:
            st.write(f"- 🎯 Match trovati: `{len(st.session_state.tutti_match)}`")
            df = pd.DataFrame(st.session_state.tutti_match)
            st.download_button("⬇️ Scarica Match Finali CSV", df.to_csv(index=False), file_name="match_finali.csv", mime="text/csv")
            st.download_button("⬇️ Scarica Match Finali JSON", json.dumps(st.session_state.tutti_match, ensure_ascii=False, indent=2), file_name="match_finali.json", mime="application/json")
        else:
            st.info("Nessun match disponibile da visualizzare.")


# === Tab: Merge ===
with tab_merge:
    PATH_CATEGORIE = os.path.join("categorie", "categorie.json")
    categorie_rilevanti = carica_categorie(PATH_CATEGORIE)

    if categorie_rilevanti:
        categorie_scelte = st.multiselect("🔖 Seleziona una o più categorie da unificare", categorie_rilevanti)
        tipo_merge = st.selectbox("⚙️ Tipo di merge", ["file", "categoria"])

        st.session_state.mostra_risultati_merge = st.toggle("📤 Mostra risultati merge", value=False)
        if st.button("🧩 Esegui merge"):
            with st.spinner("⏳ Unione dei file in corso..."):
                json_data, csv_data = unisci_json(
                    DIR_OUTPUT_JSON,
                    categorie_scelte,
                    tipo_merge=tipo_merge,
                    path_output=f"output/merge_per_{tipo_merge}",
                    mostra_output=st.session_state.mostra_risultati_merge
                )
                st.session_state.json_data = json_data
                st.session_state.csv_data = csv_data
                st.session_state.path_output = f"output/merge_per_{tipo_merge}"

        if st.session_state.json_data:
            path_json = f"{st.session_state.path_output}.json"
            with open(path_json, "w", encoding="utf-8") as f:
                json.dump(st.session_state.json_data, f, ensure_ascii=False, indent=2)
            with open(path_json, "rb") as f:
                st.download_button("⬇️ Scarica JSON unificato", f, file_name=os.path.basename(path_json), mime="application/json")

        if st.session_state.csv_data:
            path_csv = f"{st.session_state.path_output}.csv"
            pd.DataFrame(st.session_state.csv_data).to_csv(path_csv, index=False, encoding="utf-8")
            with open(path_csv, "rb") as f:
                st.download_button("⬇️ Scarica CSV unificato", f, file_name=os.path.basename(path_csv), mime="text/csv")
# === Tab: Riepilogo ===
with tab_riepilogo:
    st.markdown("### 📊 Riepilogo Finale")
    json_files = get_json_files()
    n_file = len(json_files)
    n_estratti = 0
    for f in json_files:
        dati = carica_json(os.path.join(DIR_OUTPUT_JSON, f))
        n_estratti += len(dati.get("associazioni", []))

    st.write(f"- 📁 File JSON elaborati: `{n_file}`")
    st.write(f"- 🏷️ Associazioni estratte totali: `{n_estratti}`")

    if st.session_state.tutti_match:
        st.write(f"- 🎯 Match trovati: `{len(st.session_state.tutti_match)}`")
        df = pd.DataFrame(st.session_state.tutti_match)
        st.download_button("⬇️ Scarica Match Finali CSV", df.to_csv(index=False), file_name="match_finali.csv", mime="text/csv")
        st.download_button("⬇️ Scarica Match Finali JSON", json.dumps(st.session_state.tutti_match, ensure_ascii=False, indent=2), file_name="match_finali.json", mime="application/json")
    else:
        st.info("Nessun match disponibile da visualizzare.")

    if st.session_state.json_data:
        st.markdown("---")
        st.success("✅ Risultati del merge pronti!")
        path_json = f"{st.session_state.path_output}.json"
        path_csv = f"{st.session_state.path_output}.csv"
        with open(path_json, "rb") as f:
            st.download_button("⬇️ Scarica JSON Merge Finale", f, file_name=os.path.basename(path_json), mime="application/json")
        with open(path_csv, "rb") as f:
            st.download_button("⬇️ Scarica CSV Merge Finale", f, file_name=os.path.basename(path_csv), mime="text/csv")
    else:
        st.info("Nessun merge ancora eseguito.")
