"""Definición del modelo semántico: tablas, columnas, relaciones y medidas DAX.

generar_pbip.py convierte esto en archivos TMDL. Tenerlo en Python permite
testearlo (que cada medida apunte a columnas que existen, que las relaciones
unan columnas reales...) y generar la documentación de las medidas.
"""

from dataclasses import dataclass, field


@dataclass
class Columna:
    nombre: str
    tipo: str                       # int64 | double | string | dateTime
    formato: str | None = None
    oculta: bool = False
    ordenar_por: str | None = None
    clave: bool = False
    sumarizar: str = "none"


@dataclass
class Medida:
    nombre: str
    dax: str
    formato: str
    carpeta: str
    descripcion: str


@dataclass
class Tabla:
    nombre: str
    columnas: list[Columna]
    descripcion: str
    medidas: list[Medida] = field(default_factory=list)
    es_calendario: bool = False


# Formatos (Power BI los muestra con los separadores del idioma del informe).
USD = "\\$#,0;-\\$#,0;\\$#,0"
USD2 = "\\$#,0.00;-\\$#,0.00;\\$#,0.00"
ENTERO = "#,0"
PCT = "0.0%;-0.0%;0.0%"
PCT_SIGNO = "+0.0%;-0.0%;0.0%"
USD_SIGNO = "+\\$#,0;-\\$#,0;\\$#,0"
FECHA = "dd/mm/yyyy"

TIPOS_M = {"int64": "Int64.Type", "double": "type number", "string": "type text", "dateTime": "type date"}


def _id(nombre, oculta=True):
    return Columna(nombre, "int64", oculta=oculta)


MEDIDAS = [
    # --- Ventas básicas -------------------------------------------------
    Medida("Ventas", "SUMX ( ventas, ventas[cantidad] * ventas[precio_neto] )", USD,
           "1. Ventas", "Importe vendido en USD, con descuentos (cantidad x precio neto)."),
    Medida("Coste", "SUMX ( ventas, ventas[cantidad] * ventas[coste_unitario] )", USD,
           "1. Ventas", "Coste de los productos vendidos en USD."),
    Medida("Margen", "[Ventas] - [Coste]", USD, "1. Ventas", "Ventas menos coste."),
    Medida("Margen %", "DIVIDE ( [Margen], [Ventas] )", PCT, "1. Ventas",
           "Margen bruto sobre ventas."),
    Medida("Unidades", "SUM ( ventas[cantidad] )", ENTERO, "1. Ventas", "Unidades vendidas."),
    Medida("Pedidos", "DISTINCTCOUNT ( ventas[pedido_id] )", ENTERO, "1. Ventas",
           "Número de pedidos distintos (un pedido tiene varias líneas)."),
    Medida("Ticket medio", "DIVIDE ( [Ventas], [Pedidos] )", USD, "1. Ventas",
           "Importe medio por pedido."),
    Medida("Descuento medio %",
           "VAR tarifa = SUMX ( ventas, ventas[cantidad] * ventas[precio_unitario] )\n"
           "RETURN\n"
           "    IF ( NOT ISBLANK ( tarifa ), 1 - DIVIDE ( [Ventas], tarifa ) )",
           PCT, "1. Ventas", "Cuánto se rebaja de media el precio de tarifa."),
    # --- Clientes -------------------------------------------------------
    Medida("Clientes", "DISTINCTCOUNT ( ventas[cliente_id] )", ENTERO, "2. Clientes",
           "Clientes distintos que compran en el periodo."),
    Medida("Clientes nuevos",
           "VAR inicio = MIN ( calendario[fecha] )\n"
           "VAR fin = MAX ( calendario[fecha] )\n"
           "VAR primeras =\n"
           "    ADDCOLUMNS (\n"
           "        VALUES ( ventas[cliente_id] ),\n"
           "        \"@primera\", CALCULATE ( MIN ( ventas[fecha] ), REMOVEFILTERS ( calendario ) )\n"
           "    )\n"
           "RETURN\n"
           "    COUNTROWS ( FILTER ( primeras, [@primera] >= inicio && [@primera] <= fin ) )",
           ENTERO, "2. Clientes", "Clientes cuya primera compra cae dentro del periodo."),
    Medida("% clientes nuevos", "DIVIDE ( [Clientes nuevos], [Clientes] )", PCT, "2. Clientes",
           "Parte de los clientes del periodo que compran por primera vez."),
    # --- Inteligencia de tiempo ----------------------------------------
    Medida("Ventas AA", "CALCULATE ( [Ventas], SAMEPERIODLASTYEAR ( calendario[fecha] ) )", USD,
           "3. Tiempo", "Ventas del mismo periodo del año anterior."),
    Medida("Var vs AA", "IF ( NOT ISBLANK ( [Ventas AA] ), [Ventas] - [Ventas AA] )", USD_SIGNO,
           "3. Tiempo", "Diferencia frente al año anterior."),
    Medida("Var vs AA %", "DIVIDE ( [Var vs AA], [Ventas AA] )", PCT_SIGNO, "3. Tiempo",
           "Crecimiento frente al año anterior."),
    Medida("Ventas acumuladas año", "TOTALYTD ( [Ventas], calendario[fecha] )", USD, "3. Tiempo",
           "Ventas desde el 1 de enero hasta la fecha del contexto."),
    Medida("Ventas acumuladas año AA",
           "CALCULATE ( [Ventas acumuladas año], SAMEPERIODLASTYEAR ( calendario[fecha] ) )", USD,
           "3. Tiempo", "Lo mismo, un año antes."),
    Medida("Ventas media móvil 3M",
           "VAR fin = MAX ( calendario[fecha] )\n"
           "RETURN\n"
           "    DIVIDE (\n"
           "        CALCULATE ( [Ventas], DATESINPERIOD ( calendario[fecha], fin, -3, MONTH ) ),\n"
           "        3\n"
           "    )",
           USD, "3. Tiempo", "Media mensual de los últimos 3 meses."),
    Medida("Margen % AA", "CALCULATE ( [Margen %], SAMEPERIODLASTYEAR ( calendario[fecha] ) )",
           PCT, "3. Tiempo", "Margen % del año anterior."),
    # --- Canales y tiendas ---------------------------------------------
    Medida("Ventas online", "CALCULATE ( [Ventas], tiendas[canal] = \"Online\" )", USD,
           "4. Canales", "Ventas de la tienda online."),
    Medida("% online", "DIVIDE ( [Ventas online], [Ventas] )", PCT, "4. Canales",
           "Peso de la tienda online en las ventas."),
    Medida("Ventas tiendas físicas", "CALCULATE ( [Ventas], tiendas[canal] = \"Tienda física\" )",
           USD, "4. Canales", "Ventas de las tiendas físicas."),
    Medida("Ventas por m²",
           "VAR tiendasConVentas =\n"
           "    FILTER ( VALUES ( tiendas[tienda_id] ), [Ventas tiendas físicas] > 0 )\n"
           "VAR superficie =\n"
           "    SUMX ( tiendasConVentas, CALCULATE ( SUM ( tiendas[m2] ) ) )\n"
           "RETURN\n"
           "    DIVIDE ( [Ventas tiendas físicas], superficie )",
           USD, "4. Canales",
           "Ventas de tienda física entre los m² de las tiendas que han vendido en el periodo."),
    Medida("Ranking categoría",
           "IF (\n"
           "    HASONEVALUE ( categorias[categoria] ),\n"
           "    RANKX ( ALLSELECTED ( categorias[categoria] ), [Ventas] )\n"
           ")",
           ENTERO, "1. Ventas", "Puesto de la categoría por ventas dentro de la selección."),
    # --- Objetivos ------------------------------------------------------
    Medida("Objetivo", "SUM ( objetivos[objetivo] )", USD, "5. Objetivos",
           "Presupuesto de ventas: mismo mes del año anterior + 8 %."),
    Medida("Desviación vs objetivo", "IF ( NOT ISBLANK ( [Objetivo] ), [Ventas] - [Objetivo] )",
           USD_SIGNO, "5. Objetivos", "Ventas menos objetivo."),
    Medida("Cumplimiento %", "DIVIDE ( [Ventas], [Objetivo] )", PCT, "5. Objetivos",
           "Ventas sobre objetivo (100 % = objetivo cumplido)."),
    Medida("Objetivo acumulado año", "TOTALYTD ( [Objetivo], calendario[fecha] )", USD,
           "5. Objetivos", "Objetivo desde el 1 de enero."),
    Medida("Estado objetivo",
           "VAR c = [Cumplimiento %]\n"
           "RETURN\n"
           "    SWITCH (\n"
           "        TRUE (),\n"
           "        ISBLANK ( c ), BLANK (),\n"
           "        c >= 1, \"Cumplido\",\n"
           "        c >= 0.9, \"Cerca (90-100 %)\",\n"
           "        \"Por debajo del 90 %\"\n"
           "    )",
           "", "5. Objetivos", "Semáforo de cumplimiento en texto."),
]

TABLAS = [
    Tabla("ventas", [
        _id("pedido_id"), Columna("linea", "int64", oculta=True),
        Columna("fecha", "dateTime", FECHA, oculta=True),
        Columna("dias_entrega", "int64", ENTERO, sumarizar="average"),
        _id("cliente_id"), _id("tienda_id"), _id("producto_id"),
        Columna("cantidad", "int64", ENTERO, oculta=True, sumarizar="sum"),
        Columna("precio_unitario", "double", USD2, oculta=True),
        Columna("precio_neto", "double", USD2, oculta=True),
        Columna("coste_unitario", "double", USD2, oculta=True),
        Columna("moneda", "string"),
    ], "Hechos: una fila por línea de pedido. Importes en USD.", MEDIDAS),
    Tabla("productos", [
        Columna("producto_id", "int64", oculta=True, clave=True),
        Columna("producto", "string"), Columna("marca", "string"),
        Columna("fabricante", "string"), Columna("color", "string"),
        _id("categoria_id"), Columna("subcategoria", "string"),
        Columna("precio_lista", "double", USD2), Columna("coste_lista", "double", USD2),
    ], "Un producto por fila."),
    Tabla("categorias", [
        Columna("categoria_id", "int64", oculta=True, clave=True),
        Columna("categoria", "string"),
    ], "Categoría de producto. Une productos y objetivos, que tienen distinto detalle."),
    Tabla("tiendas", [
        Columna("tienda_id", "int64", oculta=True, clave=True),
        Columna("tienda", "string"), Columna("canal", "string"),
        Columna("pais", "string"), Columna("region", "string"),
        Columna("apertura", "dateTime", FECHA), Columna("cierre", "dateTime", FECHA),
        Columna("m2", "int64", ENTERO, sumarizar="sum"), Columna("estado", "string"),
    ], "Tiendas físicas más la tienda online."),
    Tabla("clientes", [
        Columna("cliente_id", "int64", oculta=True, clave=True),
        Columna("pais", "string"), Columna("continente", "string"),
        Columna("genero", "string"), Columna("grupo_edad", "string"),
    ], "Clientes que han comprado, sin datos personales."),
    Tabla("calendario", [
        Columna("fecha", "dateTime", FECHA, clave=True),
        Columna("anio", "int64", "0"),
        Columna("trimestre", "string"), Columna("anio_trimestre", "string"),
        Columna("mes_num", "int64", "0", oculta=True),
        Columna("mes", "string", ordenar_por="mes_num"),
        Columna("anio_mes_num", "int64", "0", oculta=True),
        Columna("anio_mes", "string", ordenar_por="anio_mes_num"),
        Columna("dia_semana_num", "int64", "0", oculta=True),
        Columna("dia_semana", "string", ordenar_por="dia_semana_num"),
        Columna("tipo_dia", "string"),
    ], "Una fila por día de 2016 a 2025.", es_calendario=True),
    Tabla("objetivos", [
        Columna("fecha", "dateTime", FECHA, oculta=True),
        _id("categoria_id"),
        Columna("objetivo", "double", USD, oculta=True),
    ], "Presupuesto mensual por categoría (día 1 de cada mes)."),
]

# (desde, hacia): muchos a uno, filtro en una dirección.
RELACIONES = [
    ("ventas.fecha", "calendario.fecha"),
    ("ventas.producto_id", "productos.producto_id"),
    ("ventas.tienda_id", "tiendas.tienda_id"),
    ("ventas.cliente_id", "clientes.cliente_id"),
    ("productos.categoria_id", "categorias.categoria_id"),
    ("objetivos.fecha", "calendario.fecha"),
    ("objetivos.categoria_id", "categorias.categoria_id"),
]


def tabla(nombre: str) -> Tabla:
    return next(t for t in TABLAS if t.nombre == nombre)


def medida(nombre: str) -> Medida:
    return next(m for m in MEDIDAS if m.nombre == nombre)
