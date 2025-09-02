# Script per estrarre righe che terminano con ': [],'

input_path = 'output/comuni_out_tmp.json'
output_path = 'output/righe_vuote.txt'

with open(input_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Seleziona solo le righe che finiscono con ": [],"
righe_vuote = [line.strip() for line in lines if line.strip().endswith(': [],')]

# Salva su file
with open(output_path, 'w', encoding='utf-8') as f_out:
    for riga in righe_vuote:
        f_out.write(riga + '\n')

print(f"{len(righe_vuote)} righe trovate e salvate in '{output_path}'")