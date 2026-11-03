from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from src.cleanpro.cargador import cargar_servicios
from src.cleanpro.repositorio import crear_engine
from src.repository import make_engine

# Fecha fija para que las pruebas de tiempo den siempre el mismo resultado.
AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session():
    """Base SQLite en memoria para el proyecto base: se crea y se destruye en cada prueba."""
    engine = make_engine()
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture
def servicios():
    """Carga nueva de las 60 solicitudes del paquete del PIA de CleanPro."""
    return cargar_servicios()


@pytest.fixture
def session_cleanpro():
    engine = crear_engine()
    with Session(engine) as s:
        yield s
    engine.dispose()
