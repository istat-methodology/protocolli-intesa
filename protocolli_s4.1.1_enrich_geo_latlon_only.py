import json
import unicodedata
from collections import defaultdict
from pathlib import Path

INPUT_JSON = Path(r"output\data\step_3.0\3.0_risultati_enriched_merged.json")
OUTPUT_JSON = Path(r"output\data\step_3.0\3.0_risultati_enriched_geo.json")
COMUNI_JSON = Path(r"geo-json\gi_comuni.json")

def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s0 = s.strip().casefold()
    s1 = "".join(
        c for c in unicodedata.normalize("NFKD", s0)
        if not unicodedata.combining(c)
    )
    s1 = s1.replace("\u2019", "'").replace("`", "'").replace("\u00b4", "'")
    s1 = " ".join(s1.split())
    return s1


def load_comuni_index(comuni_file: str) -> dict[str, list[dict]]:
    comuni_path = Path(comuni_file)
    if not comuni_path.exists():
        raise FileNotFoundError(f"File comuni non trovato: {comuni_path}")

    with comuni_path.open("r", encoding="utf-8") as f:
        comuni = json.load(f)

    by_name: dict[str, list[dict]] = defaultdict(list)
    for rec in comuni:
        nome = normalize_name(
            rec.get("denominazione_ita") or rec.get("denominazione_ita_altra") or ""
        )
        if nome:
            by_name[nome].append(rec)
    return by_name


def best_match(records: list[dict], provincia_entity: str) -> dict | None:
    if not records:
        return None

    if provincia_entity:
        prov_norm = normalize_name(provincia_entity)
        prov_norm_nospace = prov_norm.replace(" ", "")
        for record in records:
            sigla = normalize_name(record.get("sigla_provincia") or "")
            if sigla == prov_norm or sigla == prov_norm_nospace:
                return record

    return records[0]


def has_valid_coords(ent: dict) -> bool:
    lat = ent.get("lat")
    lon = ent.get("lon")
    return isinstance(lat, (int, float)) and isinstance(lon, (int, float))


def enrich_entity_lat_lon_only(ent: dict, by_name: dict[str, list[dict]]) -> dict:
    """
    Aggiorna solo lat/lon se mancanti.
    Non modifica codice_regione, codice_provincia, codice_comune
    né altri campi già presenti nel JSON.
    """
    if has_valid_coords(ent):
        return ent

    comune_norm = normalize_name(ent.get("comune") or ent.get("comune_matchato") or "")
    if not comune_norm:
        return ent

    provincia_hint = ent.get("sigla_provincia") or ent.get("provincia") or ""
    match = best_match(by_name.get(comune_norm, []), provincia_hint)
    if not match:
        return ent

    try:
        ent["lat"] = float(match["lat"])
        ent["lon"] = float(match["lon"])
    except Exception:
        pass

    return ent

def iter_items(risultati):
    """
    Restituisce i record reali del JSON, qualunque sia la struttura top-level:
    - lista di dict
    - dict singolo
    - dict di dict
    - dict con liste annidate
    """
    if isinstance(risultati, list):
        for x in risultati:
            if isinstance(x, dict):
                yield x

    elif isinstance(risultati, dict):
        # Caso 1: il dict stesso è già un record
        if "soggetti" in risultati or "entities" in risultati:
            yield risultati
            return

        # Caso 2: dict contenitore
        for v in risultati.values():
            if isinstance(v, dict):
                if "soggetti" in v or "entities" in v:
                    yield v
                else:
                    for vv in v.values():
                        if isinstance(vv, dict) and ("soggetti" in vv or "entities" in vv):
                            yield vv
                        elif isinstance(vv, list):
                            for z in vv:
                                if isinstance(z, dict):
                                    yield z

            elif isinstance(v, list):
                for z in v:
                    if isinstance(z, dict):
                        yield z


def iter_entities(item):
    if not isinstance(item, dict):
        return []

    if isinstance(item.get("soggetti"), list):
        return [x for x in item["soggetti"] if isinstance(x, dict)]

    if isinstance(item.get("entities"), list):
        return [x for x in item["entities"] if isinstance(x, dict)]

    return []

def _iter_entities(item: dict) -> list[dict]:
    if isinstance(item.get("soggetti"), list):
        return item["soggetti"]
    if isinstance(item.get("entities"), list):
        return item["entities"]
    return []


def enrich_with_geo_lat_lon_only(
    input_file: str = INPUT_JSON,
    output_file: str = OUTPUT_JSON,
    comuni_file: str = COMUNI_JSON
) -> str:
    """
    Legge all_risultati_enriched_2.4.json e aggiorna solo lat/lon quando mancanti.
    Salva un file pronto per il notebook mappe.
    """
    input_path = Path(input_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as f:
        risultati = json.load(f)

    by_name = load_comuni_index(comuni_file)

    tot_entities = 0
    gia_presenti = 0
    aggiornate = 0
    non_trovate = 0

    for item in iter_items(risultati):
        for ent in iter_entities(item):
            tot_entities += 1

            if has_valid_coords(ent):
                gia_presenti += 1
                continue

            enrich_entity_lat_lon_only(ent, by_name)

            if has_valid_coords(ent):
                aggiornate += 1
            else:
                non_trovate += 1

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(risultati, f, ensure_ascii=False, indent=2)

    print(f"✅ Salvato: {output_path}")
    print(f"Entità totali: {tot_entities}")
    print(f"Coordinate già presenti: {gia_presenti}")
    print(f"Coordinclsate aggiunte: {aggiornate}")
    print(f"Coordinate non trovate: {non_trovate}")
    return str(output_path)


if __name__ == "__main__":
    enrich_with_geo_lat_lon_only()
