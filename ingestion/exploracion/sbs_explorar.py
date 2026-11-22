import pandas as pd

xls = pd.ExcelFile("data/raw/sbs/C-1242/2026/C-1242-en2026.XLS")
for hoja in xls.sheet_names:
    df = xls.parse(hoja, header=None)
    titulo = df.iloc[0:3, 1].dropna().tolist()   # los títulos del reporte
    print(f"{hoja:<12} filas={df.shape[0]:<4} columnas={df.shape[1]:<4} {titulo[:1]}")