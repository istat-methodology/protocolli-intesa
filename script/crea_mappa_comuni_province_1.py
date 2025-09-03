import os
import pandas as pd
import json
import folium
import geopandas as gpd
import branca

fld_out = "output"
fld_map = "maps"

file_protocollo = "comuni_out_end.json"
file_out_protocollo = os.path.join(fld_out, file_protocollo)

file_comuni_provincia = "comuni_provincia.csv" 
file_confini_province = "confini_province.geojson"

file_mappa = "mappa_comuni_province_1.html"
file_out_mappa = os.path.join(fld_map, file_mappa)

df = pd.read_csv("elenco comuni.csv", delimiter=';', encoding='latin1', dtype=str)
df = df.rename(columns={
    "Codice Regione":"codice_regione",
    "Denominazione Regione": "regione",
    "Denominazione dell'Unità territoriale sovracomunale (valida a fini statistici)": "provincia",
    "Codice Provincia (Storico)(1)":"codice_provincia",
    "Sigla automobilistica": "sigla_provincia",
    "Codice Comune formato numerico": "codice_comune"
})

df_prov = (
    df.groupby(["codice_regione", "codice_provincia"])
      .agg(numero_comuni=("codice_comune", "count"))
      .reset_index()
)

# Totali
tot_prov = df_prov.groupby("codice_provincia")["numero_comuni"].sum().rename("tot_prov").reset_index()
df_prov = df_prov.merge(tot_prov, on="codice_provincia")
df_prov["percentuale"] = (df_prov["numero_comuni"] / df_prov["tot_prov"]) * 100
df_prov.to_csv("comuni_provincia_ratio.csv", index=False, encoding="utf-8")

print("✅ CSV generato: comuni_per_provincia_ratio.csv")

prov_geo = gpd.read_file(file_confini_province)
prov_geo["provincia"] = prov_geo["prov_name"]


gdf = prov_geo.merge(df_prov, on="provincia", how="left")
gdf["percentuale"] = gdf["percentuale"].fillna(0)


max_pct = gdf["percentuale"].max()
colormap = branca.colormap.LinearColormap(
    colors=["white", "red", "orange", "yellow", "green"],
    vmin=0, vmax=max_pct,
    caption="Percentuale comuni della provincia sul totale regionale"
)


mappa = folium.Map(location=[42.5, 12.5], zoom_start=6, tiles="cartodbpositron")

folium.GeoJson(
    gdf,
    name="Province",
    style_function=lambda feat: {
        "fillColor": colormap(feat["properties"]["percentuale"]),
        "color": "gray",
        "weight": 0.5, 
        "fillOpacity": 0.7
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["regione", "codice_provincia", "numero_comuni", "percentuale"],
        aliases=[ "Regione:", "Provincia:", "N. comuni:", "% su regione:"],
        localize=True
    )
).add_to(mappa)

colormap.add_to(mappa)

mappa.save(file_out_mappa)
print(f"✅ Mappa salvata: {file_out_mappa}")

