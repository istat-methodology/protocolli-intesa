import pandas as pd
from pathlib import Path

input_path = Path("/mnt/data/cls_comuni.csv")
df = pd.read_csv(input_path, sep=";", encoding="latin1", dtype=str).fillna("")

# Regions CSV
region_cols = ["Codice Regione", "Denominazione Regione", "Codice Ripartizione Geografica", "Ripartizione geografica"]
regions = (
    df[region_cols]
    .drop_duplicates()
    .sort_values(["Codice Regione", "Denominazione Regione"])
    .reset_index(drop=True)
)

regions = regions.rename(columns={
    "Codice Regione": "codice_regione",
    "Denominazione Regione": "regione",
    "Codice Ripartizione Geografica": "codice_ripartizione_geografica",
    "Ripartizione geografica": "ripartizione_geografica",
})

# Provinces-by-region CSV
prov_cols = [
    "Codice Regione",
    "Denominazione Regione",
    "Codice Provincia",
    "Codice dell'Unità territoriale sovracomunale",
    "Denominazione dell'Unità territoriale sovracomunale",
    "Tipologia di Unità territoriale sovracomunale",
    "Sigla automobilistica",
]
provinces = (
    df[prov_cols]
    .drop_duplicates()
    .sort_values(["Codice Regione", "Denominazione Regione", "Codice Provincia", "Denominazione dell'Unità territoriale sovracomunale"])
    .reset_index(drop=True)
)

provinces = provinces.rename(columns={
    "Codice Regione": "codice_regione",
    "Denominazione Regione": "regione",
    "Codice Provincia": "codice_provincia",
    "Codice dell'Unità territoriale sovracomunale": "codice_unita_sovracomunale",
    "Denominazione dell'Unità territoriale sovracomunale": "provincia",
    "Tipologia di Unità territoriale sovracomunale": "tipologia_unita_sovracomunale",
    "Sigla automobilistica": "sigla_automobilistica",
})

# Save
regions_path = Path("/mnt/data/regioni_codici.csv")
provinces_path = Path("/mnt/data/province_per_regione_codici.csv")

regions.to_csv(regions_path, index=False, encoding="utf-8")
provinces.to_csv(provinces_path, index=False, encoding="utf-8")

print(f"Creato: {regions_path}")
print(f"Creato: {provinces_path}")
print(f"Righe regioni: {len(regions)}")
print(f"Righe province: {len(provinces)}")
