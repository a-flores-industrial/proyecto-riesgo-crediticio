\# Capa raw



Las tablas de esta capa \*\*no se crean con SQL\*\*: las genera Python al cargar los datos

(`ingestion/bcrp\_ingesta.py` → `raw.bcrp\_series`, `ingestion/sbs\_ingesta.py` → `raw.sbs\_morosidad`).

Contienen la copia fiel de lo descargado, todo como texto. La limpieza ocurre en `02\_staging`.

