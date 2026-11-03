"""Carga el paquete de datos del PIA de CleanPro (datos/cleanpro/*.csv) en objetos de dominio."""
import csv
from decimal import Decimal
from pathlib import Path

from src.cleanpro.dominio import Cliente, Linea, Servicio, ServicioCatalogo

DATOS = Path(__file__).resolve().parents[2] / "datos" / "cleanpro"


def _filas(nombre, carpeta=DATOS):
    with (Path(carpeta) / nombre).open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def cargar_servicios(carpeta=DATOS) -> dict[str, Servicio]:
    """Devuelve las 60 solicitudes del paquete, todas en estado SOLICITADO."""
    clientes = {
        f["actor_id"]: Cliente(f["actor_id"], f["activo"] == "1", f["es_preferente"] == "1")
        for f in _filas("actores.csv", carpeta)
    }
    catalogo = {
        f["recurso_id"]: ServicioCatalogo(
            f["recurso_id"], f["descripcion"], Decimal(f["precio_mxn"]), f["habilitado"] == "1"
        )
        for f in _filas("catalogo.csv", carpeta)
    }
    servicios = {
        f["operacion_id"]: Servicio(
            id=f["operacion_id"],
            cliente=clientes[f["actor_id"]],
            cotizacion_aceptada=f["autorizado"] == "1",
        )
        for f in _filas("operaciones.csv", carpeta)
    }
    for f in _filas("detalle_operaciones.csv", carpeta):
        servicios[f["operacion_id"]].lineas.append(
            Linea(catalogo[f["recurso_id"]], int(f["cantidad"]))
        )
    return servicios
