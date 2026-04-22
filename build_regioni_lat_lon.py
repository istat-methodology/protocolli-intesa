import json
import csv
from collections import defaultdict
from pathlib import Path

FILE_COMUNI = "geo-json\gi_comuni.json"
FILE_PROVINCE = "geo-json\province.json"   # file con chiave "resultset"
OUTPUT_JSON = "geo-json\gi_regioni.json"
OUTPUT_CSV = "geo-json\gi_regioni.csv"


def load_json(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File non trovato: {path}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def to_float(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def norm_str(value):
    if value is None:
        return ""
    return str(value).strip()


def norm_cod_reg(value):
    s = norm_str(value)
    if not s:
        return ""
    return s.zfill(2) if s.isdigit() else s


# =========================
# CARICAMENTO DATI
# =========================
comuni = load_json(FILE_COMUNI)
province_raw = load_json(FILE_PROVINCE)

# se il file province è del tipo {"resultset":[...]}
if isinstance(province_raw, dict) and "resultset" in province_raw:
    province = province_raw["resultset"]
elif isinstance(province_raw, list):
    province = province_raw
else:
    raise ValueError("Formato file province non riconosciuto")

# =========================
# MAPPE DA FILE PROVINCE
# =========================
sigla_to_regione = {}
region_info = {}

for p in province:
    sigla = norm_str(p.get("SIGLA_AUTOMOBILISTICA")).upper()
    cod_reg = norm_cod_reg(p.get("COD_REG"))
    den_reg = norm_str(p.get("DEN_REG"))
    den_rip = norm_str(p.get("DEN_RIP"))

    if sigla and cod_reg:
        sigla_to_regione[sigla] = cod_reg

    if cod_reg:
        region_info[cod_reg] = {
            "codice_regione": cod_reg,
            "denominazione_regione": den_reg,
            "area_geografica": den_rip,
        }

# =========================
# RAGGRUPPAMENTO COMUNI PER REGIONE
# =========================
comuni_per_regione = defaultdict(list)

for c in comuni:
    lat = to_float(c.get("lat"))
    lon = to_float(c.get("lon"))
    sigla = norm_str(c.get("sigla_provincia")).upper()

    if lat is None or lon is None or not sigla:
        continue

    cod_reg = sigla_to_regione.get(sigla)
    if not cod_reg:
        continue

    comuni_per_regione[cod_reg].append(c)

# =========================
# COSTRUZIONE OUTPUT
# =========================
output = []

for cod_reg in sorted(comuni_per_regione.keys()):
    lista = comuni_per_regione[cod_reg]

    lats = [to_float(c.get("lat")) for c in lista if to_float(c.get("lat")) is not None]
    lons = [to_float(c.get("lon")) for c in lista if to_float(c.get("lon")) is not None]

    lat_centroide = round(sum(lats) / len(lats), 6) if lats else None
    lon_centroide = round(sum(lons) / len(lons), 6) if lons else None

    info = region_info.get(cod_reg, {})

    record = {
        "codice_regione": cod_reg,
        "denominazione_regione": info.get("denominazione_regione", ""),
        "area_geografica": info.get("area_geografica", ""),
        "numero_comuni_dal_file_comuni": len(lista),
        "lat_centroide": lat_centroide,
        "lon_centroide": lon_centroide,
    }

    output.append(record)

# =========================
# SALVATAGGIO
# =========================
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

if output:
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

print(f"Creato: {OUTPUT_JSON}")
print(f"Creato: {OUTPUT_CSV}")
print(f"Regioni elaborate: {len(output)}")