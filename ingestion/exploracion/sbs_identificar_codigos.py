from io import BytesIO

import pandas as pd
import requests
import warnings
warnings.filterwarnings("ignore")

BASE = "https://intranet2.sbs.gob.pe/estadistica/financiera/2026/Enero/{codigo}-en2026.XLS"
CODIGOS = ["B-2362", "B-3257", "C-4234", "C-2247", "C-1242"]

for codigo in CODIGOS:
    url = BASE.format(codigo=codigo)
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        if r.status_code != 200 or not r.content.startswith(b"\xd0\xcf\x11\xe0"):
            print(f"{codigo}: no disponible (estado {r.status_code})")
            continue
        xls = pd.ExcelFile(BytesIO(r.content))
        for hoja in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=hoja, header=None)
            celdas = [str(v) for v in df.head(3).to_numpy().ravel() if pd.notna(v)]
            print(f"{codigo} | hoja: {hoja} | {celdas[:1]}")
    except Exception as e:
        print(f"{codigo}: error -> {e}")