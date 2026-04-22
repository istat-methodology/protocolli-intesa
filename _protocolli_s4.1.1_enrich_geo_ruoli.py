import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


INPUT_JSON = Path(r"output\data\step_3.0\3.0_risultati_enriched_merged.json")
OUTPUT_JSON = Path(r"output\data\step_4.1\4.1_risultati_enriched_geo_ruoli.json")

COMUNI_JSON = Path(r"geo-json\gi_comuni.json")
PROVINCE_JSON = Path(r"geo-json\gi_province.json")
REGIONI_JSON = Path(r"geo-json\gi_regioni.json")


# =========================================================
# NORMALIZZAZIONE TESTI
# =========================================================

PLACEHOLDERS = {
    "", "nan", "none", "null", "nd", "n.d.", "n/d",
    "non disponibile", "non indicato"
}


def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s0 = s.strip().casefold()
    s1 = "".join(
        c for c in unicodedata.normalize("NFKD", s0)
        if not unicodedata.combining(c)
    )
    s1 = s1.replace("\u2019", "'").replace("`", "'").replace("\u00b4", "'")
    s1 = re.sub(r"\s+", " ", s1).strip()
    if s1 in PLACEHOLDERS:
        return ""
    return s1


def clean_text(s):
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    if s.casefold() in PLACEHOLDERS:
        return ""
    return s


def title_if_not_empty(s):
    s = clean_text(s)
    return s.title() if s else ""


# =========================================================
# LETTURA BASI GEO
# =========================================================

def load_json(path: str | Path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_comuni_index(comuni_file: str | Path):
    comuni = load_json(comuni_file)

    by_name = defaultdict(list)
    by_istat = {}

    for rec in comuni:
        nome = normalize_name(
            rec.get("denominazione_ita")
            or rec.get("denominazione_ita_altra")
            or ""
        )
        if nome:
            by_name[nome].append(rec)

        codice_istat = clean_text(rec.get("codice_istat"))
        if codice_istat:
            by_istat[codice_istat] = rec

    return {
        "by_name": by_name,
        "by_istat": by_istat,
    }


def load_province_index(province_file: str | Path):
    province = load_json(province_file)

    by_sigla = {}
    by_name = defaultdict(list)
    by_codice = {}

    for rec in province:
        sigla = normalize_name(rec.get("sigla_provincia") or "")
        nome = normalize_name(rec.get("denominazione_provincia") or "")
        codice = clean_text(rec.get("codice_prov_storico") or rec.get("cod_uts") or "")

        if sigla:
            by_sigla[sigla] = rec
        if nome:
            by_name[nome].append(rec)
        if codice:
            by_codice[codice] = rec

    return {
        "by_sigla": by_sigla,
        "by_name": by_name,
        "by_codice": by_codice,
    }


def load_regioni_index(regioni_file: str | Path):
    regioni = load_json(regioni_file)

    by_code = {}
    by_name = defaultdict(list)

    for rec in regioni:
        codice = clean_text(rec.get("codice_regione") or "")
        nome = normalize_name(rec.get("denominazione_regione") or "")

        if codice:
            by_code[codice] = rec
        if nome:
            by_name[nome].append(rec)

    return {
        "by_code": by_code,
        "by_name": by_name,
    }


# =========================================================
# MATCH GEO
# =========================================================

def best_match_comune(records: list[dict], provincia_hint: str) -> dict | None:
    if not records:
        return None

    if provincia_hint:
        prov_norm = normalize_name(provincia_hint)
        prov_norm_nospace = prov_norm.replace(" ", "")

        for record in records:
            sigla = normalize_name(record.get("sigla_provincia") or "")
            if sigla == prov_norm or sigla == prov_norm_nospace:
                return record

    return records[0]


def best_match_named(records: list[dict]) -> dict | None:
    if not records:
        return None
    return records[0]


def try_float(v):
    try:
        return float(v)
    except Exception:
        return None


def has_valid_coords(ent: dict) -> bool:
    lat = try_float(ent.get("lat"))
    lon = try_float(ent.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def is_true_like(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == 1
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "si", "sì", "x"}
    return False

# =========================================================
# GOVERNANCE ROLES
# =========================================================


def note_text(ent: dict) -> str:
    note = ent.get("note", "")
    if isinstance(note, list):
        txt = " | ".join(str(x) for x in note if x is not None)
    else:
        txt = str(note or "")
    return txt.strip()


import re

def note_has(ent: dict, patterns: list[str]) -> bool:
    txt = note_text(ent).lower()
    if not txt:
        return False
    return any(re.search(p, txt, flags=re.I) for p in patterns)

# =========================================================
# RUOLI
# =========================================================

def role_in_text(ent: dict, label: str) -> bool:
    ruolo_raw = ent.get("ruolo", [])

    if isinstance(ruolo_raw, list):
        txt = " | ".join(str(x) for x in ruolo_raw if x is not None)
    else:
        txt = str(ruolo_raw or "")

    txt = txt.lower()
    txt = txt.replace("_", " ").replace("-", " ").replace("/", " ")
    txt = re.sub(r"\s+", " ", txt).strip()

    label = label.lower().strip()
    return re.search(rf"\b{re.escape(label)}\b", txt, flags=re.I) is not None

def extract_role_flags(ent: dict) -> dict:
    # da ruolo
    is_firmatario = (
        role_in_text(ent, "firmatario")
        or is_true_like(ent.get("ruolo_firmatario"))
    )

    is_proponente = (
        role_in_text(ent, "proponente")
        or role_in_text(ent, "soggetto_proponente")
        or is_true_like(ent.get("ruolo_proponente"))
    )

    is_attore = (
        role_in_text(ent, "attore")
        or is_true_like(ent.get("ruolo_attore"))
    )

    # da note
    is_gestione = (
        note_has(ent, [
            r"\bgestisc\w*",
            r"\bgestion\w*",
            r"\bente gestore\b",
            r"\bsoggett[oi] gestor\w*",
        ])
        or is_true_like(ent.get("ruolo_gestione"))
        or is_true_like(ent.get("gestione"))
    )

    is_monitoraggio = (
        note_has(ent, [
            r"\bmonitor\w*",
            r"\bmonitora\w*",
            r"\bmonitoraggio\b",
        ])
        or is_true_like(ent.get("ruolo_monitoraggio"))
        or is_true_like(ent.get("monitoraggio"))
    )

    is_coordinamento = (
        note_has(ent, [
            r"\bcoordina\w*",
            r"\bcoordinament\w*",
            r"\bcoordinatore\b",
            r"\bcoordinatric\w*",
        ])
        or is_true_like(ent.get("ruolo_coordinamento"))
        or is_true_like(ent.get("coordinamento"))
    )

    is_governance = is_coordinamento or is_gestione or is_monitoraggio

    return {
        "is_firmatario": is_firmatario,
        "is_proponente": is_proponente,
        "is_attore": is_attore,
        "is_gestione": is_gestione,
        "is_monitoraggio": is_monitoraggio,
        "is_coordinamento": is_coordinamento,
        "is_governance": is_governance,
    }


def build_ruolo_list(flags: dict) -> list[str]:
    out = []
    if flags["is_firmatario"]:
        out.append("firmatario")
    if flags["is_proponente"]:
        out.append("proponente")
    if flags["is_attore"]:
        out.append("attore")
    if flags["is_gestione"]:
        out.append("gestione")
    if flags["is_monitoraggio"]:
        out.append("monitoraggio")
    if flags["is_coordinamento"]:
        out.append("coordinamento")
    return out


def build_governance_detail(flags: dict) -> str:
    out = []
    if flags["is_gestione"]:
        out.append("gestione")
    if flags["is_monitoraggio"]:
        out.append("monitoraggio")
    if flags["is_coordinamento"]:
        out.append("coordinamento")
    return ", ".join(out)


# =========================================================
# CLASSIFICAZIONE LIVELLO TERRITORIALE
# =========================================================

PROVINCIA_KEYWORDS = [
    "provincia",
    "citta metropolitana",
    "città metropolitana",
    "libero consorzio",
]

REGIONE_KEYWORDS = [
    "regione",
    "provincia autonoma",
]

COMUNE_KEYWORDS = [
    "comune",
    "municipio",
]


def detect_level_from_entity(ent: dict) -> str:
    nome = normalize_name(ent.get("nome") or "")
    tipo = normalize_name(ent.get("tipo") or "")
    comune = normalize_name(ent.get("comune") or ent.get("comune_matchato") or "")
    provincia = normalize_name(ent.get("provincia") or ent.get("sigla_provincia") or "")
    regione = normalize_name(ent.get("regione") or "")

    blob = " | ".join([nome, tipo])

    if any(k in blob for k in REGIONE_KEYWORDS):
        return "regione"
    if any(k in blob for k in PROVINCIA_KEYWORDS):
        return "provincia"
    if any(k in blob for k in COMUNE_KEYWORDS):
        return "comune"

    if comune:
        return "comune"
    if provincia:
        return "provincia"
    if regione:
        return "regione"

    return "comune"


# =========================================================
# ITERAZIONE JSON
# =========================================================

def iter_items(obj):
    if isinstance(obj, dict):
        if "soggetti" in obj or "entities" in obj:
            yield obj
        for v in obj.values():
            yield from iter_items(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_items(item)


def iter_entities(item: dict) -> list[dict]:
    if not isinstance(item, dict):
        return []

    if isinstance(item.get("soggetti"), list):
        return [x for x in item["soggetti"] if isinstance(x, dict)]

    if isinstance(item.get("entities"), list):
        return [x for x in item["entities"] if isinstance(x, dict)]

    return []


# =========================================================
# ENRICH SINGOLA ENTITÀ
# =========================================================

def enrich_entity_geo_and_roles(
    ent: dict,
    comuni_index: dict,
    province_index: dict,
    regioni_index: dict,
) -> tuple[dict, str]:
    """
    Restituisce:
    - ent arricchita
    - esito livello: comune / provincia / regione / no_match
    """
    if not isinstance(ent, dict):
        return ent, "no_match"

    # --- ruoli ---
    flags = extract_role_flags(ent)
    ruolo_list = build_ruolo_list(flags)
    governance_detail = build_governance_detail(flags)

    ent["ruolo"] = ruolo_list
    ent["governance_detail"] = governance_detail

    for k, v in flags.items():
        ent[k] = v

    # --- livello ---
    livello = clean_text(ent.get("livello_territoriale"))
    if not livello:
        livello = detect_level_from_entity(ent)
    ent["livello_territoriale"] = livello

    # già georeferenziata?
    already_has_coords = has_valid_coords(ent)

    # indizi
    comune_raw = clean_text(ent.get("comune") or ent.get("comune_matchato") or "")
    provincia_raw = clean_text(ent.get("provincia") or ent.get("sigla_provincia") or "")
    regione_raw = clean_text(ent.get("regione") or "")
    nome_raw = clean_text(ent.get("nome") or "")

    comune_norm = normalize_name(comune_raw)
    provincia_norm = normalize_name(provincia_raw)
    regione_norm = normalize_name(regione_raw)
    nome_norm = normalize_name(nome_raw)

    # =====================================================
    # COMUNE
    # =====================================================
    if livello == "comune":
        match = best_match_comune(
            comuni_index["by_name"].get(comune_norm, []),
            provincia_raw
        )

        if not match and nome_norm:
            match = best_match_comune(
                comuni_index["by_name"].get(nome_norm, []),
                provincia_raw
            )

        if match:
            if not clean_text(ent.get("comune")):
                ent["comune"] = match.get("denominazione_ita") or match.get("denominazione_ita_altra") or comune_raw
            if not clean_text(ent.get("comune_matchato")):
                ent["comune_matchato"] = match.get("denominazione_ita") or match.get("denominazione_ita_altra") or comune_raw
            if not clean_text(ent.get("sigla_provincia")):
                ent["sigla_provincia"] = clean_text(match.get("sigla_provincia"))
            if not clean_text(ent.get("codice_comune")):
                ent["codice_comune"] = clean_text(match.get("codice_istat"))

            # regione da provincia se disponibile in seguito; qui almeno coords
            if not already_has_coords:
                lat = try_float(match.get("lat"))
                lon = try_float(match.get("lon"))
                if lat is not None and lon is not None:
                    ent["lat"] = lat
                    ent["lon"] = lon

            return ent, "comune"

    # =====================================================
    # PROVINCIA
    # =====================================================
    if livello == "provincia":
        match = None

        if provincia_norm:
            match = province_index["by_sigla"].get(provincia_norm)

        if not match and nome_norm:
            match = best_match_named(province_index["by_name"].get(nome_norm, []))

        if not match and provincia_norm:
            match = best_match_named(province_index["by_name"].get(provincia_norm, []))

        if match:
            ent["sigla_provincia"] = clean_text(match.get("sigla_provincia")) or clean_text(ent.get("sigla_provincia"))
            if not clean_text(ent.get("provincia")):
                ent["provincia"] = clean_text(match.get("denominazione_provincia"))
            if not clean_text(ent.get("codice_provincia")):
                ent["codice_provincia"] = clean_text(match.get("codice_prov_storico") or match.get("cod_uts"))
            if not clean_text(ent.get("codice_regione")):
                ent["codice_regione"] = clean_text(match.get("codice_regione"))
            if not clean_text(ent.get("regione")):
                ent["regione"] = clean_text(match.get("denominazione_regione"))

            if not already_has_coords:
                lat = try_float(match.get("lat_centroide") or match.get("lat_capoluogo"))
                lon = try_float(match.get("lon_centroide") or match.get("lon_capoluogo"))
                if lat is not None and lon is not None:
                    ent["lat"] = lat
                    ent["lon"] = lon

            return ent, "provincia"

    # =====================================================
    # REGIONE
    # =====================================================
    if livello == "regione":
        match = None

        if regione_norm:
            match = best_match_named(regioni_index["by_name"].get(regione_norm, []))

        if not match and nome_norm:
            match = best_match_named(regioni_index["by_name"].get(nome_norm, []))

        if match:
            if not clean_text(ent.get("regione")):
                ent["regione"] = clean_text(match.get("denominazione_regione"))
            if not clean_text(ent.get("codice_regione")):
                ent["codice_regione"] = clean_text(match.get("codice_regione"))

            if not already_has_coords:
                lat = try_float(match.get("lat_centroide"))
                lon = try_float(match.get("lon_centroide"))
                if lat is not None and lon is not None:
                    ent["lat"] = lat
                    ent["lon"] = lon

            return ent, "regione"

    # =====================================================
    # FALLBACK: se il livello è sbagliato, prova in cascata
    # =====================================================
    # 1) comune
    match_comune = best_match_comune(
        comuni_index["by_name"].get(comune_norm or nome_norm, []),
        provincia_raw
    )
    if match_comune:
        if not clean_text(ent.get("comune")):
            ent["comune"] = match_comune.get("denominazione_ita") or match_comune.get("denominazione_ita_altra") or ""
        if not clean_text(ent.get("comune_matchato")):
            ent["comune_matchato"] = match_comune.get("denominazione_ita") or match_comune.get("denominazione_ita_altra") or ""
        if not clean_text(ent.get("sigla_provincia")):
            ent["sigla_provincia"] = clean_text(match_comune.get("sigla_provincia"))
        if not clean_text(ent.get("codice_comune")):
            ent["codice_comune"] = clean_text(match_comune.get("codice_istat"))
        ent["livello_territoriale"] = "comune"

        if not already_has_coords:
            lat = try_float(match_comune.get("lat"))
            lon = try_float(match_comune.get("lon"))
            if lat is not None and lon is not None:
                ent["lat"] = lat
                ent["lon"] = lon

        return ent, "comune"

    # 2) provincia
    match_prov = None
    if provincia_norm:
        match_prov = province_index["by_sigla"].get(provincia_norm)
    if not match_prov and nome_norm:
        match_prov = best_match_named(province_index["by_name"].get(nome_norm, []))

    if match_prov:
        ent["livello_territoriale"] = "provincia"
        ent["sigla_provincia"] = clean_text(match_prov.get("sigla_provincia")) or clean_text(ent.get("sigla_provincia"))
        if not clean_text(ent.get("provincia")):
            ent["provincia"] = clean_text(match_prov.get("denominazione_provincia"))
        if not clean_text(ent.get("codice_provincia")):
            ent["codice_provincia"] = clean_text(match_prov.get("codice_prov_storico") or match_prov.get("cod_uts"))
        if not clean_text(ent.get("codice_regione")):
            ent["codice_regione"] = clean_text(match_prov.get("codice_regione"))
        if not clean_text(ent.get("regione")):
            ent["regione"] = clean_text(match_prov.get("denominazione_regione"))

        if not already_has_coords:
            lat = try_float(match_prov.get("lat_centroide") or match_prov.get("lat_capoluogo"))
            lon = try_float(match_prov.get("lon_centroide") or match_prov.get("lon_capoluogo"))
            if lat is not None and lon is not None:
                ent["lat"] = lat
                ent["lon"] = lon

        return ent, "provincia"

    # 3) regione
    match_reg = None
    if regione_norm:
        match_reg = best_match_named(regioni_index["by_name"].get(regione_norm, []))
    if not match_reg and nome_norm:
        match_reg = best_match_named(regioni_index["by_name"].get(nome_norm, []))

    if match_reg:
        ent["livello_territoriale"] = "regione"
        if not clean_text(ent.get("regione")):
            ent["regione"] = clean_text(match_reg.get("denominazione_regione"))
        if not clean_text(ent.get("codice_regione")):
            ent["codice_regione"] = clean_text(match_reg.get("codice_regione"))

        if not already_has_coords:
            lat = try_float(match_reg.get("lat_centroide"))
            lon = try_float(match_reg.get("lon_centroide"))
            if lat is not None and lon is not None:
                ent["lat"] = lat
                ent["lon"] = lon

        return ent, "regione"

    return ent, "no_match"


# =========================================================
# ENRICH GLOBALE
# =========================================================

def enrich_with_geo_ruoli(
    input_file: str | Path = INPUT_JSON,
    output_file: str | Path = OUTPUT_JSON,
    comuni_file: str | Path = COMUNI_JSON,
    province_file: str | Path = PROVINCE_JSON,
    regioni_file: str | Path = REGIONI_JSON,
) -> str:
    input_path = Path(input_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as f:
        risultati = json.load(f)

    comuni_index = load_comuni_index(comuni_file)
    province_index = load_province_index(province_file)
    regioni_index = load_regioni_index(regioni_file)

    tot_entities = 0
    count_comune = 0
    count_provincia = 0
    count_regione = 0
    count_no_match = 0
    coords_before = 0
    coords_after = 0


    ruolo_counts = {
        "firmatario": 0,
        "proponente": 0,
        "attore": 0,
        "gestione": 0,
        "monitoraggio": 0,
        "coordinamento": 0,
        "governance": 0,
    }





    for item in iter_items(risultati):
        for ent in iter_entities(item):
            tot_entities += 1

            if has_valid_coords(ent):
                coords_before += 1

            ent, esito = enrich_entity_geo_and_roles(
                ent,
                comuni_index=comuni_index,
                province_index=province_index,
                regioni_index=regioni_index,
            )

            if has_valid_coords(ent):
                coords_after += 1

            if ent.get("is_firmatario"):
                ruolo_counts["firmatario"] += 1
            if ent.get("is_proponente"):
                ruolo_counts["proponente"] += 1
            if ent.get("is_attore"):
                ruolo_counts["attore"] += 1
            if ent.get("is_gestione"):
                ruolo_counts["gestione"] += 1
            if ent.get("is_monitoraggio"):
                ruolo_counts["monitoraggio"] += 1
            if ent.get("is_coordinamento"):
                ruolo_counts["coordinamento"] += 1
            if ent.get("is_governance"):
                ruolo_counts["governance"] += 1

            if esito == "comune":
                count_comune += 1
            elif esito == "provincia":
                count_provincia += 1
            elif esito == "regione":
                count_regione += 1
            else:
                count_no_match += 1


    # =========================
    # DEBUG OPZIONALE
    # =========================
    DEBUG = False
    DEBUG_SAMPLE = 10

    if DEBUG:
        sample_n = 0
        for item in iter_items(risultati):
            for ent in iter_entities(item):
                print("NOME:", ent.get("nome"))
                print("RUOLO:", ent.get("ruolo"))
                print("ruolo_firmatario:", ent.get("ruolo_firmatario"))
                print("ruolo_proponente:", ent.get("ruolo_proponente"))
                print("ruolo_attore:", ent.get("ruolo_attore"))
                print("ruolo_gestione:", ent.get("ruolo_gestione"))
                print("ruolo_monitoraggio:", ent.get("ruolo_monitoraggio"))
                print("ruolo_coordinamento:", ent.get("ruolo_coordinamento"))
                print("gestione:", ent.get("gestione"))
                print("monitoraggio:", ent.get("monitoraggio"))
                print("coordinamento:", ent.get("coordinamento"))
                print("note:", ent.get("note"))
                print("-" * 80)

                sample_n += 1
                if sample_n >= DEBUG_SAMPLE:
                    break
            if sample_n >= DEBUG_SAMPLE:
                break

        debug_hits = {
            "proponente": 0,
            "gestione": 0,
            "monitoraggio": 0,
            "coordinamento": 0,
            "governance": 0,
        }

        for item in iter_items(risultati):
            for ent in iter_entities(item):
                flags = extract_role_flags(ent)

                if flags["is_proponente"]:
                    debug_hits["proponente"] += 1
                if flags["is_gestione"]:
                    debug_hits["gestione"] += 1
                if flags["is_monitoraggio"]:
                    debug_hits["monitoraggio"] += 1
                if flags["is_coordinamento"]:
                    debug_hits["coordinamento"] += 1
                if flags["is_governance"]:
                    debug_hits["governance"] += 1

        print("DEBUG HITS:", debug_hits)



    with output_path.open("w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)

    print(f"✅ Salvato: {output_path}")
    print(f"Entità totali: {tot_entities}")
    print(f"Coordinate già presenti prima: {coords_before}")
    print(f"Coordinate valide dopo: {coords_after}")
    print(f"Match comune: {count_comune}")
    print(f"Match provincia: {count_provincia}")
    print(f"Match regione: {count_regione}")
    print(f"Nessun match: {count_no_match}")
    print("--- Ruoli ---")
    print(f"Firmatari: {ruolo_counts['firmatario']}")
    print(f"Proponenti: {ruolo_counts['proponente']}")
    print(f"Attori: {ruolo_counts['attore']}")
    print(f"Gestione: {ruolo_counts['gestione']}")
    print(f"Monitoraggio: {ruolo_counts['monitoraggio']}")
    print(f"Coordinamento: {ruolo_counts['coordinamento']}")
    print(f"Governance totale: {ruolo_counts['governance']}")

    return str(output_path)


if __name__ == "__main__":
    enrich_with_geo_ruoli(
        input_file=INPUT_JSON,
        output_file=OUTPUT_JSON,
        comuni_file=COMUNI_JSON,
        province_file=PROVINCE_JSON,
        regioni_file=REGIONI_JSON,
    )