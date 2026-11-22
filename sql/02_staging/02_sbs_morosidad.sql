USE riesgo_crediticio;
GO

IF OBJECT_ID('staging.sbs_morosidad') IS NOT NULL DROP TABLE staging.sbs_morosidad;
IF OBJECT_ID('tempdb..#ref')   IS NOT NULL DROP TABLE #ref;
IF OBJECT_ID('tempdb..#largo') IS NOT NULL DROP TABLE #largo;
GO

-- 1. Dónde está cada cosa en cada archivo (desp = 0 si "Concepto" está en col_00, 1 si en col_01)
WITH enc AS (
    SELECT codigo_cuadro, anio, mes,
           MIN(nro_fila) AS fila_enc,
           MIN(CASE WHEN LTRIM(RTRIM(col_00)) = N'Concepto' THEN 0 ELSE 1 END) AS desp
    FROM raw.sbs_morosidad
    WHERE LTRIM(RTRIM(col_00)) = N'Concepto' OR LTRIM(RTRIM(col_01)) = N'Concepto'
    GROUP BY codigo_cuadro, anio, mes
)
SELECT e.codigo_cuadro, e.anio, e.mes, e.fila_enc, e.desp,
       MIN(CASE WHEN LTRIM(RTRIM(CASE WHEN e.desp = 0 THEN r.col_00 ELSE r.col_01 END))
                     LIKE N'Total Cr%ditos Directo%' THEN r.nro_fila END) AS fila_total
INTO #ref
FROM enc e
JOIN raw.sbs_morosidad r
  ON r.codigo_cuadro = e.codigo_cuadro AND r.anio = e.anio AND r.mes = e.mes
GROUP BY e.codigo_cuadro, e.anio, e.mes, e.fila_enc, e.desp;
GO

-- 2. Todas las celdas con dato dentro del área del reporte, una fila por celda
SELECT r.codigo_cuadro, r.anio, r.mes, r.archivo, r.nro_fila,
       f.fila_enc, f.desp, u.idx, u.valor
INTO #largo
FROM raw.sbs_morosidad r
JOIN #ref f ON f.codigo_cuadro = r.codigo_cuadro AND f.anio = r.anio AND f.mes = r.mes
CROSS APPLY (VALUES
    (0,r.col_00),(1,r.col_01),(2,r.col_02),(3,r.col_03),(4,r.col_04),(5,r.col_05),
    (6,r.col_06),(7,r.col_07),(8,r.col_08),(9,r.col_09),(10,r.col_10),(11,r.col_11),
    (12,r.col_12),(13,r.col_13),(14,r.col_14),(15,r.col_15),(16,r.col_16),(17,r.col_17),
    (18,r.col_18),(19,r.col_19),(20,r.col_20),(21,r.col_21)
) AS u(idx, valor)
WHERE r.nro_fila BETWEEN f.fila_enc AND f.fila_total
  AND u.valor IS NOT NULL;
GO

-- 3. Construcción de la tabla limpia
WITH enc AS (        -- nombres de entidades (fila de encabezado, columnas a la derecha del concepto)
    SELECT codigo_cuadro, anio, mes, idx, LTRIM(RTRIM(valor)) AS entidad
    FROM #largo
    WHERE nro_fila = fila_enc AND idx > desp
),
conceptos AS (       -- la columna de conceptos (tipos de crédito y modalidades)
    SELECT codigo_cuadro, anio, mes, archivo, nro_fila, desp,
           LTRIM(RTRIM(valor)) AS concepto,
           -- quita asteriscos y marcas de nota al pie (" 1/", " 2/", ...)
           LTRIM(RTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(valor,
               N'*', N''), N' 1/', N''), N' 2/', N''), N' 3/', N''), N' 4/', N''))) AS concepto_limpio,
           LEN(valor + N'x') - LEN(LTRIM(valor) + N'x') AS sangria,
           CASE WHEN LTRIM(valor) LIKE N'Total Cr%ditos Directo%' THEN 1 ELSE 0 END AS es_total,
           CASE WHEN LTRIM(valor) LIKE N'Cr_ditos%'
                  OR LTRIM(valor) LIKE N'Total Cr%ditos Directo%' THEN 1 ELSE 0 END AS es_tipo
    FROM #largo
    WHERE idx = desp AND nro_fila > fila_enc
),
jerarquia AS (       -- a cada fila, la fila del tipo de crédito que la contiene
    SELECT *,
           MAX(CASE WHEN es_tipo = 1 THEN nro_fila END)
               OVER (PARTITION BY codigo_cuadro, anio, mes
                     ORDER BY nro_fila ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS fila_tipo
    FROM conceptos
),
canon_tipo AS (      -- nombres oficiales (con tildes) de los tipos de crédito
    SELECT nombre FROM (VALUES
        (N'Créditos corporativos'), (N'Créditos a grandes empresas'),
        (N'Créditos a medianas empresas'), (N'Créditos pequeñas empresas'),
        (N'Créditos a microempresas'), (N'Créditos de consumo'),
        (N'Créditos hipotecarios para vivienda')
    ) AS v(nombre)
),
canon_mod AS (       -- nombres oficiales de las modalidades
    SELECT nombre FROM (VALUES
        (N'Tarjetas de crédito'), (N'Descuentos'), (N'Préstamos'), (N'Factoring'),
        (N'Arrendamiento financiero y Lease-back'), (N'Comercio exterior'), (N'Otros'),
        (N'Préstamos revolventes'), (N'Préstamos no revolventes'), (N'Préstamos autos'),
        (N'Préstamos Mivivienda'), (N'Pignoraticios')
    ) AS v(nombre)
)
SELECT
    j.codigo_cuadro,
    CASE j.codigo_cuadro WHEN 'B-2362' THEN N'Banca Múltiple'
                         WHEN 'C-4234' THEN N'Empresas de Créditos'
                         WHEN 'C-2247' THEN N'Cajas Rurales'
                         WHEN 'C-1242' THEN N'Cajas Municipales' END          AS tipo_entidad,
    EOMONTH(DATEFROMPARTS(j.anio, j.mes, 1))                                 AS fecha,
    e.entidad,
    CASE WHEN e.entidad LIKE N'TOTAL%' THEN 1 ELSE 0 END                     AS es_total_entidad,
    CASE WHEN t.es_total = 1 THEN N'Total Créditos Directos'
         ELSE COALESCE(ct.nombre, t.concepto_limpio) END                     AS tipo_credito,
    CASE WHEN j.es_tipo = 1 THEN N'(Total del tipo)'
         ELSE COALESCE(cm.nombre, j.concepto_limpio) END                     AS modalidad,
    j.sangria                                                                AS nivel_sangria,
    TRY_CAST(TRY_CAST(v.valor AS float) AS decimal(18, 10))                  AS morosidad_pct,
    CASE WHEN LTRIM(RTRIM(v.valor)) = N'-' THEN 1 ELSE 0 END                 AS sin_cartera,
    j.nro_fila,
    j.archivo
INTO staging.sbs_morosidad
FROM jerarquia j
JOIN jerarquia t ON t.codigo_cuadro = j.codigo_cuadro AND t.anio = j.anio
                AND t.mes = j.mes AND t.nro_fila = j.fila_tipo
JOIN #largo v    ON v.codigo_cuadro = j.codigo_cuadro AND v.anio = j.anio
                AND v.mes = j.mes AND v.nro_fila = j.nro_fila AND v.idx > j.desp
JOIN enc e       ON e.codigo_cuadro = j.codigo_cuadro AND e.anio = j.anio
                AND e.mes = j.mes AND e.idx = v.idx
LEFT JOIN canon_tipo ct ON ct.nombre = t.concepto_limpio COLLATE Latin1_General_CI_AI
LEFT JOIN canon_mod  cm ON cm.nombre = j.concepto_limpio COLLATE Latin1_General_CI_AI;
GO