import pandas as pd

# Carica il file ISTAT grezzo (usa il delimitatore corretto)
df = pd.read_csv("elenco comuni.csv", delimiter=';', encoding='latin1') 

# Estrai solo le colonne che ci servono
df_out = df[[
    'Codice Comune formato numerico',
    'Denominazione in italiano',
    'Denominazione Regione'
]].copy()

# Rinomina le colonne per il nostro uso
df_out.columns = ['codice_comune', 'nome_comune', 'regione']

# Rimuovi comuni senza codice (non dovrebbero esserci, ma per sicurezza)
df_out = df_out.dropna(subset=["codice_comune", "nome_comune", "regione"])

# Salva in CSV
df_out.to_csv("comuni_regione.csv", index=False)
print("✅ File 'comuni_regione.csv' generato correttamente.")