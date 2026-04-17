
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import streamlit as st

reg_code = "16"   # es. "09" Emilia-Romagna
# === FILE JSON DI INPUT ===
JSON_STEP1_FOLDER = r"output/data/step_1"
INPUT_JSON  = f"{JSON_STEP1_FOLDER}/{reg_code}_risultatià.json"
# === FILE JSON DI OUTPUT ===
OUTPUT_JSON_FILTER = INPUT_JSON.replace(".json", ".filtered.json")
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
pos = nx.spring_layout(G)
plt.figure(figsize=(12, 12))
nx.draw(G, pos, with_labels=True, node_size=500, node_color="skyblue", font_size=10, font_weight="bold")
st.pyplot(plt)  