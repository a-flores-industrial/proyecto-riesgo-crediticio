import os
import time
from datetime import date
from urllib.parse import quote_plus

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

# --- Conexión a SQL Server (igual que en la prueba de humo) ---
conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")

# --- Qué series descargar ---
ANIO_INICIO = 2015
SERIES = {
    "PD04637PD": "diaria",    # TC interbancario compra
    "PD04638PD": "diaria",    # TC interbancario venta (verificar nombre al correr)
    "PD04722MM": "mensual",   # Tasa de referencia BCRP
    "PN01271PM": "mensual",   # IPC var% mensual
    "PN01273PM": "mensual",   # IPC var% 12 meses
}
BASE_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"


def periodos(frecuencia):
    hoy = date.today()
    if frecuencia == "diaria":
        return f"{ANIO_INICIO}-1-1", f"{hoy.year}-{hoy.month}-{hoy.day}"
    return f"{ANIO_INICIO}-1", f"{hoy.year}-{hoy.month}"


def descargar_serie(codigo, frecuencia):
    ini, fin = periodos(frecuencia)
    url = f"{BASE_URL}/{codigo}/json/{ini}/{fin}/ing"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    nombre = data["config"]["series"][0]["name"]
    filas = [
        {
            "serie_codigo": codigo,
            "serie_nombre": nombre,
            "frecuencia": frecuencia,
            "periodo": p["name"],        # texto original, ej. "Jan.2023"
            "valor": p["values"][0],     # texto original, puede ser "n.d."
        }
        for p in data["periods"]
    ]
    print(f"{codigo}: {len(filas)} filas | {nombre}")
    return pd.DataFrame(filas)


def main():
    tablas = []
    for codigo, frecuencia in SERIES.items():
        tablas.append(descargar_serie(codigo, frecuencia))
        time.sleep(1)  # pausa de cortesía entre llamadas

    df = pd.concat(tablas, ignore_index=True)
    df["fecha_carga"] = pd.Timestamp.now()

    df.to_sql("bcrp_series", engine, schema="raw", if_exists="replace", index=False)
    print(f"\nCargadas {len(df)} filas en raw.bcrp_series")


if __name__ == "__main__":
    main()