"""Definición de las páginas del informe y de sus objetos visuales.

Cada visual es un diccionario sencillo; generar_pbip.py lo convierte al
formato PBIR (un visual.json por objeto). Lienzo de 1280 x 720.
"""

ANIO_POR_DEFECTO = 2025


def C(tabla, columna):
    """Referencia a una columna."""
    return ("col", tabla, columna)


def M(nombre):
    """Referencia a una medida (todas viven en la tabla ventas)."""
    return ("med", "ventas", nombre)


def cabecera(titulo, subtitulo):
    return {"nombre": "cabecera", "tipo": "textbox", "pos": (16, 4, 840, 72),
            "parrafos": [(titulo, "20pt", True), (subtitulo, "11pt", False)]}


def slicer_anio(x=872, defecto=ANIO_POR_DEFECTO):
    return {"nombre": "filtro_anio", "tipo": "slicer", "pos": (x, 8, 190, 60),
            "roles": {"Values": [C("calendario", "anio")]}, "titulo": "Año",
            "defecto": (C("calendario", "anio"), f"{defecto}L") if defecto else None}


def slicer_canal(x=1074):
    return {"nombre": "filtro_canal", "tipo": "slicer", "pos": (x, 8, 190, 60),
            "roles": {"Values": [C("tiendas", "canal")]}, "titulo": "Canal"}


def tarjetas(prefijo, medidas, y=84, alto=96):
    n = len(medidas)
    hueco = 16
    ancho = (1248 - hueco * (n - 1)) // n
    return [
        {"nombre": f"{prefijo}_{i}", "tipo": "card",
         "pos": (16 + i * (ancho + hueco), y, ancho, alto),
         "roles": {"Values": [M(m)]}}
        for i, m in enumerate(medidas)
    ]


PAGINAS = [
    {
        "nombre": "resumen",
        "titulo": "Resumen",
        "visuales": [
            cabecera("Contoso · Resumen de ventas",
                     "Importes en USD. Por defecto, 2025 frente a 2024."),
            slicer_anio(), slicer_canal(),
            *tarjetas("kpi", ["Ventas", "Var vs AA %", "Margen %", "Pedidos", "Ticket medio", "Cumplimiento %"]),
            {"nombre": "ventas_mes", "tipo": "lineChart", "pos": (16, 196, 812, 252),
             "roles": {"Category": [C("calendario", "mes")], "Y": [M("Ventas"), M("Ventas AA")]},
             "titulo": "Ventas por mes frente al año anterior", "orden": (C("calendario", "mes"), "Ascending")},
            {"nombre": "ventas_canal", "tipo": "donutChart", "pos": (844, 196, 420, 252),
             "roles": {"Category": [C("tiendas", "canal")], "Y": [M("Ventas")]},
             "titulo": "Ventas por canal"},
            {"nombre": "ventas_categoria", "tipo": "clusteredBarChart", "pos": (16, 464, 620, 240),
             "roles": {"Category": [C("categorias", "categoria")], "Y": [M("Ventas")]},
             "titulo": "Ventas por categoría", "orden": (M("Ventas"), "Descending")},
            {"nombre": "ventas_pais", "tipo": "clusteredBarChart", "pos": (652, 464, 612, 240),
             "roles": {"Category": [C("tiendas", "pais")], "Y": [M("Ventas")]},
             "titulo": "Ventas por país de la tienda", "orden": (M("Ventas"), "Descending")},
        ],
    },
    {
        "nombre": "productos",
        "titulo": "Productos",
        "visuales": [
            cabecera("Productos y categorías",
                     "Crecimiento, margen y descuento por categoría."),
            slicer_anio(), slicer_canal(),
            {"nombre": "matriz_categorias", "tipo": "pivotTable", "pos": (16, 84, 760, 620),
             "roles": {"Rows": [C("categorias", "categoria"), C("productos", "subcategoria")],
                       "Values": [M("Ventas"), M("Var vs AA %"), M("Margen %"), M("Unidades"),
                                  M("Descuento medio %")]},
             "titulo": "Categorías y subcategorías", "orden": (M("Ventas"), "Descending")},
            {"nombre": "crecimiento_categoria", "tipo": "clusteredBarChart", "pos": (792, 84, 472, 300),
             "roles": {"Category": [C("categorias", "categoria")], "Y": [M("Var vs AA %")]},
             "titulo": "Crecimiento frente al año anterior", "orden": (M("Var vs AA %"), "Descending")},
            {"nombre": "top_productos", "tipo": "tableEx", "pos": (792, 400, 472, 304),
             "roles": {"Values": [C("productos", "producto"), M("Ventas"), M("Unidades")]},
             "titulo": "Productos más vendidos", "orden": (M("Ventas"), "Descending")},
        ],
    },
    {
        "nombre": "evolucion",
        "titulo": "Evolución",
        "visuales": [
            cabecera("Evolución 2016-2025",
                     "2016 empieza en mayo y no tiene objetivo."),
            slicer_canal(),
            {"nombre": "ventas_online_anio", "tipo": "lineClusteredColumnComboChart",
             "pos": (16, 84, 812, 300),
             "roles": {"Category": [C("calendario", "anio")], "Y": [M("Ventas")], "Y2": [M("% online")]},
             "titulo": "Ventas y peso del canal online", "orden": (C("calendario", "anio"), "Ascending")},
            {"nombre": "ticket_anio", "tipo": "lineChart", "pos": (844, 84, 420, 300),
             "roles": {"Category": [C("calendario", "anio")], "Y": [M("Ticket medio")]},
             "titulo": "Ticket medio por año", "orden": (C("calendario", "anio"), "Ascending")},
            {"nombre": "clientes_anio", "tipo": "clusteredColumnChart", "pos": (16, 400, 620, 304),
             "roles": {"Category": [C("calendario", "anio")], "Y": [M("Clientes"), M("Clientes nuevos")]},
             "titulo": "Clientes y clientes nuevos", "orden": (C("calendario", "anio"), "Ascending")},
            {"nombre": "tabla_anual", "tipo": "tableEx", "pos": (652, 400, 612, 304),
             "roles": {"Values": [C("calendario", "anio"), M("Ventas"), M("Var vs AA %"), M("Margen %"),
                                  M("Ticket medio"), M("% online")]},
             "titulo": "Resumen anual", "orden": (C("calendario", "anio"), "Ascending")},
        ],
    },
    {
        "nombre": "tiendas",
        "titulo": "Tiendas",
        "visuales": [
            cabecera("Tiendas y canal online",
                     "Ventas por m²: solo tiendas físicas con ventas en el año."),
            slicer_anio(x=1074),
            *tarjetas("kpi_tiendas", ["Ventas tiendas físicas", "Ventas online", "% online", "Ventas por m²"]),
            {"nombre": "ventas_pais", "tipo": "clusteredBarChart", "pos": (16, 196, 500, 508),
             "roles": {"Category": [C("tiendas", "pais")], "Y": [M("Ventas")]},
             "titulo": "Ventas por país", "orden": (M("Ventas"), "Descending")},
            {"nombre": "tabla_tiendas", "tipo": "tableEx", "pos": (532, 196, 732, 508),
             "roles": {"Values": [C("tiendas", "tienda"), C("tiendas", "estado"), C("tiendas", "m2"),
                                  M("Ventas"), M("Ventas por m²"), M("Var vs AA %")]},
             "titulo": "Tiendas", "orden": (M("Ventas"), "Descending")},
        ],
    },
    {
        "nombre": "objetivos",
        "titulo": "Objetivos",
        "visuales": [
            cabecera("Ventas frente a objetivo",
                     "Objetivo = mismo mes del año anterior + 8 %."),
            slicer_anio(x=1074),
            *tarjetas("kpi_objetivo", ["Ventas", "Objetivo", "Desviación vs objetivo", "Cumplimiento %"]),
            {"nombre": "ventas_objetivo_mes", "tipo": "lineClusteredColumnComboChart",
             "pos": (16, 196, 812, 260),
             "roles": {"Category": [C("calendario", "mes")], "Y": [M("Ventas")], "Y2": [M("Objetivo")]},
             "titulo": "Ventas y objetivo por mes", "orden": (C("calendario", "mes"), "Ascending")},
            {"nombre": "acumulado", "tipo": "lineChart", "pos": (844, 196, 420, 260),
             "roles": {"Category": [C("calendario", "mes")],
                       "Y": [M("Ventas acumuladas año"), M("Objetivo acumulado año"),
                             M("Ventas acumuladas año AA")]},
             "titulo": "Acumulado del año", "orden": (C("calendario", "mes"), "Ascending")},
            {"nombre": "cumplimiento_categoria", "tipo": "tableEx", "pos": (16, 472, 1248, 232),
             "roles": {"Values": [C("categorias", "categoria"), M("Ranking categoría"), M("Ventas"), M("Objetivo"),
                                  M("Desviación vs objetivo"), M("Cumplimiento %"), M("Estado objetivo")]},
             "titulo": "Cumplimiento por categoría", "orden": (M("Cumplimiento %"), "Descending")},
        ],
    },
]
