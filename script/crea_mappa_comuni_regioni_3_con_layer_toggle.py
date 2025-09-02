import os
import geopandas as gpd
import pandas as pd
import json
import branca
import folium
from folium import FeatureGroup
from folium.plugins import MarkerCluster

# Configurazioni cerchi
visual_type = "circle"  # "marker", "circle", "circlemarker"
enable_clustering = False
scale_radius_by_file = True
color_by_region = True

regioni_color_map = {
    'Abruzzo': '#1f77b4', 'Basilicata': '#aec7e8', 'Calabria': '#ff7f0e',
    'Campania': '#ffbb78', 'Emilia-Romagna': '#2ca02c', 'Friuli-Venezia Giulia': '#98df8a',
    'Lazio': '#d62728', 'Liguria': '#ff9896', 'Lombardia': '#9467bd', 'Marche': '#c5b0d5',
    'Molise': '#8c564b', 'Piemonte': '#c49c94', 'Puglia': '#e377c2', 'Sardegna': '#f7b6d2',
    'Sicilia': '#7f7f7f', 'Toscana': '#c7c7c7', 'Trentino-Alto Adige/Südtirol': '#bcbd22',
    'Umbria': '#dbdb8d', "Valle d'Aosta": '#17becf', 'Veneto': '#9edae5'
}


fld_out = "output"
fld_map = "maps"
file_end = "comuni_out_end.json"
out_end_file = os.path.join(fld_out, file_end)
file_comuni_regione ="comuni_regione.csv"
file_confini_regioni = "confini_regioni.geojson"
file_mappa = "mappa_comuni_regioni_3_con_layer_toggle.html"
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

layer_regioni = FeatureGroup(name="Copertura regioni")
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
).add_to(layer_regioni)
layer_regioni.add_to(mappa)

# Aggiunge solo se almeno un valore > 0
if max_percentuale > 0:
    colormap.add_to(mappa)



# === 5. Aggiunta cerchi comuni ===
layer_cerchi = FeatureGroup(name="Comuni trovati (cerchi)")
file_counts = {f: len(v) for f, v in comuni_data.items()}
max_count = max(file_counts.values())
cluster_layer = MarkerCluster() if enable_clustering else None

for file, entries in comuni_data.items():
    count = file_counts.get(file, 1)
    for entry in entries:
        lat = entry.get("lat")
        lon = entry.get("lon")
        nome = entry.get("match_finale")
        estratto = entry.get("estratto", "")
        regione = entry.get("regione", "default")

        if lat and lon:
            location = [float(lat), float(lon)]
            tooltip = f"{nome} ({regione})"
            popup = folium.Popup(f"<b>{nome}</b><br>{estratto}<br><i>{file}</i>", max_width=300)
            radius = 4000 #+ (c * (count / max_count)) if scale_radius_by_file else 5000
            color = "blue" #regioni_color_map.get(regione, "#3186cc")

            if visual_type == "circle":
                marker = folium.Circle(location=location, radius=radius, popup=popup,
                                       tooltip=tooltip, color=color, fill=True, fill_opacity=0.5)
            elif visual_type == "circlemarker":
                marker = folium.CircleMarker(location=location, radius=6 + 6 * (count / max_count),
                                             popup=popup, tooltip=tooltip, color=color,
                                             fill=True, fill_opacity=0.7)
            else:
                marker = folium.Marker(location=location, popup=popup, tooltip=tooltip,
                                       icon=folium.Icon(color="blue", icon="info-sign"))

            if enable_clustering and visual_type in ["marker", "circlemarker"]:
                cluster_layer.add_child(marker)
            else:
                marker.add_to(layer_cerchi)

if enable_clustering and visual_type in ["marker", "circlemarker"]:
    layer_cerchi.add_to(mappa)
if cluster_layer:
    cluster_layer.add_to(mappa)
layer_cerchi.add_to(mappa)

folium.LayerControl(collapsed=False).add_to(mappa)
mappa.save(file_out_mappa)
print(f"✅ Mappa salvata: {file_out_mappa}")
