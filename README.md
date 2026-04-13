# Protocolli d'intesa
Questo repository contiene dati, classificazioni e metodi per l'analisi dei protocolli di intesa.




Come procedere: 
In primis si dovrà essere eseguita l'estrazione dei dati dai testi attraverso

lo 
py protocolli_s1.1_llm_extract_soggetti_attori_proponenti.py

uso: 
protocolli_s1.1_llm_extract_soggetti_attori_proponenti.py 

[-h]

Una sola regione:

[--reg_code REG_CODE]  :

Un range:

[--start_reg START_REG]  [--end_reg END_REG]

Una volta concluso il processo di estrazione attraverso LLM si potrà passare alla fase successiva di esecuzione degli script per avviare l'enrichment dei dati estratti:

Una sola regione:

    py run_pipeline_regioni.py --regioni 09

Un range:

    py run_pipeline_regioni.py --regioni 01-05

Una lista:

    py run_pipeline_regioni.py --regioni 01,07,09

Misto:

    py run_pipeline_regioni.py --regioni 01-03,07,09

Tutte:

    py run_pipeline_regioni.py --regioni all




    