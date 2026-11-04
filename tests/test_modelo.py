"""Tests del modelo semántico y del informe, sin necesidad de abrir Power BI.

Comprueban que todo lo que se referencia existe: columnas de las medidas,
relaciones, campos de los visuales, y que los CSV tienen las columnas que el
modelo espera.
"""

import csv
import json
import re

import pytest

from generar_pbip import CARPETA, NOMBRE, generar
from informe import PAGINAS
from modelo import MEDIDAS, RELACIONES, TABLAS, tabla

DATOS = CARPETA / "datos"
NOMBRES_MEDIDAS = {m.nombre for m in MEDIDAS}


def columnas_de(nombre_tabla):
    return {c.nombre for c in tabla(nombre_tabla).columnas}


def test_nombres_unicos():
    assert len(NOMBRES_MEDIDAS) == len(MEDIDAS)
    for t in TABLAS:
        nombres = [c.nombre for c in t.columnas]
        assert len(nombres) == len(set(nombres)), t.nombre


@pytest.mark.parametrize("m", MEDIDAS, ids=lambda m: m.nombre)
def test_medida_referencia_columnas_y_medidas_existentes(m):
    for t, c in re.findall(r"(\w+)\[([^\]]+)\]", m.dax):
        assert c in columnas_de(t), f"{m.nombre}: {t}[{c}] no existe"
    # [Algo] sin tabla delante es una medida (o una columna creada con ADDCOLUMNS, que empieza por @)
    for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", m.dax):
        assert ref.startswith("@") or ref in NOMBRES_MEDIDAS, f"{m.nombre}: [{ref}] no es una medida"


def test_medidas_bien_documentadas():
    for m in MEDIDAS:
        assert m.descripcion and m.carpeta, m.nombre
        assert m.dax.count("(") == m.dax.count(")"), m.nombre


def test_relaciones_unen_columnas_existentes_y_van_a_una_clave():
    for desde, hacia in RELACIONES:
        t1, c1 = desde.split(".")
        t2, c2 = hacia.split(".")
        assert c1 in columnas_de(t1)
        assert c2 in columnas_de(t2)
        assert any(c.nombre == c2 and c.clave for c in tabla(t2).columnas), hacia


def test_columnas_ordenadas_por_columnas_existentes():
    for t in TABLAS:
        for c in t.columnas:
            if c.ordenar_por:
                assert c.ordenar_por in columnas_de(t.nombre)


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p["nombre"])
def test_visuales_usan_campos_existentes(pagina):
    nombres = [v["nombre"] for v in pagina["visuales"]]
    assert len(nombres) == len(set(nombres))
    for v in pagina["visuales"]:
        x, y, w, h = v["pos"]
        assert x >= 0 and y >= 0 and x + w <= 1280 and y + h <= 720, v["nombre"]
        refs = [r for refs in v.get("roles", {}).values() for r in refs]
        if v.get("orden"):
            refs.append(v["orden"][0])
        for tipo, t, nombre in refs:
            if tipo == "col":
                assert nombre in columnas_de(t), f"{v['nombre']}: {t}.{nombre}"
            else:
                assert nombre in NOMBRES_MEDIDAS, f"{v['nombre']}: medida {nombre}"


def test_csv_tienen_las_columnas_del_modelo():
    if not (DATOS / "ventas.csv").exists():
        pytest.skip("Faltan los CSV: python preparar_datos.py")
    for t in TABLAS:
        with open(DATOS / f"{t.nombre}.csv", encoding="utf-8") as f:
            cabecera = next(csv.reader(f))
        # Power Query lee las columnas por nombre, así que el orden da igual.
        assert sorted(cabecera) == sorted(c.nombre for c in t.columnas), t.nombre


def test_generar_es_reproducible(tmp_path):
    generar(tmp_path / "a")
    generar(tmp_path / "b")
    archivos_a = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    archivos_b = sorted(p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*") if p.is_file())
    assert archivos_a == archivos_b
    for rel in archivos_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()


def test_proyecto_publicado_coincide_con_el_generador(tmp_path):
    """Los archivos de powerbi/ están al día con modelo.py e informe.py."""
    generar(tmp_path)
    for p in tmp_path.rglob("*"):
        if p.is_file():
            publicado = CARPETA / p.relative_to(tmp_path)
            assert publicado.exists(), publicado
            assert publicado.read_bytes() == p.read_bytes(), f"{publicado} desactualizado: python generar_pbip.py"


def test_json_del_informe_es_valido():
    for p in (CARPETA / f"{NOMBRE}.Report").rglob("*.json"):
        json.loads(p.read_text(encoding="utf-8"))
