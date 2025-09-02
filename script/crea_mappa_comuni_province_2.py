import os
import pandas as pd
import json
import folium
import geopandas as gpd
import branca

def style_function(feature):
    p = feature["properties"].get("percentuale")
    if p is None:
        return {
            "fillColor": "#ffffff",  # bianco per assenza di dati
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.3,
        }
    return {
        "fillColor": colormap(p),
        "color": "black",
        "weight": 0.5,
        "fillOpacity": 0.7,
    }

fld_out = "output"
fld_map = "maps"

file_protocollo = "comuni_out_end.json"
file_out_protocollo = os.path.join(fld_out, file_protocollo)

file_comuni_provincia = "comuni_provincia.csv" 
file_confini_province = "confini_province.geojson"

file_mappa = "mappa_comuni_province_2.html"
file_out_mappa = os.path.join(fld_map, file_mappa)


with open(file_out_protocollo, 'r', encoding='utf-8') as f:
    protocollo_data = json.load(f)

comuni_match = []
for file_data in protocollo_data.values():
    for item in file_data:
        if item.get("match_finale") and item.get("codice_comune"):
            comuni_match.append({
                "codice_provincia":item["codice_provincia"],
                "comune": item["match_finale"],
                "codice_comune": item["codice_comune"],
                "regione": item.get("regione", ""),
            })
df_comuni_match = pd.DataFrame(comuni_match)
df_comuni_match["codice_provincia"] = df_comuni_match["codice_provincia"].astype(str).str.zfill(3)
print(df_comuni_match)  

         
comuni_trovati = {}
for entries in protocollo_data.values():
    for entry in entries:
        regione = entry.get("regione")
        codice_prov = entry.get("codice_provincia")
        codice_comune = entry.get("codice_comune")
        if codice_prov and codice_comune:
            codice_prov = str(codice_prov).zfill(3)
            comuni_trovati.setdefault(codice_prov, set()).add(codice_comune)    

df_province = pd.read_csv(file_comuni_provincia, dtype={"codice_provincia": str})
df_province["codice_provincia"] = df_province["codice_provincia"].astype(str).str.zfill(3)


gdf = gpd.read_file(file_confini_province)
gdf["provincia"] = gdf["prov_name"].str.strip() 
gdf["codice_provincia"] = gdf["prov_istat_code"].astype(str).str.zfill(3)

comuni_per_provincia = df_province.set_index("codice_provincia")["numero_comuni"].to_dict()

percentuali = {
    codice_prov: (len(comuni_trovati.get(codice_prov, [])) / comuni_per_provincia.get(codice_prov, 1)) * 100
    for codice_prov in comuni_per_provincia
}
gdf["comuni_trovati"] = gdf["codice_provincia"].map(lambda cp: len(comuni_trovati.get(cp, [])))
gdf["numero_comuni"] = gdf["codice_provincia"].map(lambda cp: comuni_per_provincia.get(cp, 0))
gdf["percentuale"] = gdf["codice_provincia"].map(percentuali)
gdf["%"] = gdf.apply(
    lambda row: (
        f"{row['provincia']}: "
        f"{int(len(comuni_trovati.get(row['codice_provincia'], [])))} su "
        f"{comuni_per_provincia.get(row['codice_provincia'], 0)} comuni "
        f"({row['percentuale']:.1f}%)"
        if pd.notnull(row['percentuale']) and row['percentuale'] > 0
        else f"{row['provincia']}: nessun dato"
    ),
    axis=1
)

# === 4. Colormap dinamica ===
max_percentuale = gdf["percentuale"].max()
colormap = branca.colormap.LinearColormap(
    colors=[
        "#ff0000", "#ff3200", "#ff6400", "#ff9600", "#ffc800", "#ffff00",
        "#ccff00", "#99ff00", "#66ff00", "#33ff00", "#00ff00"
    ],
    vmin=0,
    vmax=max_percentuale,
    caption="Percentuale comuni trovati per provincia"
)

# === 5. Mappa ===
mappa = folium.Map(location=[42.5, 12.5], zoom_start=6, tiles="cartodbpositron")


tooltip = folium.GeoJsonTooltip(
    fields=["codice_provincia", "provincia", "comuni_trovati", "numero_comuni", "percentuale"],
    aliases=["Codice Provincia", "Provincia", "Trovati", "Totali", "%"],
    localize=True,
    sticky=True
)

folium.GeoJson(
    gdf,
    name="Percentuale comuni per provincia",
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

if max_percentuale > 0:
    colormap.add_to(mappa)    
    folium.LayerControl().add_to(mappa)

# === 6. Salva ===
mappa.save(file_out_mappa)
print(f"✅ Mappa salvata: {file_out_mappa}")
missing = gdf[~gdf["codice_provincia"].isin(percentuali.keys())]["codice_provincia"]
#print("Codici provincia non presenti nei dati comuni:", missing.tolist())