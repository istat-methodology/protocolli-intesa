# filtra in base ad una lista

import os
import re
import json
import copy
import pandas as pd
from pathlib import Path

reg_code = "16"   

JSON_STEP1_FOLDER = r"output/data/step_1"
INPUT_JSON  = f"{JSON_STEP1_FOLDER}/{reg_code}_risultati.json"
OUTPUT_JSON_FILTER = INPUT_JSON.replace(".json", ".filtered.json")

# === ELENCO FILE DA TENERE ===
file_target_09 = {
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
file_target = {
    "16_terreg_Prot_CGIL - CISL - CONFINDUSTRIA_CAV.txt",
    "16_taranto_protocollo d'intesa CAVGinosa sottoscritto.txt",
    "16_taranto_protocollo Prefettura ProvinciaTaranto.txt",
    "16_lecce_Protocollo Operativo - Procedure integrate per la prevenzione e il contrasto alla violenza contro donne e minori - Copia_Marcato.txt",
    "16_2406_rta_16_250410140506_4166---RIVIVI_Arpal_ATS_CAV.txt",
    "16_2406_rta_16_250410122122_4166---Protocollo_Viola.txt",
    "16_2406_rta_16_250409174252_4166---Protocollo_Intesa_LARA.txt",
    "16_bat_convenzione CAV - ASL BT.txt",
    "16_2406_rta_16_250409161633_4166---29_prot_n_0090671_2024_PROT_OP-ODVPOLIZIADISTATO-RISCOPRIRSI.txt",
    "16_bari_protollo di intesa Putignano_rete antiviolenza.txt",
    "16_bar_protocollo operativo Triggiano_rete antiviolenza.pdf.txt",
    "16_bari_protocollo operativo Putignano_EMI.txt",
    "16_bari_protocollo operativo Mola di Bari_rete Antiviolenza.txt",
    "16_bari_protocollo operativo Grumo_EMI.txt",
    "16_bari_protocollo operativo Gioia del Colle_EMI.txt",
    "16_bari_Protocollo Gioia del Colle_ATS_Rete locale.txt",
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
