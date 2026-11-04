"""Prepara las tablas del modelo de Power BI a partir de los CSV de Contoso.

Lee data/raw/ (los CSV originales de Contoso V2, versión 100K) y escribe en
powerbi/datos/ un esquema en estrella listo para Power BI:

    ventas       hechos: una fila por línea de pedido
    productos    dimensión de producto
    categorias   dimensión de categoría (une productos y objetivos)
    tiendas      dimensión de tienda (incluye la tienda online)
    clientes     dimensión de cliente, sin datos personales
    calendario   una fila por día, en español
    objetivos    presupuesto mensual por categoría

También guarda powerbi/datos/cifras_control.json con los totales que tiene
que dar el informe, calculados aquí con SQL, para comprobar las medidas DAX.

Uso: python preparar_datos.py
"""

import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).parent
RAW = RAIZ / "data" / "raw"
SALIDA = RAIZ / "powerbi" / "datos"

TIENDA_ONLINE = 999999
CRECIMIENTO_OBJETIVO = 0.08     # el plan pide un 8 % más que el año anterior
PRIMER_ANIO, ULTIMO_ANIO = 2016, 2025

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def conectar(raw: Path = RAW) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for tabla, archivo in {
        "raw_ventas": "sales.csv",
        "raw_productos": "product.csv",
        "raw_clientes": "customer.csv",
        "raw_tiendas": "store.csv",
    }.items():
        con.execute(
            f"CREATE TABLE {tabla} AS SELECT * FROM read_csv('{(raw / archivo).as_posix()}', "
            "header = true, auto_detect = true)"
        )
    return con


def construir(con: duckdb.DuckDBPyConnection) -> None:
    meses = "[" + ", ".join(f"'{m}'" for m in MESES) + "]"
    dias = "[" + ", ".join(f"'{d}'" for d in DIAS) + "]"
    con.execute(f"""
    -- Hechos. Los precios de Contoso están en USD en todos los pedidos; el
    -- tipo de cambio solo sirve para pasar a la moneda local, así que no
    -- se usa para el análisis.
    CREATE OR REPLACE TABLE ventas AS
    SELECT
        OrderKey                        AS pedido_id,
        LineNumber                      AS linea,
        CAST(OrderDate AS DATE)         AS fecha,
        DATE_DIFF('day', OrderDate, DeliveryDate) AS dias_entrega,
        CustomerKey                     AS cliente_id,
        StoreKey                        AS tienda_id,
        ProductKey                      AS producto_id,
        Quantity                        AS cantidad,
        ROUND(UnitPrice, 4)             AS precio_unitario,
        ROUND(NetPrice, 4)              AS precio_neto,
        ROUND(UnitCost, 4)              AS coste_unitario,
        CurrencyCode                    AS moneda
    FROM raw_ventas
    WHERE YEAR(OrderDate) BETWEEN {PRIMER_ANIO} AND {ULTIMO_ANIO}
    ORDER BY fecha, pedido_id, linea;

    CREATE OR REPLACE TABLE categorias AS
    SELECT DISTINCT CategoryKey AS categoria_id, CategoryName AS categoria
    FROM raw_productos
    ORDER BY categoria_id;

    CREATE OR REPLACE TABLE productos AS
    SELECT
        ProductKey      AS producto_id,
        ProductName     AS producto,
        Brand           AS marca,
        Manufacturer    AS fabricante,
        Color           AS color,
        CategoryKey     AS categoria_id,
        SubCategoryName AS subcategoria,
        Price           AS precio_lista,
        Cost            AS coste_lista
    FROM raw_productos
    ORDER BY producto_id;

    CREATE OR REPLACE TABLE tiendas AS
    SELECT
        StoreKey AS tienda_id,
        CASE WHEN StoreKey = {TIENDA_ONLINE} THEN 'Tienda online'
             ELSE 'Tienda ' || CountryCode || ' - ' || State END     AS tienda,
        CASE WHEN StoreKey = {TIENDA_ONLINE} THEN 'Online'
             ELSE 'Tienda física' END                                AS canal,
        CASE WHEN StoreKey = {TIENDA_ONLINE} THEN 'Online'
             ELSE CountryName END                                    AS pais,
        State                                                        AS region,
        CAST(OpenDate AS DATE)                                       AS apertura,
        CAST(CloseDate AS DATE)                                      AS cierre,
        SquareMeters                                                 AS m2,
        CASE Status WHEN 'Closed' THEN 'Cerrada'
                    WHEN 'Restructured' THEN 'Reformada'
                    ELSE 'Abierta' END                               AS estado
    FROM raw_tiendas
    ORDER BY tienda_id;

    -- Solo los clientes que compran, y sin nombres ni direcciones.
    CREATE OR REPLACE TABLE clientes AS
    SELECT
        c.CustomerKey  AS cliente_id,
        c.CountryFull  AS pais,
        c.Continent    AS continente,
        CASE c.Gender WHEN 'female' THEN 'Mujer' ELSE 'Hombre' END AS genero,
        CASE
            WHEN DATE_DIFF('year', c.Birthday, DATE '{ULTIMO_ANIO}-12-31') < 30 THEN '1. Menos de 30'
            WHEN DATE_DIFF('year', c.Birthday, DATE '{ULTIMO_ANIO}-12-31') < 45 THEN '2. 30-44'
            WHEN DATE_DIFF('year', c.Birthday, DATE '{ULTIMO_ANIO}-12-31') < 60 THEN '3. 45-59'
            ELSE '4. 60 o más'
        END AS grupo_edad
    FROM raw_clientes AS c
    WHERE c.CustomerKey IN (SELECT DISTINCT cliente_id FROM ventas)
    ORDER BY cliente_id;

    CREATE OR REPLACE TABLE calendario AS
    SELECT
        CAST(d AS DATE)                                   AS fecha,
        YEAR(d)                                           AS anio,
        'T' || QUARTER(d)                                 AS trimestre,
        YEAR(d) || '-T' || QUARTER(d)                     AS anio_trimestre,
        MONTH(d)                                          AS mes_num,
        {meses}[MONTH(d)]                                 AS mes,
        {meses}[MONTH(d)] || ' ' || YEAR(d)               AS anio_mes,
        YEAR(d) * 100 + MONTH(d)                          AS anio_mes_num,
        ISODOW(d)                                         AS dia_semana_num,
        {dias}[ISODOW(d)]                                 AS dia_semana,
        CASE WHEN ISODOW(d) <= 5 THEN 'Laborable' ELSE 'Fin de semana' END AS tipo_dia
    FROM GENERATE_SERIES(DATE '{PRIMER_ANIO}-01-01', DATE '{ULTIMO_ANIO}-12-31', INTERVAL 1 DAY) AS t(d);

    -- Presupuesto: cada mes y categoría, lo vendido el mismo mes del año
    -- anterior más un {CRECIMIENTO_OBJETIVO:.0%}. Se guarda el día 1 de cada mes.
    CREATE OR REPLACE TABLE objetivos AS
    WITH mensual AS (
        SELECT
            CAST(DATE_TRUNC('month', v.fecha) AS DATE) AS mes,
            p.categoria_id,
            SUM(v.cantidad * v.precio_neto)            AS ventas
        FROM ventas AS v
        JOIN productos AS p USING (producto_id)
        GROUP BY ALL
    )
    SELECT
        CAST(mes + INTERVAL 1 YEAR AS DATE)              AS fecha,
        categoria_id,
        ROUND(ventas * (1 + {CRECIMIENTO_OBJETIVO}), -2) AS objetivo
    FROM mensual
    WHERE YEAR(mes) + 1 BETWEEN 2017 AND {ULTIMO_ANIO}
    ORDER BY fecha, categoria_id;
    """)


def cifras_control(con: duckdb.DuckDBPyConnection) -> dict:
    """Totales por año calculados en SQL: el informe tiene que dar lo mismo."""
    filas = con.execute(f"""
        SELECT
            YEAR(v.fecha)                                            AS anio,
            ROUND(SUM(v.cantidad * v.precio_neto), 2)                AS ventas,
            ROUND(SUM(v.cantidad * v.coste_unitario), 2)             AS coste,
            COUNT(DISTINCT v.pedido_id)                              AS pedidos,
            SUM(v.cantidad)                                          AS unidades,
            COUNT(DISTINCT v.cliente_id)                             AS clientes,
            COALESCE(ROUND(SUM(v.cantidad * v.precio_neto)
                  FILTER (WHERE v.tienda_id = {TIENDA_ONLINE}), 2), 0) AS ventas_online
        FROM ventas AS v
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    objetivos = dict(con.execute(
        "SELECT YEAR(fecha), ROUND(SUM(objetivo), 2) FROM objetivos GROUP BY 1"
    ).fetchall())
    salida = {}
    for anio, ventas, coste, pedidos, unidades, clientes, online in filas:
        ventas, coste, online = float(ventas), float(coste), float(online)
        salida[str(anio)] = {
            "ventas": ventas,
            "coste": coste,
            "margen_pct": round(1 - coste / ventas, 4),
            "pedidos": pedidos,
            "unidades": int(unidades),
            "clientes": clientes,
            "ticket_medio": round(ventas / pedidos, 2),
            "pct_online": round(online / ventas, 4),
            "objetivo": objetivos.get(anio),
        }
    return salida


TABLAS = ["ventas", "productos", "categorias", "tiendas", "clientes", "calendario", "objetivos"]


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    con = conectar()
    construir(con)
    for tabla in TABLAS:
        destino = (SALIDA / f"{tabla}.csv").as_posix()
        con.execute(f"COPY {tabla} TO '{destino}' (HEADER, DELIMITER ',')")
        n = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"{tabla:<12} {n:>8} filas")
    cifras = cifras_control(con)
    (SALIDA / "cifras_control.json").write_text(
        json.dumps(cifras, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("cifras_control.json guardado")


if __name__ == "__main__":
    main()
