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
file_mappa = "mappa_comuni_regioni_2.html"
file_out_mappa = os.path.join(fld_map, file_mappa)

with open(out_end_file, 'r', encoding='utf-8') as f:
    dati_comuni = json.load(f)
with open(file_confini_regioni, "r", encoding="utf-8") as f:
    geo_data = json.load(f)
df_comuni = pd.read_csv(file_comuni_regione, dtype=str)
df_comuni["regione"] = df_comuni["regione"].str.strip()

# Calcolo: comuni trovati per regione
comuni_trovati = []

for entries in dati_comuni.values():
    for e in entries:
        if e.get("match_finale") and e.get("regione"):
            comuni_trovati.append((e["regione"], e["match_finale"]))

df_trovati = pd.DataFrame(comuni_trovati, columns=["regione", "comune"])
df_trovati = df_trovati.drop_duplicates()

# Calcolo comuni totali per regione
totali = df_comuni.groupby("regione")["nome_comune"].count().reset_index(name="totale_comuni")
trovati = df_trovati.groupby("regione")["comune"].count().reset_index(name="comuni_trovati")

df_stat = pd.merge(totali, trovati, on="regione", how="left").fillna(0)
df_stat["comuni_trovati"] = df_stat["comuni_trovati"].astype(int)
df_stat["percentuale"] = round(df_stat["comuni_trovati"] / df_stat["totale_comuni"] * 100, 2)


# Prepara dizionario per shading
colormap_data = {row["regione"]: row["percentuale"] for _, row in df_stat.iterrows()}

# Mappa centrata sul nord Italia
mappa = folium.Map(location=[45.0, 8.5], zoom_start=6, tiles="cartodbpositron")

# Layer per colorare le regioni in base alla % comuni trovati
folium.Choropleth(
    geo_data=geo_data,
    name="Copertura comuni per regione",
    data=df_stat,
    columns=["regione", "percentuale"],
    key_on="feature.properties.reg_name",
    fill_color="YlOrRd",
    fill_opacity=0.6,
    line_opacity=0.5,
    legend_name="% comuni trovati per regione",
).add_to(mappa)

# Popup con percentuale
for feature in geo_data["features"]:
    nome_regione = feature["properties"]["reg_name"]
    percentuale = colormap_data.get(nome_regione, 0)
    popup_text = f"<b>{nome_regione}</b><br>{percentuale}% comuni trovati"
    centroide = feature["properties"].get("centroid", None)
    if centroide:
        folium.Marker(
            location=centroide[::-1],
            icon=folium.DivIcon(html=f"""<div style="font-size:10pt; color:black">{percentuale}%</div>""")
        ).add_to(mappa)

# Aggiunta dei marker dei singoli comuni trovati
for entries in dati_comuni.values():
    for entry in entries:
        nome = entry.get("match_finale")
        estratto = entry.get("estratto")
        lat = entry.get("lat")
        lon = entry.get("lon")
        if lat and lon:
            popup_text = f"<strong>{nome}</strong><br>{estratto}"
            folium.Marker(
                location=[float(lat), float(lon)],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=nome,
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mappa)

# Layer control
folium.LayerControl().add_to(mappa)

# Salva la mappa

mappa.save(file_out_mappa)
print(f"✅ Mappa salvata: {file_out_mappa}")

