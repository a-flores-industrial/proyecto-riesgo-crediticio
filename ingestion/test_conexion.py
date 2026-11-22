import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()
conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")

# Python -> SQL
df = pd.DataFrame({"mensaje": ["hola desde python"], "fecha": [pd.Timestamp.now()]})
df.to_sql("prueba", engine, schema="raw", if_exists="replace", index=False)

# SQL -> Python
print(pd.read_sql("SELECT * FROM raw.prueba", engine))