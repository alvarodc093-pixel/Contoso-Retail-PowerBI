"""Genera el proyecto de Power BI (formato PBIP: TMDL + PBIR) en powerbi/.

    python generar_pbip.py              # los datos se leen de GitHub
    python generar_pbip.py --local      # los datos se leen de powerbi/datos/

El modelo está en modelo.py y las páginas en informe.py. Los identificadores
(lineageTag, logicalId) se derivan del nombre de cada objeto, así que generar
dos veces da exactamente los mismos archivos.
"""

import argparse
import json
import shutil
import uuid
from pathlib import Path

from informe import PAGINAS
from modelo import RELACIONES, TABLAS, TIPOS_M, Medida, Tabla

RAIZ = Path(__file__).parent
CARPETA = RAIZ / "powerbi"
NOMBRE = "ContosoRetail"
URL_DATOS = "https://raw.githubusercontent.com/alvarodc093-pixel/Contoso-Retail-PowerBI/main/powerbi/datos/"

ESQUEMA = "https://developer.microsoft.com/json-schemas/fabric"
NS = uuid.UUID("6f1c2d0e-3c55-4a8e-9a57-0b9d2a1c7e11")


def uid(*partes: str) -> str:
    return str(uuid.uuid5(NS, "/".join(partes)))


def escribir(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(contenido, str):
        contenido = json.dumps(contenido, indent=2, ensure_ascii=False) + "\n"
    ruta.write_text(contenido, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- TMDL --

def nombre_tmdl(nombre: str) -> str:
    return nombre if nombre.replace("_", "").isalnum() and nombre.isascii() else f"'{nombre}'"


def tmdl_medida(t: Tabla, m: Medida) -> str:
    lineas = [f"\t/// {m.descripcion}", f"\tmeasure {nombre_tmdl(m.nombre)} ="]
    lineas += [f"\t\t\t{l}" for l in m.dax.split("\n")]
    if m.formato:
        lineas.append(f"\t\tformatString: {m.formato}")
    lineas.append(f"\t\tdisplayFolder: {m.carpeta}")
    lineas.append(f"\t\tlineageTag: {uid(t.nombre, 'medida', m.nombre)}")
    return "\n".join(lineas) + "\n"


def tmdl_tabla(t: Tabla, origen_local: bool) -> str:
    out = [f"/// {t.descripcion}", f"table {t.nombre}", f"\tlineageTag: {uid(t.nombre)}"]
    if t.es_calendario:
        out.append("\tdataCategory: Time")
    out.append("")
    for m in t.medidas:
        out.append(tmdl_medida(t, m))
    for c in t.columnas:
        out.append(f"\tcolumn {c.nombre}")
        out.append(f"\t\tdataType: {c.tipo}")
        if c.oculta:
            out.append("\t\tisHidden")
        if c.clave:
            out.append("\t\tisKey")
        if c.formato:
            out.append(f"\t\tformatString: {c.formato}")
        out.append(f"\t\tlineageTag: {uid(t.nombre, 'columna', c.nombre)}")
        out.append(f"\t\tsummarizeBy: {c.sumarizar}")
        out.append(f"\t\tsourceColumn: {c.nombre}")
        if c.ordenar_por:
            out.append(f"\t\tsortByColumn: {c.ordenar_por}")
        out.append("")
        if c.tipo == "dateTime":
            out.append("\t\tannotation UnderlyingDateTimeDataType = Date")
            out.append("")
    tipos = ", ".join(f'{{"{c.nombre}", {TIPOS_M[c.tipo]}}}' for c in t.columnas)
    m_query = [
        "let",
        f'    Ruta = OrigenDatos & "{t.nombre}.csv",',
        '    Contenido = if Text.StartsWith(Ruta, "http") then Web.Contents(Ruta) else File.Contents(Ruta),',
        '    Origen = Csv.Document(Contenido, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),",
        '    SinVacios = Table.TransformColumns(Encabezados, {}, each if _ = "" then null else _),',
        f'    Tipos = Table.TransformColumnTypes(SinVacios, {{{tipos}}}, "en-US")',
        "in",
        "    Tipos",
    ]
    out.append(f"\tpartition {t.nombre} = m")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    out += [f"\t\t\t\t{l}" for l in m_query]
    out.append("")
    out.append("\tannotation PBI_ResultType = Table")
    out.append("")
    return "\n".join(out) + "\n"


def generar_modelo(destino: Path, origen: str) -> None:
    base = destino / f"{NOMBRE}.SemanticModel"
    escribir(base / ".platform", {
        "$schema": f"{ESQUEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": uid("modelo")},
    })
    escribir(base / "definition.pbism", {"version": "4.2", "settings": {}})
    d = base / "definition"
    escribir(d / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n\n")
    orden = json.dumps([t.nombre for t in TABLAS] + ["OrigenDatos"])
    escribir(d / "model.tmdl", "\n".join([
        "model Model",
        "\tculture: es-ES",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: es-ES",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {orden}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        'annotation PBI_ProTooling = ["DevMode"]',
        "",
        *[f"ref table {t.nombre}" for t in TABLAS],
        "",
    ]) + "\n")
    escribir(d / "expressions.tmdl",
             f'expression OrigenDatos = "{origen}" meta [IsParameterQuery = true, Type = "Text", '
             f"IsParameterQueryRequired = true]\n\tlineageTag: {uid('OrigenDatos')}\n\n"
             "\tannotation PBI_ResultType = Text\n\n")
    rel = []
    for desde, hacia in RELACIONES:
        rel += [f"relationship {uid('rel', desde, hacia)}", f"\tfromColumn: {desde}",
                f"\ttoColumn: {hacia}", ""]
    escribir(d / "relationships.tmdl", "\n".join(rel) + "\n")
    for t in TABLAS:
        escribir(d / "tables" / f"{t.nombre}.tmdl", tmdl_tabla(t, origen.startswith("http")))


# ---------------------------------------------------------------- PBIR --

def lit(valor: str) -> dict:
    return {"expr": {"Literal": {"Value": valor}}}


def texto(s: str) -> dict:
    return lit("'" + s.replace("'", "''") + "'")


def campo(ref) -> dict:
    tipo, tabla, nombre = ref
    clave = "Column" if tipo == "col" else "Measure"
    return {clave: {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": nombre}}


def proyeccion(ref, rol: str, tipo_visual: str) -> dict:
    p = {"field": campo(ref), "queryRef": f"{ref[1]}.{ref[2]}", "nativeQueryRef": ref[2]}
    # "active" solo en ejes, filas y filtros: en una tabla hace que Power BI
    # descarte las medidas.
    if ref[0] == "col" and (rol in ("Category", "Rows") or tipo_visual == "slicer"):
        p["active"] = True
    return p


def visual_json(v: dict, z: int) -> dict:
    x, y, w, h = v["pos"]
    cuerpo = {"visualType": v["tipo"]}
    if v["tipo"] == "textbox":
        parrafos = [
            {"textRuns": [{"value": t, "textStyle": {"fontSize": tam, **({"fontWeight": "bold"} if neg else {})}}]}
            for t, tam, neg in v["parrafos"]
        ]
        cuerpo["objects"] = {"general": [{"properties": {"paragraphs": parrafos}}]}
    else:
        query = {"queryState": {rol: {"projections": [proyeccion(r, rol, v["tipo"]) for r in refs]}
                                for rol, refs in v["roles"].items()}}
        if v.get("orden"):
            ref, direccion = v["orden"]
            query["sortDefinition"] = {"sort": [{"field": campo(ref), "direction": direccion}]}
        cuerpo["query"] = query
        if v.get("titulo"):
            cuerpo["visualContainerObjects"] = {
                "title": [{"properties": {"show": lit("true"), "text": texto(v["titulo"])}}]
            }
        if v["tipo"] == "slicer":
            objetos = {"data": [{"properties": {"mode": texto("Dropdown")}}],
                       "header": [{"properties": {"show": lit("false")}}]}
            if v.get("defecto"):
                (_, tabla, columna), valor = v["defecto"]
                objetos["general"] = [{"properties": {"filter": {"filter": {
                    "Version": 2,
                    "From": [{"Name": "f", "Entity": tabla, "Type": 0}],
                    "Where": [{"Condition": {"In": {
                        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}},
                                                    "Property": columna}}],
                        "Values": [[{"Literal": {"Value": valor}}]],
                    }}}],
                }}}}]
            cuerpo["objects"] = objetos
        cuerpo["drillFilterOtherVisuals"] = True
    return {
        "$schema": f"{ESQUEMA}/item/report/definition/visualContainer/1.4.0/schema.json",
        "name": v["nombre"],
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": cuerpo,
    }


def generar_informe(destino: Path) -> None:
    base = destino / f"{NOMBRE}.Report"
    escribir(base / ".platform", {
        "$schema": f"{ESQUEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": uid("informe")},
    })
    escribir(base / "definition.pbir",
             {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}}})
    d = base / "definition"
    escribir(d / "version.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    escribir(d / "report.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {},
        "objects": {"outspacePane": [{"properties": {"expanded": lit("false")}}]},
        "settings": {"useEnhancedTooltips": False},
    })
    escribir(d / "pages" / "pages.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p["nombre"] for p in PAGINAS],
        "activePageName": PAGINAS[0]["nombre"],
    })
    for p in PAGINAS:
        carpeta = d / "pages" / p["nombre"]
        escribir(carpeta / "page.json", {
            "$schema": f"{ESQUEMA}/item/report/definition/page/1.3.0/schema.json",
            "name": p["nombre"], "displayName": p["titulo"], "displayOption": "FitToPage",
            "height": 720, "width": 1280,
        })
        for z, v in enumerate(p["visuales"]):
            escribir(carpeta / "visuals" / v["nombre"] / "visual.json", visual_json(v, z))


def generar(destino: Path = CARPETA, origen: str = URL_DATOS) -> None:
    for sub in (f"{NOMBRE}.SemanticModel/definition", f"{NOMBRE}.Report/definition"):
        shutil.rmtree(destino / sub, ignore_errors=True)
    generar_modelo(destino, origen)
    generar_informe(destino)
    escribir(destino / f"{NOMBRE}.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })


def documentar(destino: Path = RAIZ / "docs" / "medidas_dax.md") -> None:
    """Escribe la lista de medidas DAX con su código, agrupadas por carpeta."""
    from modelo import MEDIDAS

    lineas = ["# Medidas DAX", "",
              "Generado por `generar_pbip.py` a partir de `modelo.py`. "
              "Todas las medidas están en la tabla `ventas`.", ""]
    carpeta = None
    for m in MEDIDAS:
        if m.carpeta != carpeta:
            carpeta = m.carpeta
            lineas += [f"## {carpeta}", ""]
        lineas += [f"### {m.nombre}", "", m.descripcion, "", "```dax",
                   f"{m.nombre} =", m.dax, "```", ""]
    escribir(destino, "\n".join(lineas))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true",
                        help="leer los CSV de powerbi/datos/ en vez de GitHub")
    args = parser.parse_args()
    origen = str((CARPETA / "datos").resolve()) + "\\" if args.local else URL_DATOS
    generar(CARPETA, origen)
    documentar()
    print(f"Proyecto generado en {CARPETA / (NOMBRE + '.pbip')}")
    print(f"Datos: {origen}")


if __name__ == "__main__":
    main()
