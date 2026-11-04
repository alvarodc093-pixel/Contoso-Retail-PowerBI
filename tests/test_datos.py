"""Tests de la preparación de datos con un mini Contoso hecho a mano."""

import json

import pytest

import preparar_datos as pd_
from preparar_datos import construir, cifras_control

DATOS = pd_.SALIDA


@pytest.fixture(scope="module")
def con():
    import duckdb

    c = duckdb.connect()
    c.execute("""
    CREATE TABLE raw_ventas AS SELECT * FROM (VALUES
        (1, 0, DATE '2024-03-10', DATE '2024-03-12', 100, 10,     1, 2, 100.0, 90.0, 40.0, 'EUR', 0.9),
        (1, 1, DATE '2024-03-10', DATE '2024-03-12', 100, 10,     2, 1,  50.0, 50.0, 20.0, 'EUR', 0.9),
        (2, 0, DATE '2025-03-05', DATE '2025-03-09', 200, 999999, 1, 1, 100.0, 100.0, 40.0, 'USD', 1.0),
        (3, 0, DATE '2025-03-20', DATE '2025-03-20', 100, 10,     2, 4,  50.0, 45.0, 20.0, 'GBP', 0.8)
    ) t(OrderKey, LineNumber, OrderDate, DeliveryDate, CustomerKey, StoreKey, ProductKey,
        Quantity, UnitPrice, NetPrice, UnitCost, CurrencyCode, ExchangeRate);
    CREATE TABLE raw_productos AS SELECT * FROM (VALUES
        (1, 'TV 1', 'Contoso', 'Contoso, Ltd', 'Black', 100.0, 40.0, 2, 'TV and Video', 'Televisions'),
        (2, 'Radio 1', 'Litware', 'Litware, Inc.', 'Red', 50.0, 20.0, 1, 'Audio', 'Radio')
    ) t(ProductKey, ProductName, Brand, Manufacturer, Color, Price, Cost, CategoryKey, CategoryName, SubCategoryName);
    CREATE TABLE raw_clientes AS SELECT * FROM (VALUES
        (100, 'United States', 'North America', 'female', DATE '1990-01-01'),
        (200, 'Germany', 'Europe', 'male', DATE '1950-06-01'),
        (300, 'Italy', 'Europe', 'male', DATE '1980-01-01')
    ) t(CustomerKey, CountryFull, Continent, Gender, Birthday);
    CREATE TABLE raw_tiendas AS SELECT * FROM (VALUES
        (10, 'US', 'United States', 'Texas', DATE '2010-01-01', NULL, 500, NULL),
        (999999, '--', 'Online', 'Online', DATE '2010-01-01', NULL, NULL, NULL)
    ) t(StoreKey, CountryCode, CountryName, State, OpenDate, CloseDate, SquareMeters, Status);
    """)
    construir(c)
    yield c
    c.close()


def test_importes_en_usd_sin_tipo_de_cambio(con):
    # 2 x 90 + 1 x 50 = 230: el ExchangeRate no se aplica
    assert con.execute("SELECT SUM(cantidad * precio_neto) FROM ventas WHERE pedido_id = 1").fetchone()[0] == 230


def test_clientes_solo_los_que_compran_y_sin_datos_personales(con):
    ids = {r[0] for r in con.execute("SELECT cliente_id FROM clientes").fetchall()}
    assert ids == {100, 200}
    columnas = {r[0] for r in con.execute("DESCRIBE clientes").fetchall()}
    assert not columnas & {"nombre", "direccion", "GivenName", "StreetAddress"}


def test_tienda_online(con):
    canal, pais = con.execute("SELECT canal, pais FROM tiendas WHERE tienda_id = 999999").fetchone()
    assert (canal, pais) == ("Online", "Online")


def test_calendario_continuo_y_en_espanol(con):
    n, minimo, maximo = con.execute("SELECT COUNT(*), MIN(fecha), MAX(fecha) FROM calendario").fetchone()
    assert (maximo - minimo).days + 1 == n
    assert con.execute("SELECT mes, dia_semana FROM calendario WHERE fecha = DATE '2025-03-03'").fetchone() == ("mar", "lunes")


def test_objetivo_es_el_anio_anterior_mas_8(con):
    # Marzo 2024: TV (2 x 90 = 180) y Audio (50) -> objetivos de marzo 2025
    filas = dict(con.execute(
        "SELECT categoria_id, objetivo FROM objetivos WHERE fecha = DATE '2025-03-01'").fetchall())
    assert filas == {2: round(180 * 1.08, -2), 1: round(50 * 1.08, -2)}


def test_cifras_control(con):
    c = cifras_control(con)["2025"]
    assert c["ventas"] == 280          # 100 + 4 x 45
    assert c["pedidos"] == 2
    assert c["pct_online"] == pytest.approx(100 / 280, abs=1e-4)


@pytest.mark.skipif(not (DATOS / "cifras_control.json").exists(), reason="Faltan los datos preparados")
def test_cifras_reales_publicadas():
    cifras = json.loads((DATOS / "cifras_control.json").read_text(encoding="utf-8"))
    assert set(cifras) == {str(a) for a in range(2016, 2026)}
    assert cifras["2025"]["ventas"] == pytest.approx(29_277_489.59, abs=1)
    assert all(0.5 < c["margen_pct"] < 0.6 for c in cifras.values())
