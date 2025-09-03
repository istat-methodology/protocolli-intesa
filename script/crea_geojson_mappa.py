import os
import json
import geopandas as gpd
import pandas as pd

# === CARICA DATI ===
fld_out = "output"
file_end = "comuni_out_end.json"
file_comuni ="comuni_totali.csv"
out_end_file = os.path.join(fld_out, file_end)

file_confini_regioni = "confini_regioni.geojson"


# Carica comuni_totali.csv
df_tot = pd.read_csv(file_comuni, dtype={"codice_comune": str})

# Calcola il numero totale di comuni per regione
comuni_per_regione = df_tot.groupby("regione")["codice_comune"].nunique().to_dict()

# Carica comuni trovati dal JSON
with open(out_end_file, encoding="utf-8") as f:
    comuni_data = json.load(f)

# Calcola il numero di comuni unici trovati per regione
comuni_trovati = {}
for entries in comuni_data.values():
    for entry in entries:
        regione = entry.get("regione")
        codice = entry.get("codice_comune")
        if regione and codice:
            comuni_trovati.setdefault(regione, set()).add(codice)

# Calcola le percentuali
percentuali = {
    regione: (len(comuni_trovati.get(regione, [])) / comuni_per_regione.get(regione, 1)) * 100
    for regione in comuni_per_regione
}

# === CARICA GEOJSON REGIONI ===
gdf = gpd.read_file(file_confini_regioni)

# Assicura che i nomi delle regioni combacino
gdf["regione"] = gdf["reg_name"]

# Aggiungi colonna con percentuale comuni trovati
gdf["percentuale"] = gdf["regione"].map(percentuali).fillna(0)
gdf["tooltip"] = gdf.apply(
    lambda row: f"{row['regione']}: {int(len(comuni_trovati.get(row['regione'], [])))}/"
                f"{comuni_per_regione.get(row['regione'], 0)} comuni ({row['percentuale']:.1f}%)", axis=1
)

# Salva GeoJSON arricchito per uso con folium
path_geojson_out = "regioni_colored.geojson"
gdf.to_file(path_geojson_out, driver="GeoJSON")

path_geojson_out