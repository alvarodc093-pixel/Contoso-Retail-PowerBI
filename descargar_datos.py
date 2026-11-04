"""Descarga Contoso V2 (versión 100K, CSV) de SQLBI y lo deja en data/raw/.

Licencia MIT: https://github.com/sql-bi/Contoso-Data-Generator-V2-Data
Uso: python descargar_datos.py
"""

import io
import sys
import urllib.request
from pathlib import Path

import py7zr

URL = ("https://github.com/sql-bi/Contoso-Data-Generator-V2-Data/releases/download/"
       "ready-to-use-data/csv-100k.7z")
DESTINO = Path(__file__).parent / "data" / "raw"
ARCHIVOS = ["sales.csv", "product.csv", "customer.csv", "store.csv"]


def descargar(destino: Path = DESTINO) -> None:
    if all((destino / f).exists() for f in ARCHIVOS):
        print(f"Los datos ya están en {destino}")
        return
    destino.mkdir(parents=True, exist_ok=True)
    print("Descargando Contoso V2 100K (~10 MB)...")
    with urllib.request.urlopen(URL, timeout=120) as resp:
        contenido = resp.read()
    with py7zr.SevenZipFile(io.BytesIO(contenido)) as z:
        z.extract(path=destino, targets=ARCHIVOS)
    # Algunas versiones del archivo guardan los CSV dentro de una carpeta.
    for f in ARCHIVOS:
        if not (destino / f).exists():
            encontrado = next(destino.rglob(f))
            encontrado.replace(destino / f)
    print(f"Listo: {', '.join(ARCHIVOS)} en {destino}")


if __name__ == "__main__":
    try:
        descargar()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"No se pudo descargar el dataset: {e}")
