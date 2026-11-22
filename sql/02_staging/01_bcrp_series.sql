USE riesgo_crediticio;
GO

IF OBJECT_ID('staging.bcrp_series') IS NOT NULL DROP TABLE staging.bcrp_series;
GO

WITH meses AS (
    SELECT abrev, num FROM (VALUES
        ('Jan',1),('Feb',2),('Mar',3),('Apr',4),('May',5),('Jun',6),
        ('Jul',7),('Aug',8),('Sep',9),('Set',9),('Oct',10),('Nov',11),('Dec',12)
    ) AS v(abrev, num)
),
partes AS (
    SELECT
        serie_codigo, serie_nombre, frecuencia, valor, fecha_carga,
        PARSENAME(periodo, 1) AS anio_txt,
        PARSENAME(periodo, 2) AS mes_txt,
        CASE WHEN frecuencia = 'diaria' THEN TRY_CAST(PARSENAME(periodo, 3) AS int) ELSE 1 END AS dia
    FROM raw.bcrp_series
)
SELECT
    p.serie_codigo,
    p.serie_nombre,
    p.frecuencia,
    DATEFROMPARTS(
        CASE WHEN LEN(p.anio_txt) = 2 THEN 2000 + CAST(p.anio_txt AS int)
             ELSE CAST(p.anio_txt AS int) END,
        m.num,
        p.dia
    ) AS fecha,
    TRY_CAST(p.valor AS decimal(18, 6)) AS valor,
    p.fecha_carga
INTO staging.bcrp_series
FROM partes p
LEFT JOIN meses m ON m.abrev = p.mes_txt;
GO