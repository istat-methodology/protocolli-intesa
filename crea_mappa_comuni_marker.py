import os
import json
import folium

fld_out = "output"
fld_map = "maps"
file_end = "comuni_out_end.json"
out_end_file = os.path.join(fld_out, file_end)
file_mappa = "mappa_comuni_marker.html"
file_out_mappa = os.path.join(fld_map, file_mappa)


# Carica i dati dal file JSON
with open(out_end_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Crea una mappa centrata approssimativamente sul Piemonte
mappa = folium.Map(location=[45.0, 8.0], zoom_start=8)

# Aggiungi un marker per ogni comune trovato
for file, entries in data.items():
    for entry in entries:
        nome = entry.get("match_finale")
        estratto = entry.get("estratto")
        lat = entry.get("lat")
        lon = entry.get("lon")
        if lat and lon:
            popup_text = f"<strong>{nome}</strong><br>{estratto}<br><em>{file}</em>"
            folium.Marker(
                location=[float(lat), float(lon)],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=nome,
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mappa)

# Salva la mappa in un file HTML
mappa.save(file_out_mappa)
print(f"✅ Mappa salvata {file_out_mappa}")
