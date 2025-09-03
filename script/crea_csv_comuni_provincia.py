import pandas as pd

# === 1. Carica il file ISTAT ===
df = pd.read_csv("elenco comuni.csv", delimiter=';', encoding='latin1') 

# Estrai solo le colonne che ci servono
df_out = df[[
    'Codice Regione',
	'Denominazione Regione',	
	'Codice Provincia (Storico)(1)',
	'Denominazione dell\'Unità territoriale sovracomunale (valida a fini statistici)',
    'Sigla automobilistica',
	'Codice Comune formato numerico',
    'Denominazione in italiano'    
]].copy()

# Rinomina le colonne per il nostro uso
df_out.columns = ['codice_regione','regione','codice_provincia','provincia','sigla_provincia','codice_comune', 'nome_comune']


# === 3. Raggruppa per provincia ===
df_province = (
    df_out.groupby(['regione','codice_provincia', 'provincia', 'sigla_provincia'])
      .agg(numero_comuni=("codice_comune", "count"))
      .reset_index()
      .sort_values(by=['regione', 'numero_comuni'], ascending=[True, False])
)

# === 4. Salva il CSV ===
df_province.to_csv("comuni_provincia.csv", index=False, encoding="utf-8")

print("✅ File 'comuni_provincia.csv' generato con successo!")
print(df_province.head())