import json
import csv
from collections import defaultdict
from pathlib import Path

FILE_COMUNI = Path("geo-json\\gi_comuni.json")
FILE_PROVINCE = Path("geo-json\\province.json")   # file con chiave "resultset"

OUTPUT_JSON = Path("geo-json\\gi_provincen.json")
OUTPUT_CSV = Path("geo-json\\gi_province.csv")


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


def norm_cod(value, width=2):
    s = norm_str(value)
    if not s:
        return ""
    return s.zfill(width) if s.isdigit() else s


# =========================
# CARICAMENTO DATI
# =========================
comuni = load_json(FILE_COMUNI)
province_raw = load_json(FILE_PROVINCE)

if isinstance(province_raw, dict) and "resultset" in province_raw:
    province = province_raw["resultset"]
elif isinstance(province_raw, list):
    province = province_raw
else:
    raise ValueError("Formato file province non riconosciuto")

# =========================
# INDICE INFO PROVINCE
# =========================
prov_info = {}

for p in province:
    sigla = norm_str(p.get("SIGLA_AUTOMOBILISTICA")).upper()
    if not sigla:
        continue

    prov_info[sigla] = {
        "sigla_provincia": sigla,
        "codice_regione": norm_cod(p.get("COD_REG"), 2),
        "codice_ripartizione": norm_cod(p.get("COD_RIP"), 1),
        "denominazione_provincia": norm_str(p.get("DEN_UTS")),
        "denominazione_regione": norm_str(p.get("DEN_REG")),
        "area_geografica": norm_str(p.get("DEN_RIP")),
        "tipo_uts": p.get("TIPO_UTS"),
        "tipologia_provincia": norm_str(p.get("DESC_TIPO_UTS")),
        "codice_prov_storico": norm_cod(p.get("COD_PROV_STORICO"), 3),
        "cod_uts": norm_cod(p.get("COD_UTS"), 3),
        "codice_fiscale_provincia": norm_str(p.get("COD_PROV_FISCALE")),
        "codice_nuts3_2024": norm_str(p.get("COD_NUTS3_2024")),
    }

# =========================
# RAGGRUPPAMENTO COMUNI PER PROVINCIA
# =========================
comuni_per_provincia = defaultdict(list)

for c in comuni:
    sigla = norm_str(c.get("sigla_provincia")).upper()
    lat = to_float(c.get("lat"))
    lon = to_float(c.get("lon"))

    if not sigla:
        continue
    if lat is None or lon is None:
        continue

    comuni_per_provincia[sigla].append(c)

# =========================
# COSTRUZIONE OUTPUT
# =========================
output = []

for sigla in sorted(comuni_per_provincia.keys()):
    lista = comuni_per_provincia[sigla]

    # capoluogo
    capoluogo = None
    for c in lista:
        if norm_str(c.get("flag_capoluogo")).upper() == "SI":
            capoluogo = c
            break

    # media coordinate di tutti i comuni della provincia
    lats = [to_float(c.get("lat")) for c in lista if to_float(c.get("lat")) is not None]
    lons = [to_float(c.get("lon")) for c in lista if to_float(c.get("lon")) is not None]

    lat_centroide = round(sum(lats) / len(lats), 6) if lats else None
    lon_centroide = round(sum(lons) / len(lons), 6) if lons else None

    info = prov_info.get(sigla, {})

    # fallback: se manca la denominazione provincia, usa il capoluogo
    denominazione_provincia = info.get("denominazione_provincia", "")
    if not denominazione_provincia and capoluogo:
        denominazione_provincia = norm_str(capoluogo.get("denominazione_ita"))

    record = {
        "sigla_provincia": sigla,
        "denominazione_provincia": denominazione_provincia,
        "codice_regione": info.get("codice_regione", ""),
        "denominazione_regione": info.get("denominazione_regione", ""),
        "area_geografica": info.get("area_geografica", ""),
        "tipologia_provincia": info.get("tipologia_provincia", ""),
        "tipo_uts": info.get("tipo_uts", ""),
        "codice_prov_storico": info.get("codice_prov_storico", ""),
        "cod_uts": info.get("cod_uts", ""),
        "codice_fiscale_provincia": info.get("codice_fiscale_provincia", ""),
        "codice_nuts3_2024": info.get("codice_nuts3_2024", ""),
        "numero_comuni_dal_file_comuni": len(lista),

        "capoluogo": norm_str(capoluogo.get("denominazione_ita")) if capoluogo else "",
        "lat_capoluogo": to_float(capoluogo.get("lat")) if capoluogo else None,
        "lon_capoluogo": to_float(capoluogo.get("lon")) if capoluogo else None,

        "lat_centroide": lat_centroide,
        "lon_centroide": lon_centroide,
    }

    output.append(record)

# =========================
# SALVATAGGIO JSON
# =========================
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# =========================
# SALVATAGGIO CSV
# =========================
if output:
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

print(f"Creato: {OUTPUT_JSON}")
print(f"Creato: {OUTPUT_CSV}")
print(f"Province elaborate: {len(output)}")