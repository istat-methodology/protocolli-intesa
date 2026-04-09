# filtra in base ad una lista

import os
import re
import json
import copy
import pandas as pd
from pathlib import Path

reg_code = "09"   

JSON_STEP1_FOLDER = r"output/json/step_1"
INPUT_JSON  = f"{JSON_STEP1_FOLDER}/{reg_code}_risultati.json"
OUTPUT_JSON_FILTER = INPUT_JSON.replace(".json", ".filtered.json")

# === ELENCO FILE DA TENERE ===
file_target = {
    "09_APUANE_2015 Protocollo Prefettura.txt",
    "09_ALTA VALDELSA Protocollo-violenza-valdelsa-2022_ALTA VALDELSA.txt",
    "09_AREZZO Prot_2024-2026.txt",
    "09_FIRENZE Linee-di-indirizzo2024.txt",
    "09_GROSSETO 2022 fpdf.txt",
    "09_LIVORNO Protocollo_ RETE ANTIVIOLENZA_ LIVORNO.txt",
    "09_LUCCA PROV.txt",
    "09_PRATO PREF.txt",
    "09_PISTOIA PROV .txt",
    "09_PISA PREF E PROV.txt",
    "09_SENESE Delibera-n.1196-del-24-10-2022-allegato-a_SENESE_2.txt",
    "09_VALDICHIANA_all. decreto 37_2008 protocollo di intesa 2008.txt",
}

# === CARICA JSON ===
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    dati = json.load(f)

# === FILTRO: solo file target + solo soggetti ===
risultato = []

for item in dati:
    if item["file"] in file_target:
        risultato.append({
            "file": item.get("file", ""),
            "firmatari": item.get("firmatari", []),
            "soggetti": item.get("soggetti", []),
            "soggetti_proponenti": item.get("soggetti_proponenti", []),
            "attori_coinvolti": item.get("attori_coinvolti", [])
        })

# === OUTPUT ===
print(f"File trovati: {len(risultato)}")

# === SALVA RISULTATO ===

OUTPUT_JSON_FILTER = INPUT_JSON.replace(".json", ".filtered.json")
OUTPUT_JSON_FULL = INPUT_JSON.replace(".json", ".FULL.json")

with open(OUTPUT_JSON_FILTER, "w", encoding="utf-8") as f:
    json.dump(risultato, f, ensure_ascii=False, indent=2)

print(f"Salvato in {OUTPUT_JSON_FILTER}")

import json
from difflib import get_close_matches

# === FILE JSON DI INPUT ===
reg_code = "09"   # es. "09" Emilia-Romagna
# === FILE JSON DI INPUT ===
INPUT_JSON  = f"{JSON_STEP1_FOLDER}/{reg_code}_risultati.json"
print("Input JSON da arricchire:", INPUT_JSON)

# === ELENCO FILE ATTESI ===
file_attesi = [
    "09_APUANE_2015 Protocollo Prefettura.txt",
    "09_ALTA VALDELSA Protocollo-violenza-valdelsa-2022_ALTA VALDELSA.txt",
    "09_AREZZO Prot_2024-2026.txt",
    "09_FIRENZE Linee-di-indirizzo2024.txt",
    "09_GROSSETO 2022 fpdf.txt",
    "09_LIVORNO Protocollo_ RETE ANTIVIOLENZA_ LIVORNO.txt",
    "09_LUCCA PROV.txt",
    "09_PRATO PREF.txt",
    "09_PISTOIA PROV .txt",
    "09_PISA PREF E PROV.txt",
    "09_SENESE Delibera-n.1196-del-24-10-2022-allegato-a_SENESE_2.txt",
    "09_VALDICHIANA_all. decreto 37_2008 protocollo di intesa 2008.txt",
]

# === CARICA JSON ===
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    dati = json.load(f)

# === FILE PRESENTI NEL JSON ===
file_presenti = [item.get("file", "").strip() for item in dati]

# === CONTROLLO ===
trovati = []
mancanti = []

for nome in file_attesi:
    if nome in file_presenti:
        trovati.append(nome)
    else:
        mancanti.append(nome)

# === RISULTATI ===
print("="*80)
print("FILE TROVATI")
print("="*80)
for f in trovati:
    print("✅", f)

print("\n" + "="*80)
print("FILE MANCANTI")
print("="*80)
for f in mancanti:
    print("❌", f)

# === CERCA NOMI SIMILI PER I MANCANTI ===
print("\n" + "="*80)
print("POSSIBILI CORRISPONDENZE SIMILI")
print("="*80)

for f in mancanti:
    simili = get_close_matches(f, file_presenti, n=3, cutoff=0.5)
    print(f"\n🔍 {f}")
    if simili:
        for s in simili:
            print("   →", s)
    else:
        print("   Nessun nome simile trovato")

# === RIASSUNTO ===
print("\n" + "="*80)
print("RIEPILOGO")
print("="*80)
print(f"Totale attesi   : {len(file_attesi)}")
print(f"Totale trovati  : {len(trovati)}")
print(f"Totale mancanti : {len(mancanti)}")

INPUT_JSON = Path(INPUT_JSON)
OUTPUT_JSON_FULL = Path(OUTPUT_JSON_FULL)
OUTPUT_JSON_FILTER = Path(OUTPUT_JSON_FILTER)

if INPUT_JSON.exists():
    INPUT_JSON.rename(OUTPUT_JSON_FULL)
    print(f"Backup creato: {OUTPUT_JSON_FULL}")
else:
    print(f"❌ Non trovato: {INPUT_JSON}")

if OUTPUT_JSON_FILTER.exists():
    OUTPUT_JSON_FILTER.rename(INPUT_JSON)
    print(f"Nuovo file attivo: {INPUT_JSON}")
else:
    print(f"❌ Non trovato: {OUTPUT_JSON_FILTER}")

import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import streamlit as st

# Caricamento dati
df = pd.read_json(OUTPUT_JSON_FILTER)

st.title("Analisi rete antiviolenza")

# Distribuzione categorie
st.subheader("Distribuzione categorie")
cat_counts = df['categoria'].value_counts()
st.bar_chart(cat_counts)

# Tabella riassuntiva
st.subheader("Tabella riassuntiva")
st.dataframe(cat_counts)

# Heatmap territoriale (semplificata)
st.subheader("Distribuzione territoriale")
pivot = pd.pivot_table(df, index='area', columns='categoria', aggfunc='size', fill_value=0)
st.dataframe(pivot)

# Network
st.subheader("Rete dei soggetti")
G = nx.Graph()

for _, row in df.iterrows():
    G.add_node(row['nome'], group=row['categoria'])

# esempio connessioni (stesso file)
for file, group in df.groupby('file'):
    nodes = list(group['nome'])
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            G.add_edge(nodes[i], nodes[j])

st.write("Numero nodi:", G.number_of_nodes())
st.write("Numero archi:", G.number_of_edges())
