"""PIA CleanPro - integración: persistencia con SQLAlchemy y notificación con mock."""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.cleanpro.cargador import cargar_servicios
from src.cleanpro.dominio import EstadoServicio, ServicioNoProgramable
from src.cleanpro.repositorio import SqlServicioRepository
from src.cleanpro.servicios import ProgramacionService


def test_cln_cp14_commit_el_servicio_programado_queda_guardado(servicios, session_cleanpro):
    servicio = servicios["CLN-O001"]
    servicio.programar()
    SqlServicioRepository(session_cleanpro).guardar(servicio)
    session_cleanpro.commit()
    fila = SqlServicioRepository(session_cleanpro).obtener("CLN-O001")
    assert (fila.cliente_id, fila.estado, fila.total) == ("CLN-C020", "PROGRAMADO", Decimal("8875"))


def test_cln_cp15_rollback_el_servicio_no_queda_guardado(servicios, session_cleanpro):
    SqlServicioRepository(session_cleanpro).guardar(servicios["CLN-O002"])
    session_cleanpro.rollback()
    assert SqlServicioRepository(session_cleanpro).obtener("CLN-O002") is None


def test_cln_cp16_mock_notifica_al_cliente_una_vez(servicios, session_cleanpro):
    notificador = Mock()
    ProgramacionService(session_cleanpro, notificador).programar(servicios["CLN-O001"])
    notificador.notificar_programacion.assert_called_once_with("CLN-C020", "CLN-O001")


def test_cln_cp17_si_la_regla_falla_no_se_guarda_ni_se_notifica(servicios, session_cleanpro):
    notificador = Mock()
    with pytest.raises(ServicioNoProgramable):
        ProgramacionService(session_cleanpro, notificador).programar(servicios["CLN-O008"])
    notificador.notificar_programacion.assert_not_called()
    assert SqlServicioRepository(session_cleanpro).obtener("CLN-O008") is None


def test_cln_cp18_si_falla_el_aviso_el_servicio_sigue_programado(servicios, session_cleanpro):
    notificador = Mock()
    notificador.notificar_programacion.side_effect = TimeoutError("SMS no disponible")
    service = ProgramacionService(session_cleanpro, notificador)
    servicio = service.programar(servicios["CLN-O006"])
    assert servicio.estado == EstadoServicio.PROGRAMADO
    assert SqlServicioRepository(session_cleanpro).obtener("CLN-O006").estado == "PROGRAMADO"
    assert service.notificaciones_pendientes == ["CLN-O006"]


def test_el_paquete_tiene_60_solicitudes_en_solicitado():
    servicios = cargar_servicios()
    assert len(servicios) == 60
    assert {s.estado for s in servicios.values()} == {EstadoServicio.SOLICITADO}
