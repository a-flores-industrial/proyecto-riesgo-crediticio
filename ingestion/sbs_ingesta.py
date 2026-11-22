import os
import time
import warnings
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.types import UnicodeText

warnings.filterwarnings("ignore")
load_dotenv()

# --- Conexión a SQL Server ---
conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")

# --- Configuración ---
ANIO_INICIO = 2015
BASE = "https://intranet2.sbs.gob.pe/estadistica/financiera"
CARPETA = Path("data/raw/sbs")
HEADERS = {"User-Agent": "Mozilla/5.0"}
XLS_MAGIC = b"\xd0\xcf\x11\xe0"   # firma de un Excel .xls real

CODIGOS = {
    "B-2362": "Banca Multiple",
    "C-4234": "Empresas de Creditos",
    "C-2247": "Cajas Rurales",
    "C-1242": "Cajas Municipales",
}

# (nombre de carpeta, abreviaturas candidatas). Las confirmadas: en, fe, ma, my, jn, jl, se
MESES = [
    ("Enero", ["en"]), ("Febrero", ["fe"]), ("Marzo", ["ma"]),
    ("Abril", ["ab", "al"]), ("Mayo", ["my"]), ("Junio", ["jn"]),
    ("Julio", ["jl"]), ("Agosto", ["ag", "au"]), ("Setiembre", ["se"]),
    ("Octubre", ["oc", "ot"]), ("Noviembre", ["no", "nv"]), ("Diciembre", ["di", "dc"]),
]


def obtener_archivo(codigo, anio, mes):
    """Devuelve la ruta local del archivo (lo descarga si hace falta) o None si no existe."""
    carpeta_mes, abreviaturas = MESES[mes - 1]
    for abrev in abreviaturas:
        nombre = f"{codigo}-{abrev}{anio}.XLS"
        ruta = CARPETA / codigo / str(anio) / nombre
        if ruta.exists():
            return ruta
        url = f"{BASE}/{anio}/{carpeta_mes}/{nombre}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
        except requests.RequestException:
            continue
        time.sleep(0.3)  # pausa de cortesía
        if r.status_code == 200 and r.content.startswith(XLS_MAGIC):
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(r.content)
            return ruta
    return None


def leer_archivo(ruta, codigo, anio, mes):
    """Lee todas las hojas como texto, sin interpretar nada."""
    hojas = pd.read_excel(ruta, sheet_name=None, header=None, dtype=str)
    tablas = []
    for hoja, df in hojas.items():
        df = df.copy()
        df.columns = [f"col_{i:02d}" for i in range(df.shape[1])]
        df.insert(0, "nro_fila", range(1, len(df) + 1))
        columnas_datos = [c for c in df.columns if c.startswith("col_")]
        df = df.dropna(subset=columnas_datos, how="all")   # fuera filas totalmente vacías
        df.insert(0, "hoja", str(hoja))
        df.insert(0, "archivo", ruta.name)
        df.insert(0, "mes", mes)
        df.insert(0, "anio", anio)
        df.insert(0, "codigo_cuadro", codigo)
        tablas.append(df)
    return pd.concat(tablas, ignore_index=True)


def main():
    hoy = date.today()
    tablas = []
    for codigo, entidad in CODIGOS.items():
        faltantes = []
        encontrados = 0
        for anio in range(ANIO_INICIO, hoy.year + 1):
            for mes in range(1, 13):
                if (anio, mes) > (hoy.year, hoy.month):
                    break
                ruta = obtener_archivo(codigo, anio, mes)
                if ruta is None:
                    faltantes.append(f"{anio}-{mes:02d}")
                    continue
                tablas.append(leer_archivo(ruta, codigo, anio, mes))
                encontrados += 1
        print(f"{codigo} ({entidad}): {encontrados} archivos | faltantes: {faltantes}")

    df = pd.concat(tablas, ignore_index=True)
    df["fecha_carga"] = pd.Timestamp.now()

    tipos_texto = {
        c: UnicodeText()
        for c in df.columns
        if c.startswith("col_") or c in ("codigo_cuadro", "archivo", "hoja")
    }
    df.to_sql("sbs_morosidad", engine, schema="raw", if_exists="replace",
              index=False, dtype=tipos_texto)
    print(f"\nCargadas {len(df)} filas en raw.sbs_morosidad")


if __name__ == "__main__":
    main()