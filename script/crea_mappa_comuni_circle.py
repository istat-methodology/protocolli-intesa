import os
import json
import pandas as pd
import folium
from folium.plugins import MarkerCluster
# Colori base per regioni (semplificato)
regioni_color_map = {'Abruzzo': '#1f77b4',
 'Basilicata': '#aec7e8',
 'Calabria': '#ff7f0e',
 'Campania': '#ffbb78',
 'Emilia-Romagna': '#2ca02c',
 'Friuli-Venezia Giulia': '#98df8a',
 'Lazio': '#d62728',
 'Liguria': '#ff9896',
 'Lombardia': '#9467bd',
 'Marche': '#c5b0d5',
 'Molise': '#8c564b',
 'Piemonte': '#c49c94',
 'Puglia': '#e377c2',
 'Sardegna': '#f7b6d2',
 'Sicilia': '#7f7f7f',
 'Toscana': '#c7c7c7',
 'Trentino-Alto Adige/Südtirol': '#bcbd22',
 'Umbria': '#dbdb8d',
 "Valle d'Aosta": '#17becf',
 'Veneto': '#9edae5'}


# === PARAMETRI ===
fld_out = "output"
file_end = "comuni_out_end.json"
out_end_file = os.path.join(fld_out, file_end)
file_comuni ="comuni_totali.csv"
file_confini_regioni = "confini_regioni.geojson"
fld_map="maps"
file_mappa = "mappa_comuni_circle.html"
file_out_mappa = os.path.join(fld_map, file_mappa)

# === CONFIGURAZIONE ===
visual_type = "circle"  # "marker", "circle", "circlemarker"
enable_clustering = True  # Attiva clustering se True
scale_radius_by_file = True  # Radius variabile
color_by_region = True  # Colori diversi per regione

# === CARICA DATI ===
with open(out_end_file, encoding="utf-8") as f:
    dati_comuni = json.load(f)

# Mappa base
mappa = folium.Map(location=[45.0, 8.5], zoom_start=7, tiles="cartodbpositron")

# Estrai statistiche per radius scaling
file_counts = {f: len(v) for f, v in dati_comuni.items()}
max_count = max(file_counts.values())

# Colori base per regioni (semplificato)
regioni_color_map = {'Abruzzo': '#1f77b4',
 'Basilicata': '#aec7e8',
 'Calabria': '#ff7f0e',
 'Campania': '#ffbb78',
 'Emilia-Romagna': '#2ca02c',
 'Friuli-Venezia Giulia': '#98df8a',
 'Lazio': '#d62728',
 'Liguria': '#ff9896',
 'Lombardia': '#9467bd',
 'Marche': '#c5b0d5',
 'Molise': '#8c564b',
 'Piemonte': '#c49c94',
 'Puglia': '#e377c2',
 'Sardegna': '#f7b6d2',
 'Sicilia': '#7f7f7f',
 'Toscana': '#c7c7c7',
 'Trentino-Alto Adige/Südtirol': '#bcbd22',
 'Umbria': '#dbdb8d',
 "Valle d'Aosta": '#17becf',
 'Veneto': '#9edae5'}

# Layer clustering opzionale
cluster_layer = MarkerCluster() if enable_clustering else None

# === PLOTTAGGIO COMUNI ===
for file, entries in dati_comuni.items():
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
            radius = 3000 + (7000 * (count / max_count)) if scale_radius_by_file else 5000
            color = regioni_color_map.get(regione, regioni_color_map[regione])

            if visual_type == "marker":
                marker = folium.Marker(location=location, popup=popup, tooltip=tooltip,
                                       icon=folium.Icon(color="blue", icon="info-sign"))
            elif visual_type == "circle":
                marker = folium.Circle(location=location, radius=radius, popup=popup,
                                       tooltip=tooltip, color=color, fill=True, fill_opacity=0.5)
            elif visual_type == "circlemarker":
                marker = folium.CircleMarker(location=location, radius=6 + 6 * (count / max_count),
                                             popup=popup, tooltip=tooltip, color=color,
                                             fill=True, fill_opacity=0.7)

            if enable_clustering and visual_type in ["marker", "circlemarker"]:
                cluster_layer.add_child(marker)
            else:
                marker.add_to(mappa)

# Aggiungi cluster se abilitato
if enable_clustering and visual_type in ["marker", "circlemarker"]:
    cluster_layer.add_to(mappa)

# Salva la mappa
mappa.save(file_out_mappa)
print(f"✅ Mappa salvata: {file_out_mappa}")

