import os
import re
import json
import copy
import pandas as pd
import unicodedata
from collections import Counter

from region_config import get_reg_code, print_reg_code, build_region_file

reg_code = get_reg_code(default="09", required=True)
print_reg_code(reg_code)


CLASSIFICATION_FOLDER = r"classification"
JSON_STEP1_FOLDER = r"output/data/step_1" # Directory per i JSON con i risultati di Step 1 (estrazione nomi soggetti)
JSON_STEP2_FOLDER = r"output/data/step_2" # Directory per i JSON arricchiti con RUNTS e CAV (2.1.1) e con ALIAS_MAP (2.1.2)
INPUT_JSON = build_region_file(JSON_STEP1_FOLDER, reg_code, "risultati.json")

OUTPUT_JSON_TMP = build_region_file(JSON_STEP2_FOLDER, reg_code, "risultati_enriched_2.1.1.json")
OUTPUT_JSON = build_region_file(JSON_STEP2_FOLDER, reg_code, "risultati_enriched_2.1.2.json")

RUNTS_FILE = os.path.join(CLASSIFICATION_FOLDER, "cls_runts.csv")
PATH_LISTA_CAV = os.path.join(CLASSIFICATION_FOLDER, "cls_cav.csv")

testi = []
risultati = []

# -----------------------------
# FUZZY backend (rapidfuzz consigliato)
# -----------------------------
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_OK = True
except Exception:
    RAPIDFUZZ_OK = False

print("rapidfuzz:", "OK" if RAPIDFUZZ_OK else "MISSING (pip install rapidfuzz)")

# =========================================================
# PAROLE
# =========================================================

parole_no = [
    "COMUNE", "REGIONE", "PROVINCIA", "CITTÀ METROPOLITANA", "CITTA METROPOLITANA",
    "PREFETTURA", "QUESTURA", "CARABINIERI", "POLIZIA", "GUARDIA DI FINANZA",
    "TRIBUNALE", "PROCURA", "CORTE D'APPELLO", "CORTE D APPELLO", "ORDINE ",
    "ASL", "AUSL", "AZIENDA SANITARIA", "OSPEDALE", "PRONTO SOCCORSO",
    "SCUOLA", "ISTITUTO", "UFFICIO SCOLASTICO", "UNIVERSITÀ", "UNIVERSITA",
    "AMBITO", "PIANO DI ZONA", "DISTRETTO", "SOCIETÀ DELLA SALUTE", "SOCIETA DELLA SALUTE"
]

parole_si = [
    "ASSOCIAZIONE", "ASS.", "ASSNE", "ASS.NE",
    "COOPERATIVA SOCIALE", "COOP. SOCIALE", "FONDAZIONE",
    "ONLUS", "ODV", "APS", "ETS", "RUNTS",
    "IMPRESA SOCIALE", "ENTE DEL TERZO SETTORE", "VOLONTARIATO"
]

parole_soft = [
    "CASA", "CENTRO", "SPORTELLO", "DONNE", "DONNA",
    "ANTI VIOLENZA", "ANTIVIOLENZA"
]

# =========================================================
# Varianti deterministiche del nome
# =========================================================

_PREFIX_STRIP = [
    "ASSOCIAZIONE ",
    "ASSOCIAZIONE DI ",
    "ASSOCIAZIONE DI VOLONTARIATO ",
    "ORGANIZZAZIONE DI VOLONTARIATO ",
    "ORGANIZZAZIONI DI VOLONTARIATO ",
    "ASSOCIAZIONE DI PROMOZIONE SOCIALE ",
    "ASSOCIAZIONE CULTURALE ",
    "ASSOCIAZIONE SPORTIVA ",
    "ASSOCIAZIONE CULTURALE SPORTIVA ",
    "ASSOCIAZIONE CULTURALE SPORTIVA DILETTANTISTICA ",
    "COOPERATIVA ",
    "COOPERATIVA SOCIALE ",
    "SOCIETA' COOPERATIVA SOCIALE ",
    "SOCIETA COOPERATIVA SOCIALE ",
    "FONDAZIONE ",
    "CONSORZIO ",
]

_SUFFIX_STRIP = [
    " ONLUS", " APS", " ODV", " ETS",
    " SOCIETA' COOPERATIVA SOCIALE", " SOCIETA COOPERATIVA SOCIALE", " COOPERATIVA SOCIALE",
    " IMPRESA SOCIALE",
    " ASSOCIAZIONE DI PROMOZIONE SOCIALE",
    " ASSOCIAZIONE DI VOLONTARIATO",
    " ORGANIZZAZIONE DI VOLONTARIATO",
    " ORGANIZZAZIONI DI VOLONTARIATO",
    " S.R.L.", " SRL", " S.P.A.", " SPA",
]

GENERIC_CAV_TOKENS = {
    "CENTRO", "CENTRI", "SPORTELLO", "SPORTELLI", "ASCOLTO",
    "ANTIVIOLENZA", "VIOLENZA", "DONNA", "DONNE", "CAV",
    "CASA", "CASE", "RIFUGIO", "RIFUGI",
    "PRONTO", "AIUTO", "SERVIZIO", "SERVIZI",
    "ASSOCIAZIONE", "ASSOCIAZIONI", "ONLUS", "APS", "ODV",
    "COOPERATIVA", "COOPERATIVE", "SOCIALE", "SOCIALI",
    "DI", "DE", "DEL", "DELLA", "DELLE", "DEI", "DEGLI",
    "E", "ED", "PER", "CON", "A", "AL", "ALLA", "ALLE",
    "DA", "IN", "IL", "LA", "LE", "LO", "GLI", "I",
    "UN", "UNA"
}

generic_overlap = {
    "CENTRO", "CENTRI", "SPORTELLO", "SPORTELLI",
    "ASCOLTO", "ANTIVIOLENZA", "VIOLENZA",
    "DONNA", "DONNE", "CAV", "ASSOCIAZIONE", "ASSOCIAZIONI"
}

legal_tokens = {
    "ASSOCIAZIONE", "APS", "ODV", "ETS", "ONLUS",
    "COOPERATIVA", "SOCIETA", "SOCIETÀ", "SOCIALE",
    "IMPRESA", "VOLONTARIATO", "PROMOZIONE"
}

_PUBLIC_TOKENS = [
    "REGIONE", "PROVINCIA", "CITTA METROPOLITANA", "CITTÀ METROPOLITANA",
    "COMUNE", "PREFETTURA", "QUESTURA", "TRIBUNALE", "PROCURA",
    "CORTE D APPELLO", "MINISTERO", "DIPARTIMENTO",
    "AGENZIA REGIONALE", "AGENZIA NAZIONALE", "AUTORITA", "AUTORITÀ",
    "ASL", "AUSL", "AZIENDA SANITARIA", "OSPEDALE",
    "ISTITUTO SCOLASTICO", "SCUOLA", "UNIVERSITA", "UNIVERSITÀ"
]

_FUZZY_STOPWORDS = {
    "ASSOCIAZIONE", "ASSOCIAZIONI", "ASS", "ASSNE", "ASS.NE",
    "ORGANIZZAZIONE", "ORGANIZZAZIONI", "VOLONTARIATO",
    "PROMOZIONE", "SOCIALE", "SOCIETA", "SOCIETÀ", "COOPERATIVA",
    "IMPRESA", "ENTE", "TERZO", "SETTORE",
    "APS", "ODV", "ETS", "ONLUS", "RUNTS",
    "DI", "DEL", "DELLA", "DELL", "DEI", "DEGLI", "NEL", "NELLA", "NELL", "NEI",
    "DA", "DAL", "DALLA", "AL", "ALLA", "AI", "ALLE", "A",
    "PER", "CON", "SU", "IN", "E"
}

_GENERIC_ENTITY_NAMES = {
    "CENTRO ANTIVIOLENZA", "CENTRI ANTIVIOLENZA", "CAV",
    "CASA RIFUGIO", "CASE RIFUGIO",
    "CENTRO DI ASCOLTO", "CENTRI DI ASCOLTO",
    "SPORTELLO DI ASCOLTO", "SPORTELLI DI ASCOLTO",
    "ASSOCIAZIONE", "ASSOCIAZIONI", "COOPERATIVA", "COOPERATIVE",
    "CONSULTORIO", "CONSULTORI",
}

_GENERIC_IDENTITY_TOKENS = {
    "CENTRO", "CENTRI", "ANTIVIOLENZA", "ANTIVIOLENZE", "CAV",
    "CASA", "CASE", "RIFUGIO", "RIFUGI",
    "ASCOLTO", "SPORTELLO", "SPORTELLI",
    "DI", "DEL", "DELLA", "DEI", "DELLE",
    "APS", "ODV", "ETS", "ONLUS", "ASSOCIAZIONE", "ASSOCIAZIONI"
}

# =========================================================
# UTILITY FUNCTIONS
# =========================================================

def first_existing_path(candidates: list[str]) -> str:
    for p in candidates:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError(f"Nessun path valido trovato tra: {candidates}")


def _norm_nome(s: str) -> str:
    if not s:
        return ""
    s = str(s).upper().strip()
    s = s.replace("'", "'").replace("`", "'")
    s = re.sub(r"\bO\.?\s*D\.?\s*V\.?\b", "ODV", s)
    s = re.sub(r"\bA\.?\s*P\.?\s*S\.?\b", "APS", s)
    s = re.sub(r"\bE\.?\s*T\.?\s*S\.?\b", "ETS", s)
    s = re.sub(r"\bO\.?\s*N\.?\s*L\.?\s*U\.?\s*S\.?\b", "ONLUS", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_suffix_norm(n: str) -> str:
    n = (n or "").strip()
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIX_STRIP:
            if n.endswith(suf):
                n = n[: -len(suf)].strip()
                changed = True
    return n


def compact_alnum(s: str) -> str:
    s = _norm_nome(s)
    return re.sub(r"[^a-z0-9]", "", s)


def _norm_compact(s: str) -> str:
    if not s:
        return ""
    s = _norm_nome(s)
    return re.sub(r"[^A-Z0-9]", "", s)


def is_runts_candidate(nome: str) -> bool:
    n = _norm_nome(nome)
    if not n:
        return False
    for p in parole_no:
        if p in n:
            return False
    for p in parole_si:
        if p in n:
            return True
    for p in parole_soft:
        if p in n:
            return True
    return False


def is_public_entity(nome: str, tipo: str = "") -> bool:
    n = _norm_nome(nome)
    t = (tipo or "").upper()
    if any(x in t for x in [
        "REGION", "PROVINC", "CITT", "COMUN", "PREFETT",
        "QUESTUR", "TRIBUNAL", "PROCURA", "MINISTER"
    ]):
        return True
    for tok in _PUBLIC_TOKENS:
        if tok in n:
            return True
    return False


def informative_tokens_for_match(s: str) -> list[str]:
    s = _norm_nome(s)
    toks = re.findall(r"[A-Z0-9]+", s)
    toks = [t for t in toks if t not in _FUZZY_STOPWORDS]
    return toks


def has_distinctive_overlap(overlap_tokens: set) -> bool:
    clean = {t for t in overlap_tokens if t not in generic_overlap}
    return len(clean) > 0


def has_specific_identity(nome: str) -> bool:
    toks = informative_tokens_for_match(nome)
    if not toks:
        return False
    specific = [t for t in toks if t not in _GENERIC_IDENTITY_TOKENS]
    return len(specific) >= 1


def is_name_already_well_resolved_by_cav(nome: str, cav_match: dict | None) -> bool:
    if not cav_match:
        return False
    overlap = set(cav_match.get("overlap_tokens", []))
    return has_distinctive_overlap(overlap)


def is_generic_entity_name(nome: str) -> bool:
    n = _norm_nome(nome)
    if not n:
        return True
    return n in _GENERIC_ENTITY_NAMES


def specific_overlap_tokens(nome: str, candidato: str) -> set[str]:
    q = set(informative_tokens_for_match(nome))
    c = set(informative_tokens_for_match(candidato))
    q_spec = {t for t in q if t not in _GENERIC_IDENTITY_TOKENS}
    c_spec = {t for t in c if t not in _GENERIC_IDENTITY_TOKENS}
    return q_spec & c_spec


def is_geo_cav_name(nome: str) -> bool:
    n = _norm_nome(nome)
    return bool(re.match(r"^CENTR[OI] ANTIVIOLENZA DI [A-Z0-9 ''\-]+$", n))


def dotted_acronym_tokens(s: str) -> set:
    raw = (s or "").strip()
    if not raw:
        return set()
    acronyms = set()
    for m in re.finditer(r"(?:\b[A-Za-z]\.){2,}[A-Za-z]?\b\.?", raw):
        txt = m.group(0)
        letters = re.findall(r"[A-Za-z]", txt)
        if len(letters) >= 3:
            acronyms.add("".join(letters).lower())
    parts = raw.split()
    if len(parts) >= 3 and all(len(p) == 1 and p.isalpha() for p in parts):
        acronyms.add("".join(parts).lower())
    return acronyms


def cav_token_set(s: str) -> set:
    s_norm = _norm_nome(s)
    toks = re.findall(r"\w+", s_norm)
    base = {t.upper() for t in toks if t and t.lower() not in GENERIC_CAV_TOKENS and len(t) >= 4}
    acr = {a.upper() for a in dotted_acronym_tokens(s)}
    return base | acr


def should_save_debug_fuzzy(nome: str, candidato: str, score: int, min_score: int = 70) -> bool:
    if not nome or not candidato:
        return False
    if score < min_score:
        return False
    if is_generic_entity_name(nome):
        return False
    if not has_specific_identity(nome):
        return False
    overlap = specific_overlap_tokens(nome, candidato)
    return len(overlap) >= 1

# =========================================================
# LOAD CLASSIFICATION FILES
# =========================================================

def load_runts_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    if df.empty:
        raise RuntimeError(f"RUNTS CSV vuoto: {path}")
    return df


def load_cav_df(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File lista CAV non trovato: {path}")
    df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    if df.empty:
        raise RuntimeError(f"Lista CAV vuota: {path}")
    return df

# =========================================================
# COLS MAPPING
# =========================================================

def map_runts_columns_exact(df: pd.DataFrame) -> dict:
    required = ["Denominazione", "Codice_Fiscale", "Comune", "Sezione", "Codice_Regione"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Colonne RUNTS mancanti: {missing}. Colonne disponibili: {list(df.columns)}")
    return {
        "denominazione": "Denominazione",
        "cf_or_id": "Codice_Fiscale",
        "comune": "Comune",
        "natura": "Sezione",
        "codice_regione": "Codice_Regione",
    }


def map_cav_columns_exact(df: pd.DataFrame) -> dict:
    required = ["NOME_ANAGRAFICA_RISP"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(
            f"Colonne lista CAV mancanti: {missing}. Colonne disponibili: {list(df.columns)}"
        )
    return {
        "nome": "NOME_ANAGRAFICA_RISP",
        "codice_regione": "COD_REGIONE" if "COD_REGIONE" in df.columns else None,
        "codice_provincia": "COD_PROVINCIA" if "COD_PROVINCIA" in df.columns else None,
        "codice_comune": "COD_COMUNE" if "COD_COMUNE" in df.columns else None,
    }

# =========================================================
# CAV MATCHER
# =========================================================

def match_cav_name(nome_soggetto: str, cav_rows: list, comune_hint: str = "") -> dict | None:
    nome = (nome_soggetto or "").strip()
    if not nome:
        return None
    if len(nome.strip()) <= 3:
        return None
    if is_generic_entity_name(nome):
        return None

    nome_norm = _norm_nome(nome)
    nome_tokens = cav_token_set(nome)
    comune_hint_norm = _norm_nome(comune_hint or "")

    if not nome_tokens and len(nome_norm) < 8:
        return None

    best = None
    best_score = -1

    for row in cav_rows:
        cav_norm = row["norm_name"]
        cav_tokens = row["tokens"]

        if not cav_tokens:
            continue

        overlap = cav_tokens & nome_tokens
        overlap_distinctive = has_distinctive_overlap(overlap)
        score = 0

        if nome_norm == cav_norm:
            score = 1000
        elif cav_norm and cav_norm in nome_norm and overlap_distinctive:
            score = 900
        elif nome_norm and nome_norm in cav_norm and overlap_distinctive:
            score = 850
        elif overlap_distinctive:
            score = 100 + 40 * len(overlap)
            if cav_tokens.issubset(nome_tokens):
                score += 150
            if comune_hint_norm and comune_hint_norm in nome_norm:
                score += 20

        if score > best_score:
            best_score = score
            best = row | {
                "match_score": score,
                "overlap_tokens": sorted(list(overlap))
            }

    if best and best_score >= 180 and has_distinctive_overlap(set(best.get("overlap_tokens", []))):
        return best
    return None


def build_cav_matcher(df_cav: pd.DataFrame, cav_cols: dict):
    cav_rows = []
    for _, row in df_cav.iterrows():
        raw_name = (row.get(cav_cols["nome"], "") or "").strip()
        if not raw_name:
            continue
        raw_name_norm = _norm_nome(raw_name)
        tokset = cav_token_set(raw_name)
        compact = compact_alnum(raw_name)
        cav_rows.append({
            "raw_name": raw_name,
            "norm_name": raw_name_norm,
            "compact_name": compact,
            "tokens": tokset,
            "codice_regione": row.get(cav_cols["codice_regione"], "") if cav_cols.get("codice_regione") else "",
            "codice_provincia": row.get(cav_cols["codice_provincia"], "") if cav_cols.get("codice_provincia") else "",
            "codice_comune": row.get(cav_cols["codice_comune"], "") if cav_cols.get("codice_comune") else "",
        })
    return cav_rows

# =========================================================
# NAME VARIANTS
# =========================================================

def _name_variants(nome: str) -> list[str]:
    base = (nome or "").strip()
    if not base:
        return []

    variants = [base]

    if " - " in base:
        variants.append(base.split(" - ", 1)[0].strip())

    n = _norm_nome(base)

    n2 = re.sub(r"^ASSOCIAZIONE\s+DI\s+VOLONTARIATO\s+", "ASSOCIAZIONE ", n).strip()
    if n2 and n2 != n:
        variants.append(n2)

    n3 = re.sub(r"^ORGANIZZAZIONE\s+DI\s+VOLONTARIATO\s+", "ASSOCIAZIONE ", n).strip()
    if n3 and n3 != n:
        variants.append(n3)

    for p in _PREFIX_STRIP:
        if n.startswith(p):
            stripped = n[len(p):].strip()
            if stripped:
                variants.append(stripped)

    extra = []
    for v in variants:
        nv = _norm_nome(v)
        sv = _strip_suffix_norm(nv)
        if sv and sv != nv:
            extra.append(sv)
    variants.extend(extra)

    out = []
    seen = set()
    for v in variants:
        k = _norm_nome(v)
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


def fuzzy_normalize(s: str) -> str:
    if not s:
        return ""
    s = _norm_nome(s)
    toks = re.findall(r"[A-Z0-9]+", s)
    toks = [t for t in toks if t not in _FUZZY_STOPWORDS]
    return " ".join(toks).strip()

# =========================================================
# RUNTS INDEXES
# =========================================================

def build_runts_indexes(df: pd.DataFrame, denom_col: str, codice_regione: str | None = None):
    if codice_regione:
        codice_regione = str(codice_regione).zfill(2)
        df = df[df["Codice_Regione"].astype(str).str.zfill(2) == codice_regione]

    idx_exact = {}
    idx_compact = {}
    prefix_list = []
    fuzzy_names = []
    fuzzy_names_fz = []
    fuzzy_rows = []

    for _, row in df.iterrows():
        denom = row.get(denom_col, "")
        key_exact = _norm_nome(denom)
        key_compact = _norm_compact(denom)
        d = row.to_dict()

        if key_exact and key_exact not in idx_exact:
            idx_exact[key_exact] = d
            prefix_list.append((key_exact, d))
            fuzzy_names.append(key_exact)
            fuzzy_names_fz.append(fuzzy_normalize(key_exact))
            fuzzy_rows.append(d)

        if key_compact and key_compact not in idx_compact:
            idx_compact[key_compact] = d

    prefix_list.sort(key=lambda x: len(x[0]))
    return idx_exact, idx_compact, prefix_list, fuzzy_names, fuzzy_names_fz, fuzzy_rows


def fuzzy_lookup_best(query_text: str,
                      fuzzy_names: list, fuzzy_names_fz: list, fuzzy_rows: list,
                      min_score: int = 93):
    if not RAPIDFUZZ_OK or not query_text or not fuzzy_names:
        return None, 0, ""

    q = fuzzy_normalize(query_text)
    if not q:
        return None, 0, ""

    match = process.extractOne(q, fuzzy_names_fz, scorer=fuzz.token_sort_ratio)
    if not match:
        return None, 0, ""

    _best_norm, score, idx = match
    score = int(score)
    best_name = fuzzy_names[idx]

    if score >= min_score:
        return fuzzy_rows[idx], score, best_name
    return None, score, best_name


def runts_lookup(nome: str, tipo: str, alias_map: dict,
                 idx_exact: dict, idx_compact: dict, prefix_list: list,
                 fuzzy_names: list, fuzzy_names_fz: list, fuzzy_rows: list,
                 min_fuzzy_score: int = 93, cav_min_fuzzy_score: int = 88):
    variants = _name_variants(nome)
    best_fuzzy_name = ""
    best_fuzzy_score = 0

    if alias_map:
        k = _norm_nome(nome)
        ali = alias_map.get(k, "")
        if ali:
            row = idx_exact.get(ali)
            if row:
                return row, "alias", nome, None, best_fuzzy_name, best_fuzzy_score

    for v in variants:
        k = _norm_nome(v)
        row = idx_exact.get(k)
        if row:
            return row, "exact", v, None, best_fuzzy_name, best_fuzzy_score

    for v in variants:
        kc = _norm_compact(v)
        row = idx_compact.get(kc)
        if row:
            return row, "compact", v, None, best_fuzzy_name, best_fuzzy_score

    for v in variants:
        k = _norm_nome(v)
        if not k:
            continue
        for denom_norm, r in prefix_list:
            if denom_norm.startswith(k):
                if len(denom_norm) == len(k):
                    return r, "prefix", v, None, best_fuzzy_name, best_fuzzy_score
                nxt = denom_norm[len(k):len(k)+1]
                if nxt in (" ", "-", "(", "'", "'", ".", ",", "/"):
                    return r, "prefix", v, None, best_fuzzy_name, best_fuzzy_score
            if k.startswith(denom_norm):
                if len(k) == len(denom_norm):
                    return r, "prefix", v, None, best_fuzzy_name, best_fuzzy_score
                nxt = k[len(denom_norm):len(denom_norm)+1]
                if nxt in (" ", "-", "(", "'", "'", ".", ",", "/"):
                    return r, "prefix", v, None, best_fuzzy_name, best_fuzzy_score

    t = (tipo or "").upper()
    is_cav = (
        ("CAV" in t) or ("ANTIVIOLENZA" in t) or
        ("CENTRO ANTIVIOLENZA" in t) or ("CENTRI ANTIVIOLENZA" in t) or
        ("CASE RIFUGIO" in t)
    )
    threshold = cav_min_fuzzy_score if is_cav else min_fuzzy_score
    v_best = variants[-1] if variants else nome
    q = _norm_nome(v_best)

    row, score, best_name = fuzzy_lookup_best(q, fuzzy_names, fuzzy_names_fz, fuzzy_rows, min_score=threshold)
    best_fuzzy_score = int(score or 0)
    best_fuzzy_name = best_name or ""

    if row:
        return row, "fuzzy", v_best, best_fuzzy_score, best_fuzzy_name, best_fuzzy_score

    return None, "none", "", None, best_fuzzy_name, best_fuzzy_score


def build_alias_map_from_report(rows, top_n: int = 10, min_score: int = 92):
    alias_map = {}
    for r in rows:
        nome = (r.get("nome") or "").strip()
        best = (r.get("best_fuzzy_candidate") or "").strip()
        score = int(r.get("best_fuzzy_score") or 0)
        if not nome or not best:
            continue
        if score < min_score:
            continue
        k = _norm_nome(nome)
        v = _norm_nome(best)
        if k and v and k not in alias_map:
            alias_map[k] = v
        if len(alias_map) >= top_n:
            break
    return alias_map


def get_entities_list_ref(file_item: dict):
    if isinstance(file_item.get("soggetti"), list):
        return file_item["soggetti"]
    risultato = file_item.get("risultato") or {}
    if isinstance(risultato.get("entities"), list):
        return risultato["entities"]
    return []

# =========================================================
# ENRICH STEP1 JSON
# =========================================================

def enrich_step1_json_with_runts(INPUT_JSON, OUTPUT_JSON,
                                 idx_exact, idx_compact, prefix_list,
                                 fuzzy_names, fuzzy_names_fz, fuzzy_rows,
                                 runts_cols,
                                 alias_map: dict | None = None,
                                 cav_rows: list | None = None,
                                 min_fuzzy_score: int = 93,
                                 cav_min_fuzzy_score: int = 88,
                                 min_debug_fuzzy_score: int = 70):
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    enriched = copy.deepcopy(data)

    cf_col = runts_cols["cf_or_id"]
    comune_col = runts_cols["comune"]
    natura_col = runts_cols["natura"]
    denom_col = runts_cols["denominazione"]

    cav_rows = cav_rows or []

    ent_count = match_count = match_exact = match_fuzzy = match_alias = 0
    forced_by_type = fuzzy_skipped = best_fuzzy_saved = 0
    match_lista_cav_count = tipo_segnalato_da_lista_cav = tipo_gia_protetto_lista_cav = 0
    tipo_modificato_finale_count = tipo_modificato_da_runts_natura = tipo_modificato_da_lista_cav_finale = 0

    TIPI_PROTETTI_CAV = {"CAV/Centri Antiviolenza", "Case Rifugio"}
    TIPI_PROTETTI_FINALI = {"CAV/Centri Antiviolenza", "Case Rifugio"}
    TIPI_CENTRO_ASCOLTO = {"Centri/Sportelli di ascolto"}
    NATURE_RUNTS_ASSOCIATIVE = {
        "ASSOCIAZIONI DI PROMOZIONE SOCIALE", "ORGANIZZAZIONI DI VOLONTARIATO",
        "ENTI FILANTROPICI", "IMPRESE SOCIALI", "RETI ASSOCIATIVE",
        "SOCIETA DI MUTUO SOCCORSO", "ALTRI ENTI DEL TERZO SETTORE"
    }

    for file_item in enriched:
        entities = get_entities_list_ref(file_item)

        for ent in entities:
            nome = (ent.get("nome") or "").strip()
            if not nome:
                continue

            ent_count += 1
            tipo = (ent.get("tipo") or "").strip()
            tipo_originale_step = tipo

            ent["match_lista_cav"] = False
            ent["match_lista_cav_nome"] = ""
            ent["match_lista_cav_score"] = 0
            ent["match_lista_cav_overlap_tokens"] = []
            ent["tipo_matchato_da_lista_cav"] = False
            ent["tipo_aggiornato_da_lista_cav"] = False
            ent["codice_regione_cav"] = ""
            ent["codice_provincia_cav"] = ""
            ent["codice_comune_cav"] = ""
            ent["tipo_precedente"] = tipo
            ent["tipo_fonte_aggiornamento"] = ""
            ent["tipo_modificato_finale"] = False

            comune_hint = (ent.get("comune") or "").strip()

            cav_match = None if is_generic_entity_name(nome) else match_cav_name(nome, cav_rows, comune_hint=comune_hint)
            in_lista_cav = cav_match is not None
            ent["match_lista_cav"] = in_lista_cav

            if in_lista_cav:
                match_lista_cav_count += 1
                ent["match_lista_cav_nome"] = cav_match.get("raw_name", "")
                ent["match_lista_cav_score"] = cav_match.get("match_score", 0)
                ent["match_lista_cav_overlap_tokens"] = cav_match.get("overlap_tokens", [])
                ent["codice_regione_cav"] = cav_match.get("codice_regione", "")
                ent["codice_provincia_cav"] = cav_match.get("codice_provincia", "")
                ent["codice_comune_cav"] = cav_match.get("codice_comune", "")

                if tipo in TIPI_PROTETTI_CAV:
                    tipo_gia_protetto_lista_cav += 1
                else:
                    ent["tipo_matchato_da_lista_cav"] = True
                    tipo_segnalato_da_lista_cav += 1

            tipo_u = tipo.upper()
            force_runts = (
                ("CAV" in tipo_u) or ("CENTRI ANTIVIOLENZA" in tipo_u) or
                ("CENTRO ANTIVIOLENZA" in tipo_u) or ("CASE RIFUGIO" in tipo_u)
            )
            if force_runts:
                forced_by_type += 1

            ok_fuzzy_dbg = (
                (force_runts or is_runts_candidate(nome))
                and not is_public_entity(nome, tipo)
                and not is_generic_entity_name(nome)
                and has_specific_identity(nome)
                and not is_name_already_well_resolved_by_cav(nome, cav_match)
            )

            best_dbg_name = ""
            best_dbg_score = 0

            if ok_fuzzy_dbg and RAPIDFUZZ_OK and fuzzy_names:
                variants_dbg = _name_variants(nome)
                v_dbg = (variants_dbg[-1] if variants_dbg else nome)
                q_dbg = _norm_nome(v_dbg)

                _, sc, bn = fuzzy_lookup_best(q_dbg, fuzzy_names, fuzzy_names_fz, fuzzy_rows, min_score=1000)
                sc = int(sc or 0)

                if should_save_debug_fuzzy(nome, bn, sc, min_debug_fuzzy_score):
                    best_dbg_name = bn or ""
                    best_dbg_score = sc
                    best_fuzzy_saved += 1
                else:
                    best_dbg_name = ""
                    best_dbg_score = 0

            if is_generic_entity_name(nome) or not has_specific_identity(nome):
                best_dbg_name = ""
                best_dbg_score = 0

            if cav_match and cav_match.get("match_score", 0) >= 300:
                best_dbg_name = ""
                best_dbg_score = 0

            row, how, used_variant, fuzzy_score, best_name, best_score = runts_lookup(
                nome, tipo, alias_map or {},
                idx_exact, idx_compact, prefix_list,
                fuzzy_names, fuzzy_names_fz, fuzzy_rows,
                min_fuzzy_score=10_000, cav_min_fuzzy_score=10_000
            )

            if is_generic_entity_name(nome):
                if how in {"prefix", "compact", "fuzzy", "alias"}:
                    row = None
                    how = "none"
                    used_variant = ""
                    fuzzy_score = ""
                    best_name = ""
                    best_score = 0

            if how == "none":
                ok_fuzzy = ok_fuzzy_dbg
                if ok_fuzzy and RAPIDFUZZ_OK:
                    row, how, used_variant, fuzzy_score, best_name, best_score = runts_lookup(
                        nome, tipo, alias_map or {},
                        idx_exact, idx_compact, prefix_list,
                        fuzzy_names, fuzzy_names_fz, fuzzy_rows,
                        min_fuzzy_score=min_fuzzy_score,
                        cav_min_fuzzy_score=cav_min_fuzzy_score
                    )
                    if is_generic_entity_name(nome):
                        if how in {"prefix", "compact", "fuzzy", "alias"}:
                            row = None
                            how = "none"
                            used_variant = ""
                            fuzzy_score = ""
                            best_name = ""
                            best_score = 0
                else:
                    fuzzy_skipped += 1

            ent["match_runts_tipo"] = how
            ent["match_runts_esatto"] = (how == "exact")
            ent["match_runts_variant"] = used_variant
            ent["match_runts_fuzzy_score"] = (fuzzy_score if how == "fuzzy" else "")
            ent["best_fuzzy_candidate"] = best_dbg_name
            ent["best_fuzzy_score"] = best_dbg_score
            ent["cf"] = ""
            ent["comune_runts"] = ""
            ent["natura_runts"] = ""
            ent["denominazione_runts"] = ""
            ent["match_runts_esatto_testo"] = False
            ent["match_runts_compatibile_testo"] = False

            if row:
                denominazione_runts = (row.get(denom_col) or "").strip()
                ent["cf"] = (row.get(cf_col) or "").strip()
                ent["comune_runts"] = (row.get(comune_col) or "").strip()
                ent["natura_runts"] = (row.get(natura_col) or "").strip()
                ent["denominazione_runts"] = denominazione_runts

                nome_norm = _norm_nome(nome)
                runts_norm = _norm_nome(denominazione_runts)
                ent["match_runts_esatto_testo"] = (nome_norm == runts_norm)
                ent["match_runts_compatibile_testo"] = (nome_norm in runts_norm or runts_norm in nome_norm)

                match_count += 1
                if how == "exact":
                    match_exact += 1
                if how == "fuzzy":
                    match_fuzzy += 1
                if how == "alias":
                    match_alias += 1

            tipo_corrente = (ent.get("tipo") or "").strip()
            natura_runts = (ent.get("natura_runts") or "").strip().upper()
            match_lista_cav = ent.get("match_lista_cav") is True

            nuovo_tipo = None
            fonte_tipo = ""

            if tipo_corrente in TIPI_PROTETTI_FINALI:
                pass
            elif match_lista_cav and tipo_corrente in ({"Altro", ""} | TIPI_CENTRO_ASCOLTO):
                nuovo_tipo = "CAV/Centri Antiviolenza"
                fonte_tipo = "lista_cav"
            elif natura_runts in NATURE_RUNTS_ASSOCIATIVE and tipo_corrente in {
                "Altro", "",
                "Ente terzo settore - ETS (iscritto al RUNTS)",
                "Centri/Sportelli di ascolto"
            }:
                nuovo_tipo = natura_runts
                fonte_tipo = "runts_natura"

            if nuovo_tipo and nuovo_tipo != tipo_corrente:
                ent["tipo_precedente"] = tipo_corrente
                ent["tipo"] = nuovo_tipo
                ent["tipo_fonte_aggiornamento"] = fonte_tipo
                ent["tipo_modificato_finale"] = True
                tipo_modificato_finale_count += 1
                if fonte_tipo == "lista_cav":
                    ent["tipo_aggiornato_da_lista_cav"] = True
                    tipo_modificato_da_lista_cav_finale += 1
                elif fonte_tipo == "runts_natura":
                    ent["tipo_aggiornato_da_lista_cav"] = False
                    tipo_modificato_da_runts_natura += 1
            else:
                ent["tipo_precedente"] = tipo_originale_step
                ent["tipo_aggiornato_da_lista_cav"] = False

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print("✅ Arricchimento completato")
    print("   entità processate:", ent_count)
    print("   match RUNTS:", match_count)
    print("   match exact:", match_exact)
    print("   match prefix/compact:", match_count - match_exact - match_fuzzy - match_alias)
    print("   match fuzzy:", match_fuzzy, f"(soglia base={min_fuzzy_score}, CAV={cav_min_fuzzy_score})")
    print("   match alias:", match_alias)
    print("   forzati dal tipo (CAV/...):", forced_by_type)
    print("   fuzzy saltato (non candidato o ente pubblico):", fuzzy_skipped)
    print("   best_fuzzy salvati (>= debug soglia):", best_fuzzy_saved, f"(debug >= {min_debug_fuzzy_score})")
    print("   match lista CAV:", match_lista_cav_count)
    print("   segnalati da lista CAV:", tipo_segnalato_da_lista_cav)
    print("   già protetti in lista CAV:", tipo_gia_protetto_lista_cav)
    print("   tipo modificato finale:", tipo_modificato_finale_count)
    print("   tipo modificato da lista CAV:", tipo_modificato_da_lista_cav_finale)
    print("   tipo modificato da natura RUNTS:", tipo_modificato_da_runts_natura)
    print("📄 Output:", OUTPUT_JSON)

# =========================================================
# REPORT FUNCTIONS
# =========================================================

def report_top_non_matches(enriched_json_path: str,
                           top_n: int = 30,
                           min_best_score: int = 70,
                           only_how: str = "none"):
    with open(enriched_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for file_item in data:
        file_name = file_item.get("file", "") or file_item.get("filename", "") or ""
        entities = (file_item.get("risultato") or {}).get("entities") or []
        for ent in entities:
            how = (ent.get("match_runts_tipo") or "").strip()
            if only_how and how != only_how:
                continue
            best_score = int(ent.get("best_fuzzy_score") or 0)
            if best_score < min_best_score:
                continue
            rows.append({
                "file": file_name,
                "nome": (ent.get("nome") or "").strip(),
                "tipo": (ent.get("tipo") or "").strip(),
                "match_runts_tipo": how,
                "best_fuzzy_score": best_score,
                "best_fuzzy_candidate": (ent.get("best_fuzzy_candidate") or "").strip(),
            })

    rows.sort(key=lambda x: x["best_fuzzy_score"], reverse=True)

    print(f"\n📌 TOP {top_n} '{only_how}' per best_fuzzy_score (>= {min_best_score})")
    print("-" * 110)
    for r in rows[:top_n]:
        print(f"[{r['best_fuzzy_score']:>3}] {r['nome']}  |  tipo={r['tipo']}  |  best='{r['best_fuzzy_candidate']}'  |  file={r['file']}")
    print("-" * 110)
    print(f"Totale righe nel report: {len(rows)}\n")
    return rows


def suggest_actions_from_report(rows, top_n: int = 30,
                                score_hi: int = 92,
                                score_mid_lo: int = 85,
                                score_mid_hi: int = 91):
    def _is_acronym(s: str) -> bool:
        s = (s or "").strip()
        return bool(re.fullmatch(r"[A-Z]{2,6}", s))

    suggestions = []
    for r in rows[:top_n]:
        nome = (r.get("nome") or "").strip()
        tipo = (r.get("tipo") or "").upper()
        best = (r.get("best_fuzzy_candidate") or "").strip()
        score = int(r.get("best_fuzzy_score") or 0)

        if not best or score <= 0:
            continue

        actions = []
        rationale = []

        if "CAV" in tipo or "ANTIVIOLENZA" in tipo:
            if score_mid_lo <= score <= score_mid_hi:
                actions.append("Abbassa soglia fuzzy SOLO per CAV (es. 88–90)")
                rationale.append(f"CAV con score {score} vicino alla soglia")

        if len(nome) <= 14 and len(best) >= len(nome) + 10 and score >= score_mid_lo:
            actions.append("Aggiungi alias manuale (nome breve → denominazione RUNTS)")
            rationale.append("Nome input molto corto rispetto alla denominazione RUNTS")

        if _is_acronym(nome) and score >= score_mid_lo:
            actions.append("Aggiungi gestione sigle: mappa acronimo → denominazione RUNTS (o amplia varianti)")
            rationale.append("Input è una sigla; RUNTS spesso contiene forma estesa")

        nome_tokens = set(re.findall(r"[A-ZÀ-ÖØ-Ý0-9]+", nome.upper()))
        best_tokens = set(re.findall(r"[A-ZÀ-ÖØ-Ý0-9]+", best.upper()))
        overlap = len(nome_tokens & best_tokens)
        extra_best_legal = len((best_tokens - nome_tokens) & legal_tokens)

        if overlap >= 1 and extra_best_legal >= 2 and score >= score_mid_lo:
            actions.append("Rafforza _name_variants: strip più aggressivo di suffissi/prefissi legali (APS/ODV/ONLUS/COOP...)")
            rationale.append("Il best candidate differisce soprattutto per parole legali (APS/ODV/COOP...)")

        if score_mid_lo <= score <= score_hi:
            actions.append("fuzzy_normalize già attivo: se ancora sotto soglia, valuta alias o varianti")
            rationale.append("Score medio-alto ma sotto soglia")

        if not actions:
            actions.append("Caso da ispezionare: possibile rumore o denominazione molto diversa")
            rationale.append(f"Score={score}")

        suggestions.append({
            "score": score,
            "nome": nome,
            "tipo": r.get("tipo", ""),
            "best_fuzzy_candidate": best,
            "azioni": actions,
            "perché": rationale,
            "file": r.get("file", "")
        })

    action_counter = Counter(a for s in suggestions for a in s["azioni"])
    print("\n🧠 Azioni consigliate (più frequenti):")
    for a, c in action_counter.most_common():
        print(f"- {a}  ({c})")

    print("\n📌 Top suggerimenti (dettaglio):")
    for s in suggestions[:min(15, len(suggestions))]:
        print(f"\n[{s['score']}] {s['nome']} | tipo={s['tipo']} | best='{s['best_fuzzy_candidate']}' | file={s['file']}")
        for a in s["azioni"]:
            print(f"  - AZIONE: {a}")
        for p in s["perché"]:
            print(f"    • {p}")

    return suggestions

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    
    print("RUNTS_FILE:", RUNTS_FILE)

    # --- Load CAV ---
    df_cav = load_cav_df(PATH_LISTA_CAV)
    cav_cols = map_cav_columns_exact(df_cav)

    cav_names_norm = set(
        df_cav[cav_cols["nome"]].fillna("").map(_norm_nome).tolist()
    )
    print("Lista CAV caricata:", len(df_cav))
    print("Nomi CAV normalizzati:", len(cav_names_norm))

    if cav_cols.get("codice_regione"):
        df_cav = df_cav[
            df_cav[cav_cols["codice_regione"]].astype(str).str.zfill(2) == str(reg_code).zfill(2)
        ].copy()

    if df_cav.empty:
        raise RuntimeError(f"Nessun record CAV trovato per la regione {reg_code}")

    cav_rows = build_cav_matcher(df_cav, cav_cols)
    print("Matcher CAV costruito:", len(cav_rows))

    # --- Load RUNTS ---
    runts_df = load_runts_df(RUNTS_FILE)
    runts_cols = map_runts_columns_exact(runts_df)

    (
        idx_exact, idx_compact, prefix_list,
        fuzzy_names, fuzzy_names_fz, fuzzy_rows
    ) = build_runts_indexes(runts_df, runts_cols["denominazione"], codice_regione=reg_code)

    print("RUNTS righe indicizzate:", len(fuzzy_rows))

    # --- Pass 1 ---
    print("Input JSON da arricchire:", INPUT_JSON)
    print("Output JSON arricchito:", OUTPUT_JSON_TMP)

    enrich_step1_json_with_runts(
        INPUT_JSON=INPUT_JSON,
        OUTPUT_JSON=OUTPUT_JSON_TMP,
        idx_exact=idx_exact,
        idx_compact=idx_compact,
        prefix_list=prefix_list,
        fuzzy_names=fuzzy_names,
        fuzzy_names_fz=fuzzy_names_fz,
        fuzzy_rows=fuzzy_rows,
        runts_cols=runts_cols,
        alias_map={},
        cav_rows=cav_rows,
        min_fuzzy_score=93,
        cav_min_fuzzy_score=88,
        min_debug_fuzzy_score=70
    )

    # --- Pass 2 con ALIAS_MAP auto ---
    rows_none = report_top_non_matches(OUTPUT_JSON_TMP, top_n=50, min_best_score=70, only_how="none")

    ALIAS_MAP = build_alias_map_from_report(rows_none, top_n=10, min_score=92)
    print("\nALIAS_MAP (auto top 10):")
    for k, v in ALIAS_MAP.items():
        print(f"- {k} -> {v}")

    enrich_step1_json_with_runts(
        INPUT_JSON=INPUT_JSON,
        OUTPUT_JSON=OUTPUT_JSON,
        idx_exact=idx_exact,
        idx_compact=idx_compact,
        prefix_list=prefix_list,
        fuzzy_names=fuzzy_names,
        fuzzy_names_fz=fuzzy_names_fz,
        fuzzy_rows=fuzzy_rows,
        runts_cols=runts_cols,
        alias_map=ALIAS_MAP,
        cav_rows=cav_rows,
        min_fuzzy_score=93,
        cav_min_fuzzy_score=88,
        min_debug_fuzzy_score=70
    )

    # --- Report finali ---
    rows_none_final = report_top_non_matches(OUTPUT_JSON, top_n=30, min_best_score=70, only_how="none")
    rows_prefix = report_top_non_matches(OUTPUT_JSON, top_n=30, min_best_score=70, only_how="prefix")
    suggestions = suggest_actions_from_report(rows_none_final, top_n=30)

    # --- Debug CAV matches ---
    PATH_JSON = OUTPUT_JSON

    with open(PATH_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for file_item in data:
        file_name = file_item.get("file", "")
        entities = get_entities_list_ref(file_item)
        for ent in entities:
            if ent.get("match_lista_cav") is True:
                rows.append({
                    "file": file_name,
                    "nome": ent.get("nome", ""),
                    "comune": ent.get("comune", ""),
                    "tipo": ent.get("tipo", ""),
                    "match_lista_cav_nome": ent.get("match_lista_cav_nome", ""),
                    "match_lista_cav_score": ent.get("match_lista_cav_score", 0),
                    "tipo_precedente": ent.get("tipo_precedente", ""),
                    "tipo_fonte_aggiornamento": ent.get("tipo_fonte_aggiornamento", ""),
                    "codice_regione_cav": ent.get("codice_regione_cav", ""),
                    "codice_provincia_cav": ent.get("codice_provincia_cav", ""),
                    "codice_comune_cav": ent.get("codice_comune_cav", ""),
                })

    df_cav_debug = pd.DataFrame(rows)
    print("Match lista CAV trovati:", len(df_cav_debug))
    print(df_cav_debug.head(100).to_string())

    # --- Debug termini specifici ---
    CHECK_TERMS = ["duna", "sabine", "olympia", "lunigiana", "pronto", "centro antiviolenza"]

    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    for file_item in data:
        nome_file = file_item.get("file", "")
        for ent in get_entities_list_ref(file_item):
            nome = ent.get("nome", "")
            nome_norm = _norm_nome(nome)
            if any(t in nome_norm for t in CHECK_TERMS):
                print("\n" + "=" * 100)
                print("FILE:", nome_file)
                print(json.dumps(ent, indent=2, ensure_ascii=False))