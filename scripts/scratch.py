import csv, re
from pathlib import Path
f = open('data/data_cuestionarios_43.csv', 'r', encoding='utf-8-sig')
headers = list(csv.reader(f))[0][5:21]
f.close()
h_fmt = ',\n    '.join([f'"{h.strip()}"' for h in headers])
p = Path('src/studify/web/textos.py')
txt = p.read_text(encoding='utf-8')
txt = re.sub(r'(ENUNCIADOS: tuple\[str, \.\.\.\] = \(\n)[^)]+(\n\))', rf'\g<1>    {h_fmt}\g<2>', txt)
p.write_text(txt, encoding='utf-8')
print('Updated textos.py')
