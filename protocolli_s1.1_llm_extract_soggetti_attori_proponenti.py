# protocolli_s1.1_llm_extract_soggetti_attori_proponenti.py

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

TXT_FOLDER = "data/txt/"
JSON_STEP1_FOLDER = "output/json/step_1/"

# =========================================================
# SETUP
# =========================================================

load_dotenv()
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

if not API_KEY:
    raise ValueError("Missing AZURE_OPENAI_API_KEY")
if not ENDPOINT:
    raise ValueError("Missing AZURE_OPENAI_ENDPOINT")
if not DEPLOYMENT:
    raise ValueError("Missing AZURE_OPENAI_DEPLOYMENT")

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant. Be concise and precise."

# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = (
    "Sei un estrattore di informazioni strutturate da testi. "
    "Rispondi esclusivamente con un oggetto JSON valido. "
    "Non aggiungere testo, spiegazioni, markdown o commenti. "
    "Non inventare dati non presenti nel testo. "
    "Se l'informazione non è presente, restituisci valori vuoti coerenti con il formato richiesto."
)

# =========================================================
# USER INSTRUCTIONS - STEP 1
# =========================================================

USER_INSTRUCTIONS_STEP1 = """Analizza il testo ed estrai:

1) i firmatari del protocollo
2) tutti i soggetti (enti) citati nel testo

Output:
{
  "firmatari": [],
  "soggetti": []
}

DEFINIZIONI:

Firmatari:
- enti che sottoscrivono formalmente il protocollo

Soggetti:
- tutti gli enti pubblici e privati citati nel testo
  (istituzioni, servizi, associazioni, centri, sportelli, consorzi, ASL, enti territoriali, ecc.),
  indipendentemente dal ruolo

--------------------------------
REGOLE FIRMATARI (ALTA PRIORITÀ)
--------------------------------

- Cerca soprattutto nelle sezioni iniziali e finali del documento
- Indizi tipici:
  - "TRA"
  - "E"
  - elenco formale di enti
  - "sottoscrivono"
  - "stipulano"
  - "aderiscono"
  - "Letto, approvato e sottoscritto"

- Includi tutti gli enti esplicitamente elencati come parti del protocollo

- Se nel testo è presente un elenco esplicito di Comuni firmatari, estrai OGNI Comune come firmatario separato

- NON includere:
  - enti solo citati nel testo
  - enti coinvolti ma non firmatari
  - enti menzionati solo come collaboratori o destinatari

- Se non chiaramente identificabili → restituisci:
  "firmatari": []

--------------------------------
REGOLE SOGGETTI (ESTRAZIONE)
--------------------------------

- Estrai tutti gli enti nominati esplicitamente nel testo

- Includi:
  - Comuni
  - Regioni
  - Province / Città metropolitane
  - ASL / Aziende sanitarie / Consultori
  - Prefetture
  - Questure
  - Forze dell'ordine
  - Tribunali / Procure
  - Scuole / Uffici scolastici / Università
  - Centri antiviolenza
  - Sportelli
  - Case rifugio
  - Associazioni / ETS
  - Consorzi
  - Servizi sociali
  - Servizi educativi
  - Organismi di parità
  - altri enti istituzionali o organizzativi

- NON includere:
  - persone fisiche
  - nomi di leggi o normative
  - concetti astratti
  - ruoli senza ente (es. "il responsabile", "l'operatore", "la referente")

--------------------------------
FORMATO SOGGETTI (OBBLIGATORIO)
--------------------------------

Ogni soggetto deve essere un oggetto con ESATTAMENTE questi campi:

{
  "nome": "",
  "tipo": "",
  "comune": "",
  "indirizzo": "",
  "ente_capofila": "",
  "note": ""
}

Regole campi:
- "nome": nome completo come appare nel testo
- "tipo": uno dei valori ammessi sotto
- "comune": valorizza SOLO se esplicitamente presente nel testo come toponimo o come "Comune di <X>"
- "indirizzo": valorizza SOLO se esplicitamente presente (via, piazza, numero civico, sede)
- "ente_capofila": valorizza SOLO se il testo indica esplicitamente "ente capofila", "capofila", "soggetto capofila", "ente gestore" o equivalente
- "note": altre informazioni utili presenti nel testo sul soggetto (es. ruolo nel protocollo, funzione, eventuale qualifica operativa)

--------------------------------
TIPOLOGIA (VOCABOLARIO CHIUSO)
--------------------------------

Usa SOLO questi valori:

- CAV/Centri Antiviolenza
- Case Rifugio
- Centri/Sportelli di ascolto
- Comuni
- Polizia Municipale
- Settore educativo comunale
- Servizi sociali comunali
- Servizio abusi e maltrattamenti comunale
- Province/Città metropolitane
- Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)
- Regioni/Province Autonome
- Ospedale (Pronto soccorso, ecc.)
- ASL (consultori familiari e altri servizi territoriali)
- Prefettura
- Questura
- Carabinieri/Polizia/altre forze dell'ordine
- Scuole/Ufficio scolastico provinciale e regionale
- Procura Minorile/Tribunale minorile
- Procura Ordinaria/Tribunale/Corte d'appello
- Ordine avvocati
- Ordine psicologi e Ordine assistenti sociali
- Ordine medici e odontoiatri e Ordine farmacisti
- Altri ordini professionali
- Organismi di parità
- Ente terzo settore - ETS (iscritto al RUNTS)
- Ente terzo settore - ETS (iscritto al RUNTS) costituito da donne per le donne
- Servizi per l'impiego
- Sindacati/Associazioni di categoria
- Università
- Associazioni che si occupano di programmi di prevenzione, recupero e trattamento per uomini maltrattanti
- Altro

--------------------------------
REGOLE TIPO (ORDINE GERARCHICO OBBLIGATORIO)
--------------------------------

Applica queste regole in QUESTO ORDINE:

- Se appare "Centro antiviolenza" o "CAV" → tipo = "CAV/Centri Antiviolenza"
- Se appare "Casa rifugio" → tipo = "Case Rifugio"
- Se appare "Centro di ascolto" o "Sportello di ascolto":
  - se il nome o il contesto contengono riferimenti espliciti a violenza, donne, maltrattamenti, vittime, protezione, ascolto donne, centro antiviolenza, CAV → tipo = "CAV/Centri Antiviolenza"
  - altrimenti se il testo indica esplicitamente che si tratta di un'associazione, cooperativa, organizzazione o ETS → tipo = "Ente terzo settore - ETS (iscritto al RUNTS)"
  - altrimenti → tipo = "Centri di ascolto"
- Se appare "Comune di " → tipo = "Comuni"
- Se appare "Polizia Municipale" → tipo = "Polizia Municipale"
- Se appare "Settore educativo" o "Servizio educativo comunale" → tipo = "Settore educativo comunale"
- Se appare "Servizi sociali comunali" o "Servizio sociale comunale" → tipo = "Servizi sociali comunali"
- Se appare "Servizio abusi e maltrattamenti" → tipo = "Servizio abusi e maltrattamenti comunale"
- Se appare "Provincia" o "Città Metropolitana" → tipo = "Province/Città metropolitane"
- Se appare "Ambito sociale", "Piano di Zona", "Distretto socio-sanitario", "Società della Salute" → tipo = "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)"
- Se appare "Regione " → tipo = "Regioni/Province Autonome"
- Se appare "Ospedale" o "Pronto Soccorso" → tipo = "Ospedale (Pronto soccorso, ecc.)"
- Se appare "ASL", "AUSL", "Azienda sanitaria", "Consultorio" → tipo = "ASL (consultori familiari e altri servizi territoriali)"
- Se appare "Prefettura" → tipo = "Prefettura"
- Se appare "Questura" → tipo = "Questura"
- Se appare "Carabinieri", "Polizia di Stato", "Guardia di Finanza", "Forze dell'ordine" → tipo = "Carabinieri/Polizia/altre forze dell'ordine"
- Se appare "Scuola", "Istituto scolastico", "Ufficio scolastico provinciale", "Ufficio scolastico regionale" → tipo = "Scuole/Ufficio scolastico provinciale e regionale"
- Se appare "Procura Minorile" o "Tribunale per i minorenni" → tipo = "Procura Minorile/Tribunale minorile"
- Se appare "Procura della Repubblica", "Tribunale", "Corte d'appello" → tipo = "Procura Ordinaria/Tribunale/Corte d'appello"
- Se appare "Ordine degli Avvocati" → tipo = "Ordine avvocati"
- Se appare "Ordine degli Psicologi" o "Ordine degli Assistenti Sociali" → tipo = "Ordine psicologi e Ordine assistenti sociali"
- Se appare "Ordine dei Medici", "Ordine degli Odontoiatri", "Ordine dei Farmacisti" → tipo = "Ordine medici e odontoiatri e Ordine farmacisti"
- Se appare "Ordine degli Infermieri", "Ordine delle Ostetriche", "Ordine dei Giornalisti", "Ordine dei Commercialisti" o altri ordini professionali espliciti non ricompresi sopra → tipo = "Altri ordini professionali"
- Se appare "Consigliera di parità", "Organismo di parità", "Consulta per le pari opportunità" → tipo = "Organismi di parità"
- Se appare "Centro per l'impiego" o "Servizio per l'impiego" → tipo = "Servizi per l'impiego"
- Se appare "CGIL", "CISL", "UIL", "SUNIA", "SICET", "Unione Inquilini", "Confartigianato", "Confcommercio" o altre organizzazioni sindacali/categoria esplicite → tipo = "Sindacati/Associazioni di categoria"
- Se appare "Università" o "Ateneo" → tipo = "Università"
- Se appare esplicitamente che l'ente si occupa di programmi di recupero o trattamento per uomini maltrattanti → tipo = "Associazioni che si occupano di programmi di prevenzione, recupero e trattamento per uomini maltrattanti"
- Se è presente un array JSON opzionale 'runts_matches' e per quell'ente "match_esatto": true, e NON si applica nessuna regola più specifica sopra → tipo = "Ente terzo settore - ETS (iscritto al RUNTS)"
- Se è presente un array JSON opzionale 'runts_matches' e per quell'ente "match_esatto": true, ed è esplicitamente indicato che è "costituito da donne per le donne" → tipo = "Ente terzo settore - ETS (iscritto al RUNTS) costituito da donne per le donne"
- In tutti gli altri casi → tipo = "Altro"

--------------------------------
COMUNI: MODALITÀ COMPLETA (OBBLIGATORIA)
--------------------------------

- Se nel testo è presente un elenco esplicito di Comuni (es. elenco puntato o separato da virgole), estrai OGNI Comune come entità separata
- Non creare entità aggregate tipo "Comuni dell'area metropolitana"
- Se appare la forma "Comune di <X>" → crea un record con:
    nome = "Comune di <X>"
    tipo = "Comuni"
    comune = "<X>"
- Se un Comune è citato senza la formula "Comune di", ma è chiaramente un ente territoriale firmatario o parte formale dell'accordo, estrailo comunque come record separato con tipo "Comuni"

--------------------------------
RUNTS (SOLO SE FORNITO)
--------------------------------

- Può essere fornito un array JSON 'runts_matches'
- Puoi usare dati RUNTS SOLO se per quella voce "match_esatto": true
- Se "match_esatto": false o assente → non usare RUNTS
- Non creare nuovi match
- Non stimare similarità
- NO fuzzy matching in questa fase

--------------------------------
REGOLE ANTI-ERRORI / ANTI-HALLUCINATION
--------------------------------

- Non inventare dati
- Se un campo non è esplicitamente presente → usa ""
- Non dedurre il comune dal nome dell'ente
- Non dedurre indirizzi o sedi
- Non inferire che un ente sia firmatario solo perché compare spesso nel testo
- Non usare sinonimi non presenti nel vocabolario chiuso
- Se il tipo non è chiaro → usa "Altro"
- Mantieni il nome esattamente come nel testo

--------------------------------
DEDUPLICAZIONE
--------------------------------

- Non duplicare soggetti
- Se lo stesso ente appare più volte → inseriscilo una sola volta
- Unisci duplicati evidenti (ma senza normalizzazioni arbitrarie)
- Se lo stesso ente ha più ruoli, usa un solo record e descrivi i ruoli in "note"

--------------------------------
OUTPUT
--------------------------------

- Restituisci SOLO JSON valido
- Nessun testo extra
- Nessun markdown
- Nessun commento

Struttura finale:

{
  "firmatari": [],
  "soggetti": []
}

Testo:
"""

# =========================================================
# USER INSTRUCTIONS - STEP 2
# =========================================================

USER_INSTRUCTIONS_STEP2_PROP = """Hai a disposizione:

1) il testo del protocollo
2) la lista dei soggetti già estratti

Devi identificare i soggetti proponenti.

Output:
{
  "soggetti_proponenti": []
}

DEFINIZIONE:

- I soggetti proponenti sono gli enti che promuovono, avviano o danno impulso
  alla creazione del protocollo.

--------------------------------
REGOLE PRINCIPALI
--------------------------------

- Puoi selezionare SOLO soggetti presenti nella lista fornita
- NON inventare nuovi enti
- NON usare varianti del nome

--------------------------------
INDIZI FORTI (ALTA PRIORITÀ)
--------------------------------

- "promosso da"
- "promosso congiuntamente da"
- "proposto da"
- "su iniziativa di"
- "ente promotore"
- "soggetti promotori"
- "ha promosso"
- "ha avviato"

--------------------------------
INDIZI MEDI (USA SOLO SE CHIARO)
--------------------------------

- "intendono promuovere"
- "hanno dato impulso"
- "attivano il protocollo"

--------------------------------
ATTENZIONE (ERRORI DA EVITARE)
--------------------------------

NON considerare automaticamente proponenti:

- firmatari
- capofila
- coordinatori
- soggetti coinvolti
- enti che partecipano o collaborano

Frasi come:
- "convengono"
- "sottoscrivono"
- "aderiscono"

NON indicano proponenti.

--------------------------------
REGOLE DI SICUREZZA
--------------------------------

- Se NON è esplicitamente chiaro → restituisci []
- Meglio vuoto che sbagliato

--------------------------------
OUTPUT
--------------------------------

- Solo JSON valido
- Nessun testo extra

Testo:
{sorgente_testo}

Soggetti disponibili:
{soggetti_estratti}
"""

# =========================================================
# USER INSTRUCTIONS - STEP 3
# =========================================================

USER_INSTRUCTIONS_STEP3_ATTORI = """Hai a disposizione:

1) il testo del protocollo
2) la lista dei soggetti già estratti

Devi identificare gli attori coinvolti.

Output:
{
  "attori_coinvolti": []
}

DEFINIZIONE:

- Gli attori coinvolti sono gli enti che partecipano operativamente
  alla rete o al protocollo (servizi, supporto, interventi, presa in carico).

--------------------------------
REGOLE PRINCIPALI
--------------------------------

- Puoi selezionare SOLO soggetti presenti nella lista fornita
- NON inventare nuovi enti

--------------------------------
INDIZI FORTI
--------------------------------

- "attori coinvolti"
- "soggetti coinvolti"
- "componenti della rete"
- "enti partecipanti"
- "aderiscono"
- "partecipano"
- "collaborano"
- "in collaborazione con"
- "in rete con"

--------------------------------
INDIZI OPERATIVI (IMPORTANTI)
--------------------------------

- "presa in carico"
- "supportano"
- "intervengono"
- "gestiscono"
- "erogano servizi"
- "attivano servizi"
- "invio ai servizi"
- "percorsi di protezione"

--------------------------------
REGOLE IMPORTANTI
--------------------------------

- Gli attori possono includere anche i proponenti SE hanno ruolo operativo
- Non includere soggetti solo nominati senza ruolo

--------------------------------
ATTENZIONE
--------------------------------

NON includere:

- enti citati solo in contesto normativo
- enti nominati una sola volta senza ruolo
- enti astratti o generici

--------------------------------
REGOLE DI SICUREZZA
--------------------------------

- Se non è chiaro → escludi
- Meglio pochi attori che molti sbagliati

--------------------------------
OUTPUT
--------------------------------

- Solo JSON valido
- Nessun testo extra

Testo:
{sorgente_testo}

Soggetti disponibili:
{soggetti_estratti}
"""


from region_config import get_reg_code, print_reg_code, build_region_file

reg_code = get_reg_code(default="09", required=True)
print_reg_code(reg_code)

TXT_FOLDER = "data/txt"

OUTPUT_JSON = build_region_file("output/json/step_1", reg_code, "risultati.json")

# =========================================================
# HELPERS
# =========================================================

def clean_list(lst):
    if not isinstance(lst, list):
        return []
    seen = set()
    out = []
    for x in lst:
        if isinstance(x, str):
            v = x.strip()
            if v and v not in seen:
                seen.add(v)
                out.append(v)
    return out


def call_llm(prompt):
    resp = client.responses.create(
        model=DEPLOYMENT,
        top_p=1,
        instructions=SYSTEM_PROMPT,
        input=prompt
    )
    return json.loads(resp.output_text)


# =========================================================
# STEP 1 -> firmatari + soggetti
# =========================================================

def extract_step1(testi):
    risultati = []

    for idx, item in enumerate(testi, start=1):
        print(f"STEP 1 [{idx}/{len(testi)}] {item['nome_file']}")
        try:
            prompt = USER_INSTRUCTIONS_STEP1 + "\n" + item["contenuto"] + "\n---"
            data = call_llm(prompt)

            risultati.append({
                "file": item["nome_file"],
                "risultato": {
                    "firmatari": clean_list(data.get("firmatari", [])),
                    "soggetti": data.get("soggetti", []) if isinstance(data.get("soggetti", []), list) else []
                }
            })

        except Exception as e:
            print(f"❌ Errore STEP 1 con {item['nome_file']}: {e}")
            risultati.append({
                "file": item["nome_file"],
                "risultato": {
                    "firmatari": [],
                    "soggetti": []
                }
            })

    return risultati


# =========================================================
# STEP 2 -> soggetti proponenti
# =========================================================

def extract_step2(testi, risultati_step1):
    risultati = []

    for idx, (item, r1) in enumerate(zip(testi, risultati_step1), start=1):
        print(f"STEP 2 [{idx}/{len(testi)}] {item['nome_file']}")
        try:
            soggetti = r1.get("risultato", {}).get("soggetti", [])
            soggetti_str = json.dumps(soggetti, ensure_ascii=False)

            prompt = USER_INSTRUCTIONS_STEP2_PROP \
                .replace("{sorgente_testo}", item["contenuto"]) \
                .replace("{soggetti_estratti}", soggetti_str)

            data = call_llm(prompt)

            risultati.append({
                "file": item["nome_file"],
                "risultato": {
                    "soggetti_proponenti": clean_list(data.get("soggetti_proponenti", []))
                }
            })

        except Exception as e:
            print(f"❌ Errore STEP 2 con {item['nome_file']}: {e}")
            risultati.append({
                "file": item["nome_file"],
                "risultato": {
                    "soggetti_proponenti": []
                }
            })

    return risultati


# =========================================================
# STEP 3 -> attori coinvolti
# =========================================================

def extract_step3(testi, risultati_step1):
    risultati = []

    for idx, (item, r1) in enumerate(zip(testi, risultati_step1), start=1):
        print(f"STEP 3 [{idx}/{len(testi)}] {item['nome_file']}")
        try:
            soggetti = r1.get("risultato", {}).get("soggetti", [])
            soggetti_str = json.dumps(soggetti, ensure_ascii=False)

            prompt = USER_INSTRUCTIONS_STEP3_ATTORI \
                .replace("{sorgente_testo}", item["contenuto"]) \
                .replace("{soggetti_estratti}", soggetti_str)

            data = call_llm(prompt)

            risultati.append({
                "file": item["nome_file"],
                "risultato": {
                    "attori_coinvolti": clean_list(data.get("attori_coinvolti", []))
                }
            })

        except Exception as e:
            print(f"❌ Errore STEP 3 con {item['nome_file']}: {e}")
            risultati.append({
                "file": item["nome_file"],
                "risultato": {
                    "attori_coinvolti": []
                }
            })

    return risultati


# =========================================================
# MERGE singolo file
# =========================================================

def merge_file_results(item, step1_result=None, step2_result=None, step3_result=None):
    data1 = step1_result.get("risultato", {}) if step1_result else {}
    data2 = step2_result.get("risultato", {}) if step2_result else {}
    data3 = step3_result.get("risultato", {}) if step3_result else {}

    return {
        "file": item["nome_file"],
        "firmatari": clean_list(data1.get("firmatari", [])),
        "soggetti": data1.get("soggetti", []) if isinstance(data1.get("soggetti", []), list) else [],
        "soggetti_proponenti": clean_list(data2.get("soggetti_proponenti", [])),
        "attori_coinvolti": clean_list(data3.get("attori_coinvolti", []))
    }


# =========================================================
# MERGE di tutti i file
# =========================================================

def merge_all_results(testi, risultati_1, risultati_2, risultati_3):
    merged_results = []

    for item, r1, r2, r3 in zip(testi, risultati_1, risultati_2, risultati_3):
        merged = merge_file_results(
            item,
            step1_result=r1,
            step2_result=r2,
            step3_result=r3
        )
        merged_results.append(merged)

    return merged_results


# =========================================================
# FILE LOADING
# =========================================================

file_target = {
    "09_APUANE_2015 Protocollo Prefettura.txt",
    "09_ALTA VALDELSA Protocollo-violenza-valdelsa-2022_ALTA VALDELSA.txt",
    "09_AREZZO Prot_2024-2026.txt",
    "09_FIRENZE Linee-di-indirizzo2024.txt",
    "09_GROSSETO 2022 fpdf.txt",
    "09_LIVORNO Protocollo_ RETE ANTIVIOLENZA_ LIVORNO.txt",
    "09_LUCCA PROV.txt",
    "09_PRATO PREF.txt",
    "09_PISTOIA PROV .txt",
    "09_PISA PREF E PROV.txt",
    "09_SENESE Delibera-n.1196-del-24-10-2022-allegato-a_SENESE_2.txt",
    "09_VALDICHIANA_all. decreto 37_2008 protocollo di intesa 2008.txt",
}


def _uploadfile(reg_code):
    cartella_txt = f"{TXT_FOLDER}/{reg_code:02d}"
    print(f"📂 Caricamento file dalla cartella: {cartella_txt}")

    if not os.path.exists(cartella_txt):
        print(f"⚠️ Cartella non trovata: {cartella_txt}")
        return []

    testi = []

    file_txt = sorted([
        f for f in os.listdir(cartella_txt)
        if f.endswith(".txt") and f in file_target
    ])

    for nome_file in file_txt:
        percorso = os.path.join(cartella_txt, nome_file)
        with open(percorso, "r", encoding="utf-8") as f:
            testo = f.read()
            testi.append({
                "nome_file": nome_file,
                "contenuto": testo
            })

    presenti = set(file_txt)
    mancanti = sorted(file_target - presenti)

    print(f"📂 Regione {reg_code:02d}: caricati {len(testi)} file di testo selezionati.")

    if mancanti:
        print("⚠️ File target mancanti:")
        for f in mancanti:
            print(" -", f)

    return testi
    
def uploadfile(reg_code):

    cartella_txt = f"{TXT_FOLDER}/{reg_code:02d}" 
    print(f"📂 Caricamento file dalla cartella: {cartella_txt}" )
    testi = []    
    file_txt = [f for f in os.listdir(cartella_txt) if f.endswith(".txt")] 
    for nome_file in file_txt: 
        percorso = os.path.join(cartella_txt, nome_file)
       
        with open(percorso, "r", encoding="utf-8") as f: 
            testo = f.read() 
            testi.append({
                "nome_file": nome_file, 
                "contenuto": testo
            }) 

    print(f"📂 Regione {reg_code:02d}: caricati {len(testi)} file di testo.")        
    return testi  


# =========================================================
# OUTPUT
# =========================================================

def print_result(risultati, reg_code):
    output_dir = f"{JSON_STEP1_FOLDER}"
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"{reg_code:02d}_risultati.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(risultati, f, indent=4, ensure_ascii=False)

    print(f"✅ Risultati salvati in: {output_file}")

# =========================================================
# MAIN
# =========================================================
import argparse
import json

def parse_region_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reg_code", type=str, default=None, help="Codice regione singolo, es. 09")
    parser.add_argument("--start_reg", type=str, default=None, help="Codice regione iniziale, es. 09")
    parser.add_argument("--end_reg", type=str, default=None, help="Codice regione finale, es. 13")
    args = parser.parse_args()

    if args.reg_code is not None:
        reg = int(str(args.reg_code).zfill(2))
        return reg, reg

    start_reg = int(str(args.start_reg).zfill(2)) if args.start_reg is not None else 9
    end_reg = int(str(args.end_reg).zfill(2)) if args.end_reg is not None else start_reg

    return start_reg, end_reg


if __name__ == "__main__":
    start_reg, end_reg = parse_region_args()

    for reg_code in range(start_reg, end_reg + 1):
        print(f"\n================ REGIONE {reg_code:02d} ================\n")

        testi = uploadfile(reg_code)

        risultati_1 = extract_step1(testi)
        risultati_2 = extract_step2(testi, risultati_1)
        risultati_3 = extract_step3(testi, risultati_1)

        merged_result = merge_all_results(
            testi,
            risultati_1,
            risultati_2,
            risultati_3
        )

        print(json.dumps(merged_result[:2], indent=4, ensure_ascii=False))
        print_result(merged_result, reg_code)



# =========================================================
# MAIN
# =========================================================


#if __name__ == "__main__":
#    start_reg = 9
#    end_reg = 9

#    for reg_code in range(start_reg, end_reg + 1):
#        print(f"\n================ REGIONE {reg_code} ================\n")

#        testi = uploadfile(reg_code)

#        risultati_1 = extract_step1(testi)
#        risultati_2 = extract_step2(testi, risultati_1)
#        risultati_3 = extract_step3(testi, risultati_1)

#        merged_result = merge_all_results(
#           testi,
#            risultati_1,
#            risultati_2,
#           risultati_3
#        )

#        print(json.dumps(merged_result[:2], indent=4, ensure_ascii=False))
#        print_result(merged_result, reg_code)
