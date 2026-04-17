from pathlib import Path
import json
from difflib import get_close_matches

reg_code = "16"   # es. "09" Emilia-Romagna
# === FILE JSON DI INPUT ===
JSON_STEP1_FOLDER = r"output/data/step_1"
INPUT_JSON  = f"{JSON_STEP1_FOLDER}/{reg_code}_risultatià.json"
# === FILE JSON DI OUTPUT ===
OUTPUT_JSON_FILTER = INPUT_JSON.replace(".json", ".filtered.json")
OUTPUT_JSON_FULL = INPUT_JSON.replace(".json", ".FULL.json")


# === ELENCO FILE ATTESI ===
_file_attesi_09 = [
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
file_attesi = [
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
