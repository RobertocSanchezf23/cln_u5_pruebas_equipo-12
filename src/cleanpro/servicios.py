"""Application Service de CleanPro: programar un servicio (CU-03, US-08 y US-03).

Coordina el dominio, el repositorio y el aviso al cliente. El notificador es un
puerto: en producción enviaría un correo o SMS; en las pruebas se sustituye por un mock.
"""
from typing import Protocol

from sqlalchemy.orm import Session

from src.cleanpro.dominio import Servicio
from src.cleanpro.repositorio import SqlServicioRepository


class NotificadorCliente(Protocol):
    def notificar_programacion(self, cliente_id: str, servicio_id: str) -> None: ...


class ProgramacionService:
    def __init__(self, session: Session, notificador: NotificadorCliente):
        self.session = session
        self.repositorio = SqlServicioRepository(session)
        self.notificador = notificador
        self.notificaciones_pendientes: list[str] = []

    def programar(self, servicio: Servicio) -> Servicio:
        servicio.programar()  # 1. el dominio valida RB-02 y las precondiciones
        self.repositorio.guardar(servicio)  # 2. se guarda dentro de la transacción
        self.session.commit()  # 3. se confirma antes de avisar al cliente
        try:
            self.notificador.notificar_programacion(servicio.cliente.id, servicio.id)
        except Exception:
            # Si falla el aviso, la programación sigue siendo válida: se reintenta después.
            self.notificaciones_pendientes.append(servicio.id)
        return servicio
