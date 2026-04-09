# Arricchimento comuni / province / regioni

import os
import json
import copy
import re
import unicodedata
from pathlib import Path

import pandas as pd

from region_config import get_reg_code, print_reg_code, build_region_file

reg_code = get_reg_code(default="09", required=True)
print_reg_code(reg_code)


JSON_STEP2_FOLDER = r"output/json/step_2" # Directory per i JSON arricchiti con RUNTS e CAV (2.1.1) e con ALIAS_MAP (2.1.2)

INPUT_JSON = build_region_file(JSON_STEP2_FOLDER, reg_code, "risultati_enriched_2.2.json")
OUTPUT_JSON = build_region_file(JSON_STEP2_FOLDER, reg_code, "risultati_enriched_2.3.json")

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------

CLASSIFICATION_FOLDER = r"classification/"
COMUNI_CSV = os.path.join(CLASSIFICATION_FOLDER, "cls_elenco_comuni_2026.csv")
PROVINCE_CSV = os.path.join(CLASSIFICATION_FOLDER, "cls_elenco_province_2026.csv")
REGIONI_CSV = os.path.join(CLASSIFICATION_FOLDER, "cls_elenco_regioni_2026.csv")
RUNTS_FILE = os.path.join(CLASSIFICATION_FOLDER, "cls_runts.csv")
JSON_STEP1_FOLDER = r"output/json/step_1/"

FUZZY_THRESHOLD = 95

try:
    from rapidfuzz import process, fuzz
    RAPIDFUZZ_OK = True
except Exception:
    RAPIDFUZZ_OK = False

# Mappatura colonne ISTAT
COL_COMUNE = "Comune"
COL_COD_COMUNE = "Codice Comune (alfanumerico)"
COL_COD_PROV = "Codice Provincia/Uts"
COL_PROV = "Provincia/Uts"
COL_SIGLA_PROV = "Sigla automobilistica"
COL_COD_REG = "Codice Regione"
COL_REG = "Regione"

# Indici globali (popolati da build_comuni_index)
idx_exact = {}
idx_compact = {}
fuzzy_names = []
fuzzy_rows = []

# DataFrames globali province/regioni (popolati da load_province_regioni)
df_province = None
df_regioni = None

# ------------------------------------------------------
# TEXT NORMALIZATION
# ------------------------------------------------------

def _strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", str(s))
        if not unicodedata.combining(ch)
    )


def _norm_text(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().upper()
    s = _strip_accents(s)
    repl = {
        "\u2019": "'",
        "\u2018": "'",
        "`": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _compact(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", _norm_text(s))


def _norm_geo(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().upper()
    s = _strip_accents(s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _first_nonempty(*values):
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _extract_comune_from_nome(nome: str) -> str:
    """Estrazione conservativa dal nome dell'ente."""
    if not nome:
        return ""
    nome_clean = str(nome).strip()

    patterns = [
        r"^COMUNE DI\s+(.+)$",
        r"^PREFETTURA DI\s+(.+)$",
        r"^QUESTURA DI\s+(.+)$",
        r"^TRIBUNALE DI\s+(.+)$",
        r"^PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE DI\s+(.+)$",
        r"^ORDINE DEGLI AVVOCATI DI\s+(.+)$",
        r"^ORDINE DEI FARMACISTI DI\s+(.+)$",
        r"^ORDINE DEI MEDICI.* DI\s+(.+)$",
        r"^AZIENDA USL DI\s+(.+)$",
        r"^AZIENDA OSPEDALIERA UNIVERSITARIA DI\s+(.+)$",
        r"^UNIVERSITA DEGLI STUDI DI\s+(.+)$",
        r"^UNIVERSITA DEGLI STUDI DI\s+(.+)$",
        r"^COMANDO PROVINCIALE DEI CARABINIERI DI\s+(.+)$",
        r"^COMANDO PROVINCIALE DELLA GUARDIA DI FINANZA DI\s+(.+)$",
    ]
    norm = _norm_text(nome_clean)
    for pat in patterns:
        m = re.match(pat, norm)
        if m:
            return m.group(1).strip().title()

    if " DI " in norm:
        tail = norm.split(" DI ")[-1].strip()
        if 2 <= len(tail) <= 40 and " E " not in tail:
            return tail.title()

    return ""


# ------------------------------------------------------
# LOADING
# ------------------------------------------------------

def load_province_regioni(province_csv, regioni_csv):
    global df_province, df_regioni

    df_p = pd.read_csv(province_csv, dtype=str, sep=";").fillna("")
    df_r = pd.read_csv(regioni_csv, dtype=str, sep=";").fillna("")

    df_p = df_p.rename(columns={
        "Provincia/Uts": "provincia",
        "Regione": "regione",
        "Codice Provincia/Uts": "codice_provincia",
        "Sigla automobilistica": "sigla_provincia",
        "Codice Regione": "codice_regione",
    })

    df_r = df_r.rename(columns={
        "Regione": "regione",
        "Codice Regione": "codice_regione"
    })

    required_prov = ["provincia", "regione", "codice_provincia", "sigla_provincia", "codice_regione"]
    missing_prov = [c for c in required_prov if c not in df_p.columns]
    if missing_prov:
        raise ValueError(f"Colonne mancanti nel CSV province: {missing_prov}")

    required_reg = ["regione", "codice_regione"]
    missing_reg = [c for c in required_reg if c not in df_r.columns]
    if missing_reg:
        raise ValueError(f"Colonne mancanti nel CSV regioni: {missing_reg}")

    def norm_text(s):
        if not s:
            return ""
        s = str(s).strip().upper()
        s = "".join(
            ch for ch in unicodedata.normalize("NFKD", s)
            if not unicodedata.combining(ch)
        )
        s = s.replace("'", "'").replace("'", "'").replace("`", "'")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    df_p["provincia_norm"] = df_p["provincia"].apply(norm_text)
    df_p["regione_norm"] = df_p["regione"].apply(norm_text)
    df_r["regione_norm"] = df_r["regione"].apply(norm_text)

    df_province = df_p
    df_regioni = df_r

    print("✅ Province caricate:", df_p.shape)
    print("✅ Regioni caricate:", df_r.shape)

    return df_p, df_r


def load_comuni_csv(csv_path: str) -> pd.DataFrame:
    """Carica il CSV ISTAT dei comuni con fallback di encoding/separatore."""
    attempts = [
        {"encoding": "utf-8-sig", "sep": ";"},
        {"encoding": "utf-8", "sep": ";"},
        {"encoding": "latin1", "sep": ";"},
        {"encoding": "cp1252", "sep": ";"},
        {"encoding": "latin1", "sep": ","},
        {"encoding": "cp1252", "sep": ","},
    ]
    last_error = None
    for kw in attempts:
        try:
            df = pd.read_csv(csv_path, dtype=str, **kw).fillna("")
            if len(df.columns) >= 5:
                print(f"CSV caricato con encoding={kw['encoding']} sep={kw['sep']!r}")
                return df
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Impossibile leggere {csv_path}: {last_error}")


def build_comuni_index(df_comuni: pd.DataFrame):
    global idx_exact, idx_compact, fuzzy_names, fuzzy_rows

    required_cols = [COL_COMUNE, COL_COD_COMUNE, COL_COD_PROV, COL_PROV, COL_SIGLA_PROV, COL_COD_REG, COL_REG]
    missing = [c for c in required_cols if c not in df_comuni.columns]
    if missing:
        raise ValueError(f"Colonne mancanti nel CSV comuni: {missing}")

    idx_exact = {}
    idx_compact = {}
    fuzzy_names = []
    fuzzy_rows = []

    for _, row in df_comuni.iterrows():
        comune_raw = row[COL_COMUNE]
        comune_norm = _norm_text(comune_raw)
        comune_comp = _compact(comune_raw)
        record = row.to_dict()

        if comune_norm and comune_norm not in idx_exact:
            idx_exact[comune_norm] = record
        if comune_comp and comune_comp not in idx_compact:
            idx_compact[comune_comp] = record

        if comune_norm:
            fuzzy_names.append(comune_norm)
            fuzzy_rows.append(record)

    print("Indice exact:", len(idx_exact))
    print("Indice compact:", len(idx_compact))
    print("Fuzzy names:", len(fuzzy_names))


# ------------------------------------------------------
# LOOKUP
# ------------------------------------------------------

def lookup_comune_smart(raw_value: str, fuzzy_threshold: int = 95):
    if not raw_value:
        return None, "none", 0, ""

    q_exact = _norm_text(raw_value)
    q_comp = _compact(raw_value)

    if q_exact in idx_exact:
        return idx_exact[q_exact], "exact", 100, q_exact

    if q_comp in idx_compact:
        return idx_compact[q_comp], "compact", 100, q_exact

    if RAPIDFUZZ_OK and fuzzy_names:
        match = process.extractOne(q_exact, fuzzy_names, scorer=fuzz.token_sort_ratio)
        if match:
            best_name, score, idx = match
            score = int(score)
            if score >= fuzzy_threshold:
                return fuzzy_rows[idx], "fuzzy", score, best_name

    return None, "none", 0, ""


# ------------------------------------------------------
# ENRICHMENT
# ------------------------------------------------------

def enrich_codici_per_sovracomunali(ent, df_p, df_r):
    """
    Per enti sovracomunali:
    - NON cerca il comune
    - usa provincia e regione già presenti
    - valorizza codice_provincia, sigla_provincia, codice_regione
    """
    tipo = (ent.get("tipo") or "").strip()
    provincia = (ent.get("provincia") or "").strip()
    regione = (ent.get("regione") or "").strip()

    tipi_sovracomunali = {
        "Unione dei Comuni",
        "Comunità Montana",
        "Comunità Territoriale",
    }

    if tipo not in tipi_sovracomunali:
        return ent, False

    ent.setdefault("comune_fonte", "none")
    ent.setdefault("comune_matchato", "")
    ent.setdefault("codice_comune", "")
    ent.setdefault("codice_provincia", "")
    ent.setdefault("sigla_provincia", "")
    ent.setdefault("codice_regione", "")
    ent.setdefault("match_comune", "none")

    ent["comune_fonte"] = "not_applicable_sovracomunale"
    ent["comune_matchato"] = ""
    ent["codice_comune"] = ""
    ent["match_comune"] = "not_applicable_sovracomunale"

    provincia_norm = _norm_text(provincia)
    regione_norm = _norm_text(regione)

    if provincia_norm:
        mask_prov = df_p["provincia_norm"] == provincia_norm
        if mask_prov.any():
            rowp = df_p.loc[mask_prov].iloc[0]
            ent["codice_provincia"] = str(rowp.get("codice_provincia", "")).strip()
            ent["sigla_provincia"] = str(rowp.get("sigla_provincia", "")).strip()
            if not (ent.get("codice_regione") or "").strip():
                ent["codice_regione"] = str(rowp.get("codice_regione", "")).strip()
            if not regione:
                reg_from_prov = str(rowp.get("regione", "")).strip()
                if reg_from_prov:
                    ent["regione"] = reg_from_prov
                    regione_norm = _norm_text(reg_from_prov)

    if regione_norm and not (ent.get("codice_regione") or "").strip():
        mask_reg = df_r["regione_norm"] == regione_norm
        if mask_reg.any():
            rowr = df_r.loc[mask_reg].iloc[0]
            ent["codice_regione"] = str(rowr.get("codice_regione", "")).strip()

    return ent, True


def enrich_comune_provincia_regione_smart(
    INPUT_JSON: str,
    comuni_csv_path: str,
    OUTPUT_JSON: str,
    fuzzy_threshold: int = 95
):
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    enriched = copy.deepcopy(data)

    stats = {
        "tot_soggetti": 0,
        "con_match": 0,
        "senza_match": 0,
        "exact": 0,
        "compact": 0,
        "fuzzy": 0,
        "fonte_comune": 0,
        "fonte_comune_runts": 0,
        "fonte_nome": 0,
        "fonte_none": 0,
    }

    for file_item in enriched:
        soggetti = file_item.get("soggetti") or []

        for ent in soggetti:
            stats["tot_soggetti"] += 1

            comune = _first_nonempty(ent.get("comune"))
            comune_runts = _first_nonempty(ent.get("comune_runts"))
            comune_nome = _extract_comune_from_nome(ent.get("nome", ""))

            candidate = ""
            fonte = "none"

            if comune:
                candidate = comune
                fonte = "comune"
                stats["fonte_comune"] += 1
            elif comune_runts:
                candidate = comune_runts
                fonte = "comune_runts"
                stats["fonte_comune_runts"] += 1
            elif comune_nome:
                candidate = comune_nome
                fonte = "nome"
                stats["fonte_nome"] += 1
            else:
                stats["fonte_none"] += 1

            fonte_esistente = (ent.get("fonte_provincia_regione") or "").strip()
            is_sovracomunale = fonte_esistente == "elenchi_sovracomunali"

            ent["comune_fonte"] = fonte if not is_sovracomunale else "not_applicable_sovracomunale"
            ent["comune_matchato"] = ""
            ent["codice_comune"] = ""
            if not is_sovracomunale:
                ent["codice_provincia"] = ""
                ent["sigla_provincia"] = ""
                ent["codice_regione"] = ""
            ent["match_comune"] = "none" if not is_sovracomunale else ent.get("match_comune", "not_applicable_sovracomunale")

            if is_sovracomunale:
                continue

            if not candidate:
                stats["senza_match"] += 1
                continue

            row, how, score, best = lookup_comune_smart(candidate, fuzzy_threshold=fuzzy_threshold)

            ent["match_comune"] = how

            if row:
                ent["comune_matchato"] = row.get(COL_COMUNE, "")
                ent["codice_comune"] = row.get(COL_COD_COMUNE, "")
                ent["codice_provincia"] = row.get(COL_COD_PROV, "")
                ent["provincia"] = row.get(COL_PROV, "")
                ent["sigla_provincia"] = row.get(COL_SIGLA_PROV, "")
                ent["codice_regione"] = row.get(COL_COD_REG, "")
                ent["regione"] = row.get(COL_REG, "")

                stats["con_match"] += 1
                if how in ("exact", "compact", "fuzzy"):
                    stats[how] += 1
            else:
                stats["senza_match"] += 1

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print("✅ Arricchimento completato")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("📄 Output:", OUTPUT_JSON)

    return enriched, stats


def enrich_only_codes_from_prov_reg(
    INPUT_JSON,
    cls_comuni_csv_path,
    OUTPUT_JSON
):
    """
    Lascia invariati 'provincia' e 'regione' se già presenti.
    Aggiunge solo: codice_provincia, sigla_provincia, codice_regione
    """
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.read_csv(cls_comuni_csv_path, dtype=str).fillna("")

    col_cod_prov = "Codice Provincia/Uts"
    col_prov = "Provincia/Uts"
    col_sigla = "Sigla automobilistica"
    col_cod_reg = "Codice Regione"
    col_reg = "Regione"

    geo_df = (
        df[[col_cod_prov, col_prov, col_sigla, col_cod_reg, col_reg]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    idx_full = {}
    idx_prov = {}
    idx_reg = {}

    for _, row in geo_df.iterrows():
        prov = _norm_geo(row[col_prov])
        reg = _norm_geo(row[col_reg])

        rec = {
            "codice_provincia": row[col_cod_prov],
            "sigla_provincia": row[col_sigla],
            "codice_regione": row[col_cod_reg],
            "provincia": row[col_prov],
            "regione": row[col_reg],
        }

        if prov and reg:
            idx_full[(prov, reg)] = rec
        if prov and prov not in idx_prov:
            idx_prov[prov] = rec
        if reg and reg not in idx_reg:
            idx_reg[reg] = rec

    enriched = copy.deepcopy(data)

    n_total = 0
    n_match_full = 0
    n_match_prov = 0
    n_match_reg = 0

    for file_item in enriched:
        soggetti = file_item.get("soggetti") or []

        for ent in soggetti:
            n_total += 1

            ent, handled = enrich_codici_per_sovracomunali(ent, df_province, df_regioni)
            if handled:
                continue

            prov_raw = (ent.get("provincia") or "").strip()
            reg_raw = (ent.get("regione") or "").strip()

            if "codice_provincia" not in ent:
                ent["codice_provincia"] = ""
            if "sigla_provincia" not in ent:
                ent["sigla_provincia"] = ""
            if "codice_regione" not in ent:
                ent["codice_regione"] = ""

            prov = _norm_geo(prov_raw)
            reg = _norm_geo(reg_raw)

            rec = None

            if prov and reg and (prov, reg) in idx_full:
                rec = idx_full[(prov, reg)]
                n_match_full += 1
            elif prov and prov in idx_prov:
                rec = idx_prov[prov]
                n_match_prov += 1
            elif reg and reg in idx_reg:
                rec = idx_reg[reg]
                n_match_reg += 1

            if rec:
                if not (ent.get("codice_provincia") or "").strip():
                    ent["codice_provincia"] = rec["codice_provincia"]
                if not (ent.get("sigla_provincia") or "").strip():
                    ent["sigla_provincia"] = rec["sigla_provincia"]
                if not (ent.get("codice_regione") or "").strip():
                    ent["codice_regione"] = rec["codice_regione"]

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print("✅ Arricchimento codici completato")
    print("Totale soggetti:", n_total)
    print("Match provincia+regione:", n_match_full)
    print("Match solo provincia:", n_match_prov)
    print("Match solo regione:", n_match_reg)
    print("📄 Output:", OUTPUT_JSON)


# ------------------------------------------------------
# REPORT
# ------------------------------------------------------

def flatten_soggetti(json_data):
    rows = []
    for item in json_data:
        file_name = item.get("file", "")
        for ent in (item.get("soggetti") or []):
            rows.append({
                "file": file_name,
                "nome": ent.get("nome", ""),
                "tipo": ent.get("tipo", ""),
                "comune": ent.get("comune", ""),
                "comune_runts": ent.get("comune_runts", ""),
                "comune_fonte": ent.get("comune_fonte", ""),
                "comune_matchato": ent.get("comune_matchato", ""),
                "match_comune": ent.get("match_comune", ""),
                "codice_comune": ent.get("codice_comune", ""),
                "codice_provincia": ent.get("codice_provincia", ""),
                "provincia": ent.get("provincia", ""),
                "sigla_provincia": ent.get("sigla_provincia", ""),
                "codice_regione": ent.get("codice_regione", ""),
                "regione": ent.get("regione", ""),
            })
    return pd.DataFrame(rows)


def report_stats(df_soggetti: pd.DataFrame):
    print("=== MATCH COMUNE ===")
    print(df_soggetti["match_comune"].value_counts(dropna=False).rename_axis("match_comune").reset_index(name="count").to_string())

    print("\n=== FONTE COMUNE ===")
    print(df_soggetti["comune_fonte"].value_counts(dropna=False).rename_axis("comune_fonte").reset_index(name="count").to_string())

    print("\n=== PRIME RIGHE SENZA MATCH ===")
    print(
        df_soggetti[df_soggetti["match_comune"] == "none"][
            ["file", "nome", "tipo", "comune", "comune_runts", "comune_fonte"]
        ].head(50).to_string()
    )


# ------------------------------------------------------
# MAIN
# ------------------------------------------------------

def main():
    global df_province, df_regioni

    print("INPUT_JSON:", INPUT_JSON)
    print("OUTPUT_JSON:", OUTPUT_JSON)

    df_province, df_regioni = load_province_regioni(PROVINCE_CSV, REGIONI_CSV)

    df_comuni = load_comuni_csv(COMUNI_CSV)
    print("Righe comuni:", len(df_comuni))
    build_comuni_index(df_comuni)

    enriched_data, stats = enrich_comune_provincia_regione_smart(
        INPUT_JSON=INPUT_JSON,
        comuni_csv_path=COMUNI_CSV,
        OUTPUT_JSON=OUTPUT_JSON,
        fuzzy_threshold=FUZZY_THRESHOLD
    )

    df_soggetti = flatten_soggetti(enriched_data)
    print(df_soggetti.head(20).to_string())
    report_stats(df_soggetti)

    csv_out = Path(OUTPUT_JSON).with_suffix("").as_posix() + ".csv"
    df_soggetti.to_csv(csv_out, index=False, encoding="utf-8")
    print("CSV flat salvato in:", csv_out)


if __name__ == "__main__":
    main()