import os
import re
import json
import csv
from proto_vio_lib import unifica_nome, deduplica_associazioni, deduplica_consorzi, deduplica_comuni 

# === GRUPPI DI REGEX ORGANIZZATI ===
PATTERNS = {
    "comuni": [
        r"\bComune\s+di\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\- ]+)",
        r"\bC\.\s*COMUNE\s+([A-ZÀ-Ú'][A-ZÀ-Ú'\s\-]+)",
        r"\bComuni\s+della\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)",
        r"\bComuni\s+del\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)",
        r"Comune di\s+([A-ZÀ-Ú][A-Za-zà-ù'\s-]+(?:[A-Za-zà-ù'\s-]+)*)",
        r"Comuni della\s+([A-ZÀ-Ú][A-Za-zà-ù'\s-]+(?:[A-Za-zà-ù'\s-]+)*)",
        r"Comuni del\s+([A-ZÀ-Ú][A-Za-zà-ù'\s-]+(?:[A-Za-zà-ù'\s-]+)*)",
    ],
    "unioni_montane": [
        r"Unione Montana\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)"
    ], 
    "comunita_montane": [
        r"Comunità Montana\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)"
    ],    
    "unioni": [
        r"\bUnioni?\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)"
    ],
    "zona_distretto": [
        r"\bZona\s+Distretto\s+([A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+(?:\s+e\s+[A-ZÀ-Ú][\w'à-ùÀ-Ú\s\-]+)*)"
    ],
    "province": [
        r"(?:Provincia|Provincia di)\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)"
    ],
    "regioni": [
        r"(?:Regione|Regione Autonoma)\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)"
    ],
    "consorzi": [
        r"\b([A-Z\.]{2,})\s*\(\s*(Consorzio.*?)\)",
        r"Consorzio.*di\s+([A-Za-zÀ-Úà-ù'\s-]+)",
        r"Consorzio.*di\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)",
        r"Consorzio.*di\s+([A-ZÀ-Ú][A-Za-zà-ù'\s-]+(?:[A-Za-zà-ù'\s-]+)*)",
        r"\bConsorzio\s+(Intercomunale)?\s?(Servizi\s+[A-Za-zà-ù\s]+)?(del[l']?\s+)?([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\s\-]+)?",
        r'\b(?:Consorzio)\b(?:\s[\w/.,’“”"\'-]+){0,12}',
    ],
    "enti_pubblici": [
        r"\b(Prefettura|Tribunale|Procura|Questura|Comando Provinciale Carabinieri|Guardia Finanza|"
        r"Azienda Sanitaria Locale|Ordine [A-Za-z]+|Ufficio Scolastico Provinciale|"
        r"Consigliera Parita|Referente Nodo provinciale discriminazioni|Ufficio Esecuzione Penale Esterna)"
        r"\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\- ]+)"
    ],
    "universita": [
        r"Universit[aà]\s+degli\s+Studi\s+di\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\- ]+)(?:.*?Polo\s+di\s+([A-ZÀ-Ú][a-zà-ùA-ZÀ-Ú'\- ]+))?"
    ],
    "associazioni": [       
        #r'\b[Aa]ssociazion[ei]?\b(?:[\s\w*&+/.,’“”"\'-]{1,20}){0,6}'
        r'\bAssociazione(?:\s+di\s+\w+)?(?:\s+\w+)?\s+([A-Z][A-Za-z+& ]{2,100})'
    ],
    "generali": [
        r'\b(?:Azienda|Ospedale|Dipartimento|Procura|MIUR|ONLUS|Ministero|Ambito|Ufficio|Tribunale)\b(?:\s[\w/.,’“”"\'-]+){0,12}'
    ]
}

# === FUNZIONE DI NORMALIZZAZIONE ===
def normalize(value):
    value = re.sub(r"\s+", " ", value)
    return value.strip().title()


# === FUNZIONE DI ESTRAZIONE ===
def estrai_enti(text):
    risultati = {k: set() for k in PATTERNS.keys()}

    for categoria, patterns in PATTERNS.items():
        estratti = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    for match in matches:
                        joined = " ".join(normalize(m) for m in match if m)
                        estratti.add(joined)
                else:
                    estratti.update(normalize(m) for m in matches)

        # 🔍 Pulizia post-estrazione
        if categoria == "associazioni":
            puliti = set()
            for nome in estratti:
                nome = re.sub(r"(,?\s+si impegna a.*)$", "", nome, flags=re.IGNORECASE)
                nome = re.sub(r"(,?\s+con\b.*)$", "", nome, flags=re.IGNORECASE)
                nome = re.sub(r"(,?\s+per\b.*)$", "", nome, flags=re.IGNORECASE)
                nome = nome.split(",")[0].strip()
                puliti.add(nome)
            risultati[categoria] = set(deduplica_associazioni(puliti))
        elif categoria == "consorzi":
            risultati[categoria] = set(deduplica_consorzi(estratti))
        elif categoria == "comuni":
            risultati[categoria] = set(deduplica_comuni(estratti))
        elif categoria == "regioni":
            risultati[categoria] = set(deduplica_comuni(estratti))
        else:
            risultati[categoria] = estratti
            


    return {k: sorted(list(v)) for k, v in risultati.items() if v}



# === SCANSIONE FILE E SALVATAGGIO ===
def analizza_cartella(
    fld_inp="input",
    fld_txt="txt", 
    fld_comuni="comuni", 
    fld_runts="runts", 
    fld_out="output", 
    fld_json="json",
    fld_csv="csv"
    ):
    
    path_txt = os.path.join(fld_inp, fld_txt)
    path_comuni = os.path.join(fld_inp, fld_comuni)
    path_runts = os.path.join(fld_inp, fld_runts)
    
    path_json = os.path.join(fld_out, fld_json)
    path_csv = os.path.join(fld_out, fld_csv)

    os.makedirs(fld_out, exist_ok=True)
    os.makedirs(path_json, exist_ok=True)
    os.makedirs(path_csv, exist_ok=True)

    for nome_file in os.listdir(path_txt):
        if nome_file.endswith(".txt"):
            path = os.path.join(path_txt, nome_file)
            with open(path, "r", encoding="utf-8") as f:
                contenuto = f.read().lower()

            risultati = estrai_enti(contenuto)

            file = os.path.splitext(nome_file)[0]
            json_path = os.path.join(path_json, file + ".json")
            csv_path = os.path.join(path_csv, file + ".csv")

            with open(json_path, "w", encoding="utf-8") as f_json:
                json.dump(risultati, f_json, indent=2, ensure_ascii=False)

            with open(csv_path, "w", newline="", encoding="utf-8") as f_csv:
                writer = csv.writer(f_csv)
                writer.writerow(["Categoria", "Nome"])
                for cat, values in risultati.items():
                    for val in values:
                        writer.writerow([cat, val])

# === ESECUZIONE ===
if __name__ == "__main__":
    analizza_cartella("input","txt", "comuni", "runts","output", "json", "csv")