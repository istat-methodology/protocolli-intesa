import json
import os
from collections import OrderedDict, defaultdict
import re
import pandas as pd
from pathlib import Path
import unicodedata
import math
import statistics
import folium
import matplotlib.pyplot as plt

REGIONE2CODICE = {
    "piemonte": "01",
    "valle d'aosta": "02",
    "valledaosta": "02",
    "lombardia": "03",
    "trentino alto adige": "04",
    "trentino-alto adige": "04",
    "veneto": "05",
    "friuli venezia giulia": "06",
    "liguria": "07",
    "emilia-romagna": "08",
    "emilia romagna": "08",
    "toscana": "09",
    "umbria": "10",
    "marche": "11",
    "lazio": "12",
    "abruzzo": "13",
    "molise": "14",
    "campania": "15",
    "puglia": "16",
    "basilicata": "17",
    "calabria": "18",
    "sicilia": "19",
    "sardegna": "20",
}

JSON_STEP2_FOLDER = "output/json/step_2/"
JSON_STEP3_FOLDER = "output/json/step_3/"
MAP_FOLDER = "output/mappe/"
REPORT_FOLDER = "output/report/"
GRAFICI_FOLDER = "output/grafici/"

GEOJSON_REGIONI = "geo-json/confini_regioni.geojson"
GEOJSON_PROVINCE = "geo-json/confini_province.geojson"
MERGED_JSON = "output/json/merged/merged_json.json"

riepilogo_comuni_csv = f"{REPORT_FOLDER}riepilogo_comuni.csv"
riepilogo_codici_reg_pro_com_comune_csv = f"{REPORT_FOLDER}riepilogo_codici_reg_pro_com_comuni.csv"
riepilogo_codici_pro_com_comune_csv = f"{REPORT_FOLDER}riepilogo_codici_pro_com_comuni.csv"
riepilogo_codici_comuni_csv = f"{REPORT_FOLDER}riepilogo_codici_comuni.csv"
riepilogo_province_csv = f"{REPORT_FOLDER}riepilogo_province.csv"
riepilogo_regioni_csv = f"{REPORT_FOLDER}riepilogo_regioni.csv"
riepilogo_italia_csv = f"{REPORT_FOLDER}riepilogo_italia.csv"
report_riepilogo_xls = f"{REPORT_FOLDER}report_riepilogo.xlsx"

bar_regioni_entita = f"{GRAFICI_FOLDER}bar_regioni_entita.png"
bar_province_top20_entita = f"{GRAFICI_FOLDER}bar_province_top20_entita.png"
bar_comuni_top20_entita = f"{GRAFICI_FOLDER}bar_comuni_top20_entita.png"
bar_regioni_numcomuni = f"{GRAFICI_FOLDER}bar_regioni_numcomuni.png"

mappa_confini_regionali = f"{MAP_FOLDER}mappa_con_confini_regionali.html"
mappa_confini_provinciali = f"{MAP_FOLDER}mappa_con_confini_provinciali.html"
mappa_province_con_punti_interni = f"{MAP_FOLDER}mappa_province_con_punti_interni.html"

# Centro mappa: mediana delle coordinate (più robusta agli outlier)
center_lat = 41.9028
center_lon = 12.4964
zoom_start = 6

TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
ATTR  = "&copy; <a href='http://osm.org/copyright'>OpenStreetMap</a>"
REG_NAME = "Regioni"
PRO_NAME = "Province"

# ---------- CARICAMENTO COMUNI ----------
df_comuni = pd.read_csv('classification/cls_comuni.csv', encoding='latin1', sep=';')

df_comuni_clean = df_comuni[[
    "Codice Regione",
    "Codice Provincia",
    "Progressivo del Comune",
    "Denominazione in italiano"
]].copy()

df_comuni_clean = df_comuni_clean.rename(columns={
    "Codice Regione": "codice_regione",
    "Codice Provincia": "codice_provincia",
    "Progressivo del Comune": "progressivo",
    "Denominazione in italiano": "denominazione_italiana"
})

df_comuni_clean["codice_regione"]   = df_comuni_clean["codice_regione"].astype(str).str.zfill(2)
df_comuni_clean["codice_provincia"] = df_comuni_clean["codice_provincia"].astype(str).str.zfill(3)
df_comuni_clean["progressivo"]      = df_comuni_clean["progressivo"].astype(str).str.zfill(3)

df_comuni_clean["codice_comune"] = (
    df_comuni_clean["codice_regione"] +
    df_comuni_clean["codice_provincia"] +
    df_comuni_clean["progressivo"]
)

df_comuni_clean = df_comuni_clean[[
    "codice_regione",
    "codice_provincia",
    "progressivo",
    "codice_comune",
    "denominazione_italiana"
]]


# ---------- ENRICH JSON ----------

def enrich_with_geo(input_file: str, output_file: str,
                    comuni_file: str = "data/gi_comuni.json"):
    """
    Arricchisce un file JSON di risultati con:
      - codice_regione (01..20)
      - codice_provincia (prime 3 cifre codice ISTAT comune)
      - codice_comune (codice ISTAT a 6 cifre)
      - lat, lon del comune (se trovati)
    """

    def normalize_name(s: str) -> str:
        if not isinstance(s, str):
            return ""
        s0 = s.strip().casefold()
        s1 = "".join(c for c in unicodedata.normalize("NFKD", s0) if not unicodedata.combining(c))
        s1 = s1.replace("\u2019", "'").replace("`", "'").replace("\u00b4", "'")
        s1 = " ".join(s1.split())
        return s1

    with open(input_file, "r", encoding="utf-8") as f:
        risultati = json.load(f)

    comuni_path = comuni_file if os.path.exists(comuni_file) else "data/gi_comuni.json"
    with open(comuni_path, "r", encoding="utf-8") as f:
        comuni = json.load(f)

    by_name = defaultdict(list)
    for rec in comuni:
        nome = normalize_name(rec.get("denominazione_ita") or rec.get("denominazione_ita_altra") or "")
        if nome:
            by_name[nome].append(rec)

    def best_match(records, provincia_entity):
        if not records:
            return None
        if provincia_entity:
            prov_norm = normalize_name(provincia_entity)
            for r in records:
                if (r.get("sigla_provincia") or "").lower() == prov_norm:
                    return r
        return records[0]

    def enrich_entity(ent: dict) -> dict:
        comune_norm = normalize_name(ent.get("comune") or "")
        regione_norm = normalize_name(ent.get("regione") or "")
        records = by_name.get(comune_norm, [])
        match = best_match(records, ent.get("provincia"))

        ent["codice_regione"] = REGIONE2CODICE.get(regione_norm, "")
        ent["codice_provincia"] = ""
        ent["codice_comune"] = ""

        if match:
            codice_comune = str(match.get("codice_istat") or "")
            ent["codice_comune"] = codice_comune
            if len(codice_comune) >= 3:
                ent["codice_provincia"] = codice_comune[:3]
            try:
                ent["lat"] = float(match["lat"])
                ent["lon"] = float(match["lon"])
            except Exception:
                pass

        return ent

    for item in risultati:
        for ent in item.get("entities", []):
            enrich_entity(ent)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)

    print(f"\u2705 Salvato enrich json: {output_file}")
    return output_file


# ---------- MAIN LOOP ENRICH ----------

for codice in range(12, 12 + 1):
    input_file  = f"{JSON_STEP2_FOLDER}{codice:02d}.1_risultati.json"
    output_file = f"{JSON_STEP3_FOLDER}{codice:02d}.1_risultati.json"

    if not os.path.exists(input_file):
        print(f"\u26a0\ufe0f File non trovato: {input_file}, skip")
        continue

    print(f"\n=== Regione {codice:02d} ===")
    print(f"\U0001f4e5 Input:  {input_file}")
    print(f"\U0001f4e4 Output: {output_file}")

    enrich_with_geo(input_file, output_file)


# ---------- MERGE JSON ----------

def merge_json_folder(input_folder, output_file):
    """
    Legge tutti i file JSON nella cartella input_folder e li unisce in un unico file.
    """
    merged = []
    for fname in sorted(os.listdir(input_folder)):
        if fname.lower().endswith('.json'):
            path = os.path.join(input_folder, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    merged.extend(data)
                else:
                    print(f"Attenzione: il file {fname} non contiene una lista, lo aggiungo comunque.")
                    merged.append(data)
            except Exception as e:
                print(f"Errore nel file {fname}: {e}")
    with open(output_file, 'w', encoding='utf-8') as fout:
        json.dump(merged, fout, ensure_ascii=False, indent=2)


merge_json_folder(JSON_STEP3_FOLDER, MERGED_JSON)
print(f"Fatti: i file enriched sono stati uniti in {MERGED_JSON}")


# ---------- UTILITIES GEO ----------

def point_in_ring(lat, lon, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        cond = ((y1 > lat) != (y2 > lat)) and (lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-15) + x1)
        if cond:
            inside = not inside
    return inside

def point_in_polygon(lat, lon, polygon_coords):
    if not polygon_coords:
        return False
    outer = polygon_coords[0]
    if not point_in_ring(lat, lon, outer):
        return False
    for hole in polygon_coords[1:]:
        if point_in_ring(lat, lon, hole):
            return False
    return True

def point_in_multipolygon(lat, lon, multipolygon_coords):
    for poly in multipolygon_coords:
        if point_in_polygon(lat, lon, poly):
            return True
    return False

def point_in_feature(lat, lon, feature):
    geom = feature.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        return point_in_polygon(lat, lon, coords)
    if gtype == "MultiPolygon":
        return point_in_multipolygon(lat, lon, coords)
    return False

def guess_feature_name(feature, fallback_prefix="feature"):
    props = feature.get("properties") or {}
    candidate_keys = [
        "provincia", "PROVINCIA", "DEN_PROV", "DENOM_PROV", "NOME_PROV", "NAME_2",
        "SIGLA", "SIGLA_PROV",
        "regione", "REGIONE", "DEN_REG", "DENOM_REG", "NOME_REG", "NAME_1",
        "name", "Name", "NOME", "DENOMINAZIONE", "DEN_UTS", "DENOM"
    ]
    for k in candidate_keys:
        if k in props and props[k]:
            return str(props[k])
    fid = feature.get("id")
    if fid is not None:
        return f"{fallback_prefix}_{fid}"
    for k, v in props.items():
        if v:
            return f"{fallback_prefix}_{str(v)[:24]}"
    return f"{fallback_prefix}_sconosciuto"


# ---------- CARICAMENTI ----------

with open(MERGED_JSON, "r", encoding="utf-8") as f:
    merged = json.load(f)

with open(GEOJSON_REGIONI, "r", encoding="utf-8") as f:
    geo_regioni = json.load(f)

with open(GEOJSON_PROVINCE, "r", encoding="utf-8") as f:
    geo_province = json.load(f)

punti = []
for item in merged:
    for ent in item.get("entities", []):
        lat = ent.get("lat")
        lon = ent.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            punti.append({
                "lat": float(lat),
                "lon": float(lon),
                "nome": ent.get("nome", ""),
                "comune": ent.get("comune", ""),
                "provincia": ent.get("provincia", ""),
                "regione": ent.get("regione", ""),
            })

if not punti:
    raise SystemExit("Nessun punto con lat/lon trovato in merged_json.json")


# ---------- RIEPILOGO DATI ----------

def norm_provincia(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    return s

rows = []
for item in merged:
    for ent in item.get("entities", []):
        codice_comune = ent.get("codice_regione", "") + ent.get("codice_comune", "")
        rows.append({
            "nome_entita": ent.get("nome", ""),
            "comune": df_comuni_clean[df_comuni_clean["codice_comune"] == codice_comune]["denominazione_italiana"].values[0]
                      if codice_comune in df_comuni_clean["codice_comune"].values else ent.get("comune", ""),
            "provincia": norm_provincia(ent.get("provincia", "")),
            "regione": ent.get("regione", ""),
            "codiceregione": ent.get("codice_regione", ""),
            "codiceprovincia": ent.get("codice_provincia", ""),
            "codicecomune": ent.get("codice_comune", "")
        })

df = pd.DataFrame(rows)

agg_codici_reg_pro_com_comune = (
    df.groupby(["codiceregione", "codiceprovincia", "codicecomune", "comune"], dropna=False)
      .agg(n_entita=("nome_entita", "count"))
      .reset_index()
)

agg_codici_pro_com_comune = (
    df.groupby(["codiceprovincia", "codicecomune", "comune"], dropna=False)
      .agg(n_entita=("nome_entita", "count"))
      .reset_index()
)

agg_codice_comune = (
    df.groupby(["codicecomune", "comune"], dropna=False)
      .agg(n_entita=("nome_entita", "count"))
      .reset_index()
)

agg_comune = (
    df.groupby(["regione", "provincia", "comune"], dropna=False)
      .agg(n_entita=("nome_entita", "count"))
      .reset_index()
)

agg_prov = (
    df.groupby(["regione", "provincia"], dropna=False)
      .agg(
          n_entita=("nome_entita", "count"),
          n_comuni=("comune", lambda s: s.astype(str).replace({"": None}).nunique())
      )
      .reset_index()
)

agg_reg = (
    df.groupby(["regione"], dropna=False)
      .agg(
          n_entita=("nome_entita", "count"),
          n_province=("provincia", lambda s: s.astype(str).replace({"": None}).nunique()),
          n_comuni=("comune",      lambda s: s.astype(str).replace({"": None}).nunique()),
      )
      .reset_index()
)

tot_italia = pd.DataFrame([{
    "n_entita": int(df["nome_entita"].count()),
    "n_regioni": int(df["regione"].astype(str).replace({"": None}).nunique()),
    "n_province": int(df["provincia"].astype(str).replace({"": None}).nunique()),
    "n_comuni": int(df["comune"].astype(str).replace({"": None}).nunique()),
}])

# Crea cartelle di output se non esistono
for folder in [REPORT_FOLDER, GRAFICI_FOLDER, MAP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

agg_codici_reg_pro_com_comune.to_csv(riepilogo_codici_reg_pro_com_comune_csv, index=False, encoding="utf-8")
agg_codici_pro_com_comune.to_csv(riepilogo_codici_pro_com_comune_csv, index=False, encoding="utf-8")
agg_comune.to_csv(riepilogo_comuni_csv, index=False, encoding="utf-8")
agg_codice_comune.to_csv(riepilogo_codici_comuni_csv, index=False, encoding="utf-8")
agg_prov.to_csv(riepilogo_province_csv, index=False, encoding="utf-8")
agg_reg.to_csv(riepilogo_regioni_csv, index=False, encoding="utf-8")
tot_italia.to_csv(riepilogo_italia_csv, index=False, encoding="utf-8")

with pd.ExcelWriter(report_riepilogo_xls, engine="xlsxwriter") as xlw:
    agg_comune.to_excel(xlw, sheet_name="Comuni", index=False)
    agg_prov.to_excel(xlw, sheet_name="Province", index=False)
    agg_reg.to_excel(xlw, sheet_name="Regioni", index=False)
    tot_italia.to_excel(xlw, sheet_name="Italia", index=False)

print("Tabelle create in:", REPORT_FOLDER)


# ---------- MAPPA 1: confini REGIONALI ----------

m_regioni = folium.Map(location=(center_lat, center_lon), zoom_start=zoom_start, tiles=None, control_scale=True)

folium.TileLayer(tiles=TILES, attr=ATTR, name=REG_NAME).add_to(m_regioni)

folium.GeoJson(
    geo_regioni,
    name="Confini regionali",
    style_function=lambda feat: {"fillColor": "transparent", "color": "#333333", "weight": 1}
).add_to(m_regioni)

fg_punti_reg = folium.FeatureGroup(name=f"Comuni (tutti i punti) [{len(punti)}]", show=True)
for p in punti:
    lat, lon = p.get("lat"), p.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        folium.CircleMarker(
            location=(lat, lon),
            radius=5,
            color="#d62728",
            fill=True,
            fill_opacity=0.6,
            popup=folium.Popup(
                f"Comune: {p['comune']}<br/>Provincia: {p['provincia']}<br/>Regione: {p['regione']}",
                max_width=300
            ),
        ).add_to(fg_punti_reg)
fg_punti_reg.add_to(m_regioni)

folium.LayerControl(collapsed=False).add_to(m_regioni)

m_regioni.save(mappa_confini_regionali)
print("Fatto:")
print(mappa_confini_regionali)


# ---------- MAPPA 2: confini PROVINCIALI ----------

m_province = folium.Map(location=(center_lat, center_lon), zoom_start=zoom_start, control_scale=True, tiles=None)

folium.TileLayer(tiles=TILES, attr=ATTR, name=PRO_NAME).add_to(m_province)

folium.GeoJson(
    geo_province,
    name="Confini provinciali",
    style_function=lambda feat: {"fillColor": "transparent", "color": "#666666", "weight": 1}
).add_to(m_province)

fg_punti_prov = folium.FeatureGroup(name="Comuni (tutti i punti)", show=True)
for p in punti:
    folium.CircleMarker(
        location=(p["lat"], p["lon"]),
        radius=5,
        color="#1f77b4",
        fill=True,
        fill_opacity=0.6,
        popup=folium.Popup(
            f"<b>{p['nome']}</b><br/>Comune: {p['comune']}<br/>Provincia: {p['provincia']}<br/>Regione: {p['regione']}",
            max_width=300
        ),
    ).add_to(fg_punti_prov)
fg_punti_prov.add_to(m_province)

folium.LayerControl(collapsed=False).add_to(m_province)

m_province.save(mappa_confini_provinciali)
print("Fatto:")
print(mappa_confini_provinciali)


# ---------- MAPPA 3: layer per ciascuna PROVINCIA ----------

m_province_layers = folium.Map(location=(center_lat, center_lon), zoom_start=zoom_start, control_scale=True, tiles=None)

folium.TileLayer(tiles=TILES, attr=ATTR, name=PRO_NAME).add_to(m_province_layers)

folium.GeoJson(
    geo_province,
    name="Confini provinciali (sfondo)",
    style_function=lambda feat: {"fillColor": "transparent", "color": "#aaaaaa", "weight": 0.8}
).add_to(m_province_layers)

features_prov = geo_province.get("features", [])
for idx, feat in enumerate(features_prov):
    prov_name = guess_feature_name(feat, fallback_prefix="prov")
    fg = folium.FeatureGroup(name=f"Provincia: {prov_name}", show=False)

    folium.GeoJson(
        feat,
        name=f"Confine {prov_name}",
        style_function=lambda f: {"fillColor": "transparent", "color": "#000000", "weight": 2},
        highlight_function=lambda f: {"weight": 3, "color": "#111111"},
        tooltip=prov_name
    ).add_to(fg)

    for p in punti:
        if point_in_feature(p["lat"], p["lon"], feat):
            folium.CircleMarker(
                location=(p["lat"], p["lon"]),
                radius=5,
                color="#2ca02c",
                fill=True,
                fill_opacity=0.7,
                popup=folium.Popup(
                    f"<b>{p['nome']}</b><br/>Comune: {p['comune']}<br/>Provincia: {p['provincia']}<br/>Regione: {p['regione']}",
                    max_width=300
                ),
            ).add_to(fg)

    fg.add_to(m_province_layers)

folium.LayerControl(collapsed=False).add_to(m_province_layers)

m_province_layers.save(mappa_province_con_punti_interni)
print("Fatto:")
print(mappa_province_con_punti_interni)


# ---------- GRAFICI A BARRE ----------

def barh_save(labels, values, title, xlabel, outfile, figsize=(10, 6)):
    plt.figure(figsize=figsize)
    zipped = sorted(zip(values, labels), reverse=True)
    vals_sorted = [v for v, _ in zipped]
    labs_sorted = [l for _, l in zipped]
    plt.barh(labs_sorted, vals_sorted)
    plt.xlabel(xlabel)
    plt.title(title)
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close()


labels_reg = agg_reg["regione"].fillna("— Nessuna").astype(str).tolist()
vals_reg   = agg_reg["n_entita"].astype(int).tolist()
barh_save(labels_reg, vals_reg,
          title="Entità per Regione",
          xlabel="N. entità",
          outfile=bar_regioni_entita,
          figsize=(10, max(4, 0.35 * len(labels_reg))))

topN = 20
agg_prov_top = agg_prov.sort_values("n_entita", ascending=False).head(topN)
labels_prov  = (agg_prov_top["regione"].fillna("—") + " – " + agg_prov_top["provincia"].fillna("—")).tolist()
vals_prov    = agg_prov_top["n_entita"].astype(int).tolist()
barh_save(labels_prov, vals_prov,
          title=f"Entità per Provincia (Top {topN})",
          xlabel="N. entità",
          outfile=bar_province_top20_entita,
          figsize=(10, max(4, 0.35 * len(labels_prov))))

agg_comune_top = agg_comune.sort_values("n_entita", ascending=False).head(topN)
labels_com = (agg_comune_top["regione"].fillna("—") + " – " +
              agg_comune_top["provincia"].fillna("—") + " – " +
              agg_comune_top["comune"].fillna("—")).tolist()
vals_com   = agg_comune_top["n_entita"].astype(int).tolist()
barh_save(labels_com, vals_com,
          title=f"Entità per Comune (Top {topN})",
          xlabel="N. entità",
          outfile=bar_comuni_top20_entita,
          figsize=(12, max(4, 0.35 * len(labels_com))))

labels_reg_c = agg_reg["regione"].fillna("— Nessuna").astype(str).tolist()
vals_reg_c   = agg_reg["n_entita"].astype(int).tolist()
barh_save(labels_reg_c, vals_reg_c,
          title="Numero di Comuni per Regione",
          xlabel="N. comuni",
          outfile=bar_regioni_numcomuni,
          figsize=(10, max(4, 0.35 * len(labels_reg_c))))

print("Grafici creati:")
print(bar_regioni_entita)
print(bar_province_top20_entita)
print(bar_comuni_top20_entita)
print(bar_regioni_numcomuni)


# ---------- REPORT HTML ----------

report_html = Path("report.html")
report_html.write_text(f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Report Mappe & Riepiloghi</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
h1, h2 {{ margin: 0.6em 0; }}
section {{ margin: 24px 0; }}
a {{ text-decoration: none; }}
img {{ max-width: 100%; height: auto; border: 1px solid #ddd; padding: 4px; }}
ul {{ line-height: 1.6; }}
.code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #f6f8fa; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>Report mappe, tabelle e grafici</h1>

<section>
  <h2>Mappe</h2>
  <ul>
    <li><a href="{mappa_confini_regionali}">Mappa: Confini regionali + punti</a></li>
    <!--li><a href="{mappa_confini_provinciali}">Mappa: Confini provinciali + punti</a></li>
    <li><a href="{mappa_province_con_punti_interni}">Mappa: Layer per provincia (solo punti interni)</a></li--!>
  </ul>
</section>

<section>
  <h2>Tabelle (CSV & Excel)</h2>
  <ul>
    <li><a href="{riepilogo_comuni_csv}">riepilogo_comuni.csv</a></li>
    <li><a href="{riepilogo_province_csv}">riepilogo_province.csv</a></li>
    <li><a href="{riepilogo_regioni_csv}">riepilogo_regioni.csv</a></li>
    <li><a href="{riepilogo_italia_csv}">riepilogo_italia.csv</a></li>
    <li><a href="{report_riepilogo_xls}">report_riepilogo.xlsx</a></li>
  </ul>
</section>

<section>
  <h2>Grafici</h2>
  <p>Nota: i grafici sono ordinati per valore (decrescente).</p>
  <h3>Entità per Regione</h3>
  <img src="{bar_regioni_entita}" alt="Entità per Regione">
  <h3>Entità per Provincia (Top 20)</h3>
  <img src="{bar_province_top20_entita}" alt="Entità per Provincia Top 20">
  <h3>Entità per Comune (Top 20)</h3>
  <img src="{bar_comuni_top20_entita}" alt="Entità per Comune Top 20">
  <h3>Numero di Comuni per Regione</h3>
  <img src="{bar_regioni_numcomuni}" alt="Numero di Comuni per Regione">
</section>

<section>
  <h2>Come riprodurre</h2>
  <p>Esegui lo script con Python 3.10+ e i pacchetti <span class="code">folium</span>, <span class="code">pandas</span>, <span class="code">xlsxwriter</span>, <span class="code">matplotlib</span>.</p>
  <p>Esempio:</p>
  <pre class="code">python protocolli_s4.1_mappe.py</pre>
</section>

</body>
</html>
""", encoding="utf-8")

print("Creato report HTML: report.html")
