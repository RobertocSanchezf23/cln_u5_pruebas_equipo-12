"""Dominio de CleanPro (PIA, Equipo 12): adaptación de tres reglas del BRD a Python.

Reglas del BRD que se implementan y prueban:
  R1  RB-02  El servicio solo se programa si el cliente aceptó la cotización.
             + precondiciones del paquete del PIA: cliente activo, al menos un servicio
               en el detalle y servicios del catálogo habilitados.
  R2  RB-07  Solo se factura un servicio terminado (COMPLETADO).
      RB-11  Si el cliente no permite el acceso tras 15 minutos de espera, el servicio
             queda NO_REALIZADO y se factura un cargo de cancelación del 50 %.
  R3  RB-12 / RB-14  Un cargo adicional debe estar autorizado antes de facturar.
      RB-15  Solo el coordinador puede autorizar cargos adicionales.

El dominio no importa SQLAlchemy ni servicios externos: se prueba sin base de datos.
Los importes usan Decimal (a diferencia del proyecto base, que usa float).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

CENTAVOS = Decimal("0.01")
MINUTOS_DE_ESPERA_POR_ACCESO = 15  # RB-11
PORCENTAJE_CANCELACION = Decimal("0.50")  # RB-11


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------
class ReglaDeNegocioError(Exception):
    """Una operación viola una regla del BRD de CleanPro."""

    def __init__(self, regla: str, mensaje: str):
        self.regla = regla
        super().__init__(f"{regla}: {mensaje}")


class ServicioNoProgramable(ReglaDeNegocioError):
    pass


class TransicionInvalida(ReglaDeNegocioError):
    pass


class FacturacionNoPermitida(ReglaDeNegocioError):
    pass


class AutorizacionDenegada(ReglaDeNegocioError):
    pass


# ---------------------------------------------------------------------------
# Value Objects y entidades sencillas
# ---------------------------------------------------------------------------
class Rol(str, Enum):
    COORDINADOR = "COORDINADOR"
    SUPERVISOR = "SUPERVISOR"
    ADMINISTRACION = "ADMINISTRACION"


class EstadoServicio(str, Enum):
    SOLICITADO = "SOLICITADO"
    PROGRAMADO = "PROGRAMADO"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADO = "COMPLETADO"
    NO_REALIZADO = "NO_REALIZADO"


@dataclass(frozen=True)
class Cliente:
    id: str
    activo: bool = True
    preferente: bool = False


@dataclass(frozen=True)
class ServicioCatalogo:
    id: str
    descripcion: str
    precio: Decimal
    habilitado: bool = True


@dataclass(frozen=True)
class Linea:
    servicio: ServicioCatalogo
    cantidad: int

    def __post_init__(self):
        if self.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")

    @property
    def subtotal(self) -> Decimal:
        return self.servicio.precio * self.cantidad


@dataclass
class CargoAdicional:
    """Cargo por servicio adicional en sitio o material especial (RB-12, RB-14)."""

    descripcion: str
    monto: Decimal
    autorizado: bool = False

    def __post_init__(self):
        if self.monto <= 0:
            raise ValueError("El cargo adicional debe ser mayor que cero")


# ---------------------------------------------------------------------------
# Specifications de la regla R1 (programar)
# ---------------------------------------------------------------------------
class Especificacion:
    regla = ""
    motivo = ""

    def se_cumple(self, servicio: "Servicio") -> bool:
        raise NotImplementedError

    def __and__(self, otra: "Especificacion") -> "Especificacion":
        return _Y(self, otra)


class _Y(Especificacion):
    def __init__(self, izquierda: Especificacion, derecha: Especificacion):
        self.partes = [izquierda, derecha]

    def se_cumple(self, servicio):
        return all(p.se_cumple(servicio) for p in self.partes)

    def incumplidas(self, servicio):
        resultado = []
        for parte in self.partes:
            if isinstance(parte, _Y):
                resultado.extend(parte.incumplidas(servicio))
            elif not parte.se_cumple(servicio):
                resultado.append(parte)
        return resultado


class CotizacionAceptada(Especificacion):
    regla, motivo = "RB-02", "el cliente no ha aceptado la cotización"

    def se_cumple(self, servicio):
        return servicio.cotizacion_aceptada


class ClienteActivo(Especificacion):
    regla, motivo = "PIA-precondición", "el cliente está inactivo"

    def se_cumple(self, servicio):
        return servicio.cliente.activo


class TieneServicios(Especificacion):
    regla, motivo = "PIA-precondición", "la solicitud no tiene servicios en el detalle"

    def se_cumple(self, servicio):
        return len(servicio.lineas) > 0


class ServiciosHabilitados(Especificacion):
    regla, motivo = "PIA-precondición", "incluye un servicio deshabilitado en el catálogo"

    def se_cumple(self, servicio):
        return all(linea.servicio.habilitado for linea in servicio.lineas)


PUEDE_PROGRAMARSE = (
    CotizacionAceptada() & ClienteActivo() & TieneServicios() & ServiciosHabilitados()
)


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------
@dataclass
class Servicio:
    id: str
    cliente: Cliente
    cotizacion_aceptada: bool
    lineas: list[Linea] = field(default_factory=list)
    estado: EstadoServicio = EstadoServicio.SOLICITADO
    cargos: list[CargoAdicional] = field(default_factory=list)
    eventos: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((linea.subtotal for linea in self.lineas), Decimal("0.00"))

    # ----- R1: programar (RB-02 + precondiciones) --------------------------
    def programar(self) -> None:
        self._exigir_estado(EstadoServicio.SOLICITADO, "programar")
        fallas = PUEDE_PROGRAMARSE.incumplidas(self)
        if fallas:
            primera = fallas[0]
            raise ServicioNoProgramable(primera.regla, "no se puede programar: " + primera.motivo)
        self._cambiar_a(EstadoServicio.PROGRAMADO, "ServicioProgramado")

    def iniciar(self) -> None:
        self._exigir_estado(EstadoServicio.PROGRAMADO, "iniciar")
        self._cambiar_a(EstadoServicio.EN_PROCESO, "ServicioIniciado")

    def completar(self) -> None:
        self._exigir_estado(EstadoServicio.EN_PROCESO, "completar")
        self._cambiar_a(EstadoServicio.COMPLETADO, "ServicioCompletado")

    # ----- R2: acceso denegado (RB-11) ------------------------------------
    def registrar_acceso_denegado(self, minutos_espera: int) -> None:
        self._exigir_estado(EstadoServicio.PROGRAMADO, "registrar acceso denegado en")
        if minutos_espera < MINUTOS_DE_ESPERA_POR_ACCESO:
            raise TransicionInvalida(
                "RB-11",
                f"se debe esperar al menos {MINUTOS_DE_ESPERA_POR_ACCESO} minutos "
                f"(se esperaron {minutos_espera})",
            )
        self._cambiar_a(EstadoServicio.NO_REALIZADO, "ServicioNoRealizado")

    # ----- R3: cargos adicionales (RB-12, RB-14, RB-15) --------------------
    def registrar_cargo(self, descripcion: str, monto: Decimal) -> CargoAdicional:
        self._exigir_estado(EstadoServicio.EN_PROCESO, "registrar cargos en")
        cargo = CargoAdicional(descripcion, monto)
        self.cargos.append(cargo)
        self.eventos.append("CargoAdicionalRegistrado")
        return cargo

    def autorizar_cargo(self, cargo: CargoAdicional, rol: Rol) -> None:
        if rol != Rol.COORDINADOR:
            raise AutorizacionDenegada(
                "RB-15", f"solo el coordinador autoriza cargos adicionales (rol: {rol.value})"
            )
        if cargo not in self.cargos:
            raise ValueError("El cargo no pertenece a este servicio")
        cargo.autorizado = True
        self.eventos.append("CargoAdicionalAutorizado")

    # ----- R2 + R3: facturar ------------------------------------------------
    def calcular_factura(self) -> Decimal:
        if self.estado == EstadoServicio.NO_REALIZADO:
            return (self.total * PORCENTAJE_CANCELACION).quantize(CENTAVOS, ROUND_HALF_UP)
        if self.estado != EstadoServicio.COMPLETADO:
            raise FacturacionNoPermitida(
                "RB-07", f"solo se factura un servicio terminado (estado: {self.estado.value})"
            )
        if any(not c.autorizado for c in self.cargos):
            raise FacturacionNoPermitida("RB-14", "hay cargos adicionales sin autorizar")
        cargos = sum((c.monto for c in self.cargos), Decimal("0.00"))
        return (self.total + cargos).quantize(CENTAVOS, ROUND_HALF_UP)

    # ----- auxiliares -------------------------------------------------------
    def _exigir_estado(self, esperado: EstadoServicio, accion: str) -> None:
        if self.estado != esperado:
            raise TransicionInvalida(
                "Máquina de estados",
                f"no se puede {accion} un servicio en estado {self.estado.value}",
            )

    def _cambiar_a(self, nuevo: EstadoServicio, evento: str) -> None:
        self.estado = nuevo
        self.eventos.append(evento)
