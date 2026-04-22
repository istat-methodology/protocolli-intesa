import json
from pathlib import Path

nb_path = Path("notebook_mappe_reti_violenza_finale.ipynb")

cells = []

def md(text):
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": text.strip("\n").splitlines(keepends=True)
    })

def code(text):
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip("\n").splitlines(keepends=True)
    })

md("""
# Notebook finale — Mappe soggetti, ruoli e governance

Questo notebook:

- legge il file JSON enriched con coordinate
- attraversa correttamente la struttura annidata
- costruisce il `DataFrame` dei punti geocodificati
- crea filtri per firmatari, proponenti, attori e governance
- produce mappe `folium` con layer separati
- aggiunge i confini di regioni e province
- salva mappe HTML e CSV di riepilogo
""")

code(r'''
import json
from pathlib import Path

import pandas as pd
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import MarkerCluster

INPUT_JSON = r"output\data\step_3.0\3.0_risultati_enriched_geo.json"
GEOJSON_REGIONI = r"geo-json\limits_IT_regions.geojson"
GEOJSON_PROVINCE = r"geo-json\limits_IT_provinces.geojson"

OUTPUT_MAPPA = r"output\mappe\mappa_soggetti_layer.html"
OUTPUT_MAPPA_GOV = r"output\mappe\mappa_governance.html"
OUTPUT_DIR_TABLE = Path(r"output\reports\mappe")
''')

code(r'''
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    merged = json.load(f)

with open(GEOJSON_REGIONI, "r", encoding="utf-8") as f:
    geo_regioni = json.load(f)

with open(GEOJSON_PROVINCE, "r", encoding="utf-8") as f:
    geo_province = json.load(f)

print("JSON e GeoJSON caricati correttamente.")
''')

code(r'''
def iter_items(obj):
    """
    Restituisce tutti i record che contengono 'soggetti' o 'entities',
    qualunque sia la profondità della struttura JSON.
    """
    if isinstance(obj, dict):
        if "soggetti" in obj or "entities" in obj:
            yield obj
        for v in obj.values():
            yield from iter_items(v)

    elif isinstance(obj, list):
        for item in obj:
            yield from iter_items(item)


def iter_entities(item):
    """
    Restituisce la lista delle entità presenti nel record,
    supportando sia 'soggetti' sia 'entities'.
    """
    if not isinstance(item, dict):
        return []

    if isinstance(item.get("soggetti"), list):
        return [x for x in item["soggetti"] if isinstance(x, dict)]

    if isinstance(item.get("entities"), list):
        return [x for x in item["entities"] if isinstance(x, dict)]

    return []
''')

code(r'''
punti = []

for item in iter_items(merged):
    for ent in iter_entities(item):
        lat = ent.get("lat")
        lon = ent.get("lon")

        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            ruolo_raw = ent.get("ruolo", [])
            if isinstance(ruolo_raw, list):
                ruolo_txt = ", ".join(ruolo_raw)
            else:
                ruolo_txt = str(ruolo_raw or "")

            punti.append({
                "lat": float(lat),
                "lon": float(lon),
                "nome": ent.get("nome", ""),
                "comune": ent.get("comune", "") or ent.get("comune_matchato", ""),
                "provincia": ent.get("provincia", "") or ent.get("sigla_provincia", ""),
                "regione": ent.get("regione", ""),
                "tipo": ent.get("tipo", ""),
                "ruolo": ruolo_txt,
            })

print(f"Punti caricati: {len(punti)}")
if not punti:
    raise SystemExit("Nessun punto con lat/lon trovato nel file JSON enriched.")
''')

code(r'''
df_punti = pd.DataFrame(punti).copy()

for col in ["nome", "comune", "provincia", "regione", "tipo", "ruolo"]:
    if col not in df_punti.columns:
        df_punti[col] = ""
    df_punti[col] = df_punti[col].fillna("").astype(str).str.strip()

df_punti = df_punti.drop_duplicates(
    subset=["lat", "lon", "nome", "comune", "provincia", "regione", "tipo", "ruolo"]
).reset_index(drop=True)

print(df_punti.shape)
display(df_punti.head())
''')

code(r'''
df_punti["is_firmatario"] = df_punti["ruolo"].str.contains("firmatario", case=False, na=False)
df_punti["is_proponente"] = df_punti["ruolo"].str.contains("proponente", case=False, na=False)
df_punti["is_attore"] = df_punti["ruolo"].str.contains("attore", case=False, na=False)

df_punti["is_governance"] = df_punti["ruolo"].str.contains(
    r"governance|gestione|coordinamento|monitoraggio",
    case=False,
    na=False,
    regex=True
)

df_punti["is_gestione"] = df_punti["ruolo"].str.contains("gestione", case=False, na=False)
df_punti["is_monitoraggio"] = df_punti["ruolo"].str.contains("monitoraggio", case=False, na=False)
df_punti["is_coordinamento"] = df_punti["ruolo"].str.contains("coordinamento", case=False, na=False)

print("Totale punti:", len(df_punti))
print("Firmatari:", int(df_punti["is_firmatario"].sum()))
print("Proponenti:", int(df_punti["is_proponente"].sum()))
print("Attori:", int(df_punti["is_attore"].sum()))
print("Governance:", int(df_punti["is_governance"].sum()))
print("Gestione:", int(df_punti["is_gestione"].sum()))
print("Monitoraggio:", int(df_punti["is_monitoraggio"].sum()))
print("Coordinamento:", int(df_punti["is_coordinamento"].sum()))
''')

code(r'''
df_firmatari = df_punti[df_punti["is_firmatario"]].copy()
df_proponenti = df_punti[df_punti["is_proponente"]].copy()
df_attori = df_punti[df_punti["is_attore"]].copy()
df_governance = df_punti[df_punti["is_governance"]].copy()
df_gestione = df_punti[df_punti["is_gestione"]].copy()
df_monitoraggio = df_punti[df_punti["is_monitoraggio"]].copy()
df_coordinamento = df_punti[df_punti["is_coordinamento"]].copy()

display(df_governance.head())
''')

code(r'''
def filtra_punti(df, tipi=None, ruolo_contains=None, solo_governance=False, regioni=None):
    out = df.copy()

    if tipi:
        out = out[out["tipo"].isin(tipi)]

    if ruolo_contains:
        out = out[
            out["ruolo"].str.contains(ruolo_contains, case=False, na=False, regex=True)
        ]

    if solo_governance:
        out = out[out["is_governance"]]

    if regioni:
        out = out[out["regione"].isin(regioni)]

    return out.reset_index(drop=True)
''')

code(r'''
def style_regioni(feature):
    return {
        "fillColor": "#00000000",
        "color": "#cc0000",
        "weight": 2,
        "fillOpacity": 0.0,
    }


def style_province(feature):
    return {
        "fillColor": "#00000000",
        "color": "#666666",
        "weight": 1,
        "fillOpacity": 0.0,
    }
''')

code(r'''
COLORI = {
    "tutti": "#808080",
    "firmatari": "#1f77b4",
    "proponenti": "#d62728",
    "attori": "#2ca02c",
    "governance": "#9467bd",
    "gestione": "#ff7f0e",
    "monitoraggio": "#17becf",
    "coordinamento": "#8c564b",
}
''')

code(r'''
def make_popup_html(row):
    return f"""
    <b>{row.get('nome', '')}</b><br>
    Tipo: {row.get('tipo', '')}<br>
    Ruolo: {row.get('ruolo', '')}<br>
    Comune: {row.get('comune', '')}<br>
    Provincia: {row.get('provincia', '')}<br>
    Regione: {row.get('regione', '')}
    """


def add_points_to_cluster_with_fixed_color(df, cluster, color):
    for _, row in df.iterrows():
        popup_html = make_popup_html(row)

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=row.get("nome", ""),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            weight=1
        ).add_to(cluster)
''')

code(r'''
centro_lat = df_punti["lat"].mean()
centro_lon = df_punti["lon"].mean()

mappa = folium.Map(
    location=[centro_lat, centro_lon],
    zoom_start=6,
    tiles="OpenStreetMap"
)

layer_tutti = FeatureGroup(name="Tutti i soggetti", show=True)
layer_firmatari = FeatureGroup(name="Firmatari", show=False)
layer_proponenti = FeatureGroup(name="Proponenti", show=False)
layer_attori = FeatureGroup(name="Attori", show=False)
layer_governance = FeatureGroup(name="Governance", show=True)
layer_gestione = FeatureGroup(name="Gestione", show=False)
layer_monitoraggio = FeatureGroup(name="Monitoraggio", show=False)
layer_coordinamento = FeatureGroup(name="Coordinamento", show=False)
layer_regioni = FeatureGroup(name="Confini regioni", show=True)
layer_province = FeatureGroup(name="Confini province", show=False)

cluster_tutti = MarkerCluster().add_to(layer_tutti)
cluster_firmatari = MarkerCluster().add_to(layer_firmatari)
cluster_proponenti = MarkerCluster().add_to(layer_proponenti)
cluster_attori = MarkerCluster().add_to(layer_attori)
cluster_governance = MarkerCluster().add_to(layer_governance)
cluster_gestione = MarkerCluster().add_to(layer_gestione)
cluster_monitoraggio = MarkerCluster().add_to(layer_monitoraggio)
cluster_coordinamento = MarkerCluster().add_to(layer_coordinamento)

add_points_to_cluster_with_fixed_color(df_punti, cluster_tutti, COLORI["tutti"])
add_points_to_cluster_with_fixed_color(df_firmatari, cluster_firmatari, COLORI["firmatari"])
add_points_to_cluster_with_fixed_color(df_proponenti, cluster_proponenti, COLORI["proponenti"])
add_points_to_cluster_with_fixed_color(df_attori, cluster_attori, COLORI["attori"])
add_points_to_cluster_with_fixed_color(df_governance, cluster_governance, COLORI["governance"])
add_points_to_cluster_with_fixed_color(df_gestione, cluster_gestione, COLORI["gestione"])
add_points_to_cluster_with_fixed_color(df_monitoraggio, cluster_monitoraggio, COLORI["monitoraggio"])
add_points_to_cluster_with_fixed_color(df_coordinamento, cluster_coordinamento, COLORI["coordinamento"])

folium.GeoJson(
    geo_regioni,
    name="Regioni",
    style_function=style_regioni
).add_to(layer_regioni)

folium.GeoJson(
    geo_province,
    name="Province",
    style_function=style_province
).add_to(layer_province)

layer_tutti.add_to(mappa)
layer_firmatari.add_to(mappa)
layer_proponenti.add_to(mappa)
layer_attori.add_to(mappa)
layer_governance.add_to(mappa)
layer_gestione.add_to(mappa)
layer_monitoraggio.add_to(mappa)
layer_coordinamento.add_to(mappa)
layer_regioni.add_to(mappa)
layer_province.add_to(mappa)

LayerControl(collapsed=False).add_to(mappa)

legend_html = """
<div style="
position: fixed; 
bottom: 40px; left: 40px; width: 230px; 
background-color: white; 
border: 2px solid grey; 
z-index: 9999; 
font-size: 14px;
padding: 10px;
box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
">
<b>Legenda ruoli</b><br>
<span style="color:#808080;">●</span> Tutti i soggetti<br>
<span style="color:#1f77b4;">●</span> Firmatari<br>
<span style="color:#d62728;">●</span> Proponenti<br>
<span style="color:#2ca02c;">●</span> Attori<br>
<span style="color:#9467bd;">●</span> Governance<br>
<span style="color:#ff7f0e;">●</span> Gestione<br>
<span style="color:#17becf;">●</span> Monitoraggio<br>
<span style="color:#8c564b;">●</span> Coordinamento
</div>
"""
mappa.get_root().html.add_child(folium.Element(legend_html))

mappa
''')

code(r'''
Path(OUTPUT_MAPPA).parent.mkdir(parents=True, exist_ok=True)
mappa.save(OUTPUT_MAPPA)
print(f"Mappa salvata in: {OUTPUT_MAPPA}")
''')

code(r'''
if len(df_governance) > 0:
    centro_lat_gov = df_governance["lat"].mean()
    centro_lon_gov = df_governance["lon"].mean()
else:
    centro_lat_gov, centro_lon_gov = 41.9, 12.5

mappa_governance = folium.Map(
    location=[centro_lat_gov, centro_lon_gov],
    zoom_start=6,
    tiles="OpenStreetMap"
)

cluster_gov = MarkerCluster().add_to(mappa_governance)
add_points_to_cluster_with_fixed_color(df_governance, cluster_gov, COLORI["governance"])

layer_regioni_gov = FeatureGroup(name="Confini regioni", show=True)
layer_province_gov = FeatureGroup(name="Confini province", show=False)

folium.GeoJson(
    geo_regioni,
    name="Regioni",
    style_function=style_regioni
).add_to(layer_regioni_gov)

folium.GeoJson(
    geo_province,
    name="Province",
    style_function=style_province
).add_to(layer_province_gov)

layer_regioni_gov.add_to(mappa_governance)
layer_province_gov.add_to(mappa_governance)

LayerControl(collapsed=False).add_to(mappa_governance)

legend_html_gov = """
<div style="
position: fixed; 
bottom: 40px; left: 40px; width: 180px; 
background-color: white; 
border: 2px solid grey; 
z-index: 9999; 
font-size: 14px;
padding: 10px;
box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
">
<b>Legenda</b><br>
<span style="color:#9467bd;">●</span> Governance
</div>
"""
mappa_governance.get_root().html.add_child(folium.Element(legend_html_gov))

mappa_governance
''')

code(r'''
Path(OUTPUT_MAPPA_GOV).parent.mkdir(parents=True, exist_ok=True)
mappa_governance.save(OUTPUT_MAPPA_GOV)
print(f"Mappa governance salvata in: {OUTPUT_MAPPA_GOV}")
''')

code(r'''
tab_gov_regione = (
    df_governance.groupby("regione", dropna=False)
    .size()
    .reset_index(name="n_governance")
    .sort_values("n_governance", ascending=False)
    .reset_index(drop=True)
)

display(tab_gov_regione)
''')

code(r'''
tab_gov_tipo = (
    df_governance.groupby(["regione", "tipo"], dropna=False)
    .size()
    .reset_index(name="n")
    .sort_values(["regione", "n"], ascending=[True, False])
    .reset_index(drop=True)
)

display(tab_gov_tipo.head(100))
''')

code(r'''
df_cav = filtra_punti(
    df_punti,
    tipi=["CAV/Centri Antiviolenza", "Case Rifugio"]
)

df_gov_toscana = filtra_punti(
    df_punti,
    solo_governance=True,
    regioni=["Toscana"]
)

df_prop = filtra_punti(
    df_punti,
    ruolo_contains="proponente"
)

display(df_cav.head())
display(df_gov_toscana.head())
display(df_prop.head())
''')

code(r'''
OUTPUT_DIR_TABLE.mkdir(parents=True, exist_ok=True)

df_punti.to_csv(OUTPUT_DIR_TABLE / "punti_geocodificati.csv", index=False, encoding="utf-8-sig")
df_governance.to_csv(OUTPUT_DIR_TABLE / "punti_governance.csv", index=False, encoding="utf-8-sig")
tab_gov_regione.to_csv(OUTPUT_DIR_TABLE / "tabella_governance_per_regione.csv", index=False, encoding="utf-8-sig")
tab_gov_tipo.to_csv(OUTPUT_DIR_TABLE / "tabella_governance_per_tipo.csv", index=False, encoding="utf-8-sig")

print("CSV esportati in:", OUTPUT_DIR_TABLE)
''')

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.x"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

with nb_path.open("w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=2)

print(f"Notebook creato: {nb_path}")
