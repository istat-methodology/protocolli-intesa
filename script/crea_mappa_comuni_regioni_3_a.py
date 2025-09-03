import os
import geopandas as gpd
import pandas as pd
import json
import branca
import folium

fld_out = "output"
fld_map = "maps"
file_end = "comuni_out_end.json"
out_end_file = os.path.join(fld_out, file_end)
file_comuni_regione ="comuni_regione.csv"
file_confini_regioni = "confini_regioni.geojson"
file_mappa = "mappa_comuni_regioni_3.html"
file_out_mappa = os.path.join(fld_map, file_mappa)

# === 1. Carica i dati ===
with open(out_end_file, encoding="utf-8") as f:
    comuni_data = json.load(f)

df_tot = pd.read_csv(file_comuni_regione, dtype={"codice_comune": str})
gdf = gpd.read_file(file_confini_regioni)
gdf["regione"] = gdf["reg_name"]

# === 2. Calcolo copertura per regione ===
comuni_per_regione = df_tot.groupby("regione")["codice_comune"].nunique().to_dict()

comuni_trovati = {}
for entries in comuni_data.values():
    for entry in entries:
        regione = entry.get("regione")
        codice = entry.get("codice_comune")
        if regione and codice:
            comuni_trovati.setdefault(regione, set()).add(codice)

percentuali = {
    regione: (len(comuni_trovati.get(regione, [])) / comuni_per_regione.get(regione, 1)) * 100
    for regione in comuni_per_regione
}

gdf["percentuale"] = gdf["regione"].map(percentuali)
gdf["%"] = gdf.apply(
    lambda row: (
        f"{row['regione']}: "
        f"{int(len(comuni_trovati.get(row['regione'], [])))} su "
        f"{comuni_per_regione.get(row['regione'], 0)} comuni "
        f"({row['percentuale']:.1f}%)"
        if pd.notnull(row['percentuale']) and row['percentuale'] > 0
        else f"{row['regione']}: nessun dato"
    ),
    axis=1
)

# === 3. Colormap: scala dinamica su percentuali > 0 ===
max_percentuale = gdf["percentuale"].max()
colormap = branca.colormap.LinearColormap(
    colors = [
    "#ff0000", "#ff1900", "#ff3200", "#ff4b00", "#ff6400", "#ff7d00", "#ff9600",
    "#ffaf00", "#ffc800", "#ffe100", "#ffff00", "#e6ff00", "#ccff00", "#b3ff00",
    "#99ff00", "#80ff00", "#66ff00", "#4dff00", "#33ff00", "#1aff00", "#00ff00"
    ],
    vmin=0,
    vmax=max_percentuale,
    caption="Percentuale comuni trovati per regione"
)

# === 4. Crea mappa ===
mappa = folium.Map(location=[42.5, 12.5], zoom_start=6, tiles="cartodbpositron")

folium.GeoJson(
    gdf,
    name="Copertura comuni",
    style_function=lambda feature: {
        "fillColor": (
            colormap(feature["properties"]["percentuale"])
            if feature["properties"]["percentuale"] and feature["properties"]["percentuale"] > 0
            else "white"
        ),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.75,
    },
    tooltip=folium.GeoJsonTooltip(fields=["%"], sticky=True)
).add_to(mappa)

# Aggiunge solo se almeno un valore > 0
if max_percentuale > 0:
    colormap.add_to(mappa)


mappa.save(file_out_mappa)
print(f"✅ Mappa salvata: {file_out_mappa}")
