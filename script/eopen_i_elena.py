import openai

import json
 
openai.api_key = "LA_TUA_API_KEY"
 
def estrai_centri_antiviolenza(testo):

    prompt = f"""

    Estrai tutti i centri antiviolenza citati nel seguente testo.

    Restituisci un JSON con nome, indirizzo, città, telefono, email (metti null se mancante).

    Testo: {testo}

    """

    response = openai.ChatCompletion.create(

        model="gpt-4o",  # o altro LLM

        messages=[{"role": "user", "content": prompt}]

    )

    return json.loads(response.choices[0].message.content)
 
# Esempio

testo = """Casa delle Donne per non subire violenza, via dell’Oro 3 Bologna, tel. 051 333173.

Centro Mai + Sole, via Teatro 2 Savigliano CN, numero 335 1701008."""

print(estrai_centri_antiviolenza(testo))
 
import os

import json

from openai import OpenAI
 
# 🔑 Inserisci la tua API key

client = OpenAI(api_key="LA_TUA_API_KEY")
 
def estrai_centri(testo):

    prompt = f"""

Sei un estrattore di informazioni.

Leggi il testo qui sotto e trova tutti i centri antiviolenza citati.

Per ciascun centro, restituisci un oggetto JSON con queste chiavi:

- nome

- indirizzo

- città

- telefono (solo numeri, senza spazi)

- email (null se assente)

Restituisci SOLO un array JSON valido.

Testo:

{testo}

"""

    response = client.chat.completions.create(

        model="gpt-4o",  # oppure "gpt-4o-mini" per risparmiare token

        messages=[{"role": "user", "content": prompt}],

        temperature=0  # massima precisione

    )

    # Parse JSON restituito dal modello

    return json.loads(response.choices[0].message.content)
 
# 📂 Esempio: lista di testi da elaborare

testi = [

    """Casa delle Donne per non subire violenza, via dell’Oro 3 Bologna, tel. 051 333173, email accoglienzabologna@casadonne.it.""",

    """Centro Mai + Sole, via Teatro 2 Savigliano CN, numero 335 1701008, email info@maipiusole.it."""

]
 
risultati = []

for t in testi:

    risultati.extend(estrai_centri(t))
 
# Salva tutto in un file JSON unico

with open("centri_antiviolenza.json", "w", encoding="utf-8") as f:

    json.dump(risultati, f, ensure_ascii=False, indent=2)
 
print("✅ Estrazione completata! Centri trovati:")

print(json.dumps(risultati, indent=2, ensure_ascii=False))

 