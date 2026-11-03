"""Genera las matrices de pruebas (resultado esperado contra resultado real) en docs/.

Ejecuta cada caso contra el código actual y escribe:
  docs/matriz_pruebas.csv       CP01-CP15 del proyecto base (casos_de_prueba.csv)
  docs/matriz_autorizacion.csv  política de cancelación (src/security.py)
  docs/matriz_cleanpro.csv      adaptación al PIA de CleanPro (3 reglas del BRD)

Uso:  python generar_matrices.py
"""
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application import OrderService
from src.cleanpro.cargador import cargar_servicios
from src.cleanpro.dominio import Rol
from src.cleanpro.repositorio import SqlServicioRepository, crear_engine
from src.cleanpro.servicios import ProgramacionService
from src.domain import Order
from src.repository import OrderRow, SqlOrderRepository, make_engine
from src.security import can_cancel

RAIZ = Path(__file__).resolve().parent
DOCS = RAIZ / "docs"


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def escribir(nombre, filas):
    DOCS.mkdir(exist_ok=True)
    with (DOCS / nombre).open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    pasan = sum(f["estado"] == "PASA" for f in filas)
    print(f"{nombre}: {pasan}/{len(filas)} casos PASA")


def resultado(funcion):
    """Ejecuta un caso y devuelve el resultado real como texto."""
    try:
        return funcion()
    except Exception as exc:  # el nombre de la excepción es el resultado real
        return f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Proyecto base: CP01-CP15
# ---------------------------------------------------------------------------
TIPO = {
    "CP01": "Éxito", "CP02": "Éxito", "CP06": "Éxito", "CP09": "Éxito", "CP10": "Éxito",
    "CP14": "Éxito", "CP03": "Error", "CP05": "Error", "CP08": "Error", "CP11": "Error",
    "CP13": "Error", "CP15": "Error", "CP04": "Límite", "CP07": "Límite", "CP12": "Límite",
}
PRUEBA = {
    "CP13": "test_service.py::test_gateway_rejected",
    "CP14": "test_repository.py::test_repository_commit",
    "CP15": "test_repository.py::test_repository_rollback",
}


def caso_confirmar(pedido):
    order = Order(float(pedido["total"]), pedido["es_vip"] == "1", pedido["estado_inicial"])
    cobro = order.confirm(customer_debt=float(pedido["deuda_cliente"]))
    return f"{order.status}, cobro {cobro:.2f}"


def caso_pago_rechazado():
    gateway = Mock()
    gateway.charge.return_value = False
    OrderService(gateway).checkout(Order(100))
    return "cobro aprobado"


def caso_persistencia(hacer_commit):
    engine = make_engine()
    with Session(engine) as session:
        SqlOrderRepository(session).save(1, Order(120))
        session.commit() if hacer_commit else session.rollback()
        fila = session.scalar(select(OrderRow).where(OrderRow.id == 1))
    engine.dispose()
    return "Registro visible después de commit" if fila else "Registro ausente después de rollback"


def matriz_base():
    pedidos = {p["pedido_id"]: p for p in leer(RAIZ / "datos" / "pedidos_prueba.csv")}
    filas = []
    for caso in leer(RAIZ / "datos" / "casos_de_prueba.csv"):
        cid, accion = caso["caso_id"], caso["accion"]
        esperado = caso["resultado_esperado"]
        if accion == "confirmar":
            p = pedidos[caso["pedido_id"]]
            entrada = (f"total={p['total']}, vip={p['es_vip']}, deuda={p['deuda_cliente']}, "
                       f"estado={p['estado_inicial']}")
            real = resultado(lambda p=p: caso_confirmar(p))
            if "TDD" in caso["nota"]:
                esperado = "OrderAlreadyConfirmed (ValueError): already confirmed"
            prueba = f"test_casos_csv.py::test_caso_del_csv[{cid}]"
        elif accion == "pago rechazado":
            entrada, real = "Order(100), mock charge -> False", resultado(caso_pago_rechazado)
            prueba = PRUEBA[cid]
        else:
            commit = "commit" in accion
            entrada = f"save(1, Order(120)) + {'commit' if commit else 'rollback'}"
            real, prueba = caso_persistencia(commit), PRUEBA[cid]
        if esperado.startswith("CONFIRMED, cobro"):
            pasa = real == esperado
        elif "TDD" in caso["nota"]:
            pasa = real == "OrderAlreadyConfirmed: already confirmed"
        else:
            pasa = real.startswith(esperado.split(":")[0])
        filas.append({
            "caso_id": cid, "pedido_id": caso["pedido_id"], "accion": accion, "entrada": entrada,
            "tipo": TIPO[cid], "resultado_esperado": esperado, "resultado_real": real,
            "estado": "PASA" if pasa else "FALLA", "prueba": prueba,
        })
    return filas


# ---------------------------------------------------------------------------
# Matriz de autorización (E6)
# ---------------------------------------------------------------------------
def matriz_autorizacion():
    ahora = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    casos = [
        ("Propietario", "Sí", "NEW", timedelta(hours=1), True, "test_owner_within_24h"),
        ("Tercero", "No", "NEW", timedelta(0), False, "test_stranger_denied"),
        ("Administrador", "Sí", "SHIPPED", timedelta(0), False, "test_shipped_denied_even_admin"),
        ("Propietario", "Sí", "NEW", timedelta(hours=25), False, "test_expired_denied"),
        ("Administrador", "No", "NEW", timedelta(hours=48), True,
         "test_admin_cancela_pedido_new_de_otro_usuario"),
        ("Propietario", "Sí", "NEW", timedelta(hours=24), False,
         "test_propietario_exactamente_a_las_24h_se_rechaza"),
        ("Propietario", "Sí", "NEW", timedelta(hours=23, minutes=59, seconds=59), True,
         "test_propietario_un_segundo_antes_de_24h_se_permite"),
        ("Tercero", "No", "CONFIRMED", timedelta(hours=1), False,
         "test_tercero_no_admin_dentro_de_24h_se_rechaza"),
    ]
    filas = []
    for rol, propietario, estado, antiguedad, esperado, prueba in casos:
        user = 1 if propietario == "Sí" else 2
        real = can_cancel(estado, 1, user, rol == "Administrador", ahora - antiguedad, ahora)
        horas, resto = divmod(int(antiguedad.total_seconds()), 3600)
        minutos, segundos = divmod(resto, 60)
        texto = f"{horas} h" + (f" {minutos} min {segundos} s" if resto else "")
        filas.append({
            "rol": rol, "es_propietario": propietario, "estado_pedido": estado,
            "antiguedad": texto, "esperado": "Permitido" if esperado else "Denegado",
            "real": "Permitido" if real else "Denegado",
            "estado": "PASA" if real == esperado else "FALLA", "prueba": prueba,
        })
    return filas


# ---------------------------------------------------------------------------
# Adaptación al PIA de CleanPro (E9)
# ---------------------------------------------------------------------------
def cleanpro(sid, *pasos):
    servicio = cargar_servicios()[sid]
    for paso in pasos:
        paso(servicio)
    return servicio


def en_proceso(s):
    s.programar()
    s.iniciar()


def con_cargo(monto, rol=None):
    def paso(s):
        cargo = s.registrar_cargo("cargo", Decimal(monto))
        if rol:
            s.autorizar_cargo(cargo, rol)
    return paso


def rollback_cleanpro():
    engine = crear_engine()
    with Session(engine) as session:
        repo = SqlServicioRepository(session)
        repo.guardar(cargar_servicios()["CLN-O002"])
        session.rollback()
        texto = "guardado" if repo.obtener("CLN-O002") else "no guardado tras rollback"
    engine.dispose()
    return texto


def matriz_cleanpro():
    def programado(sid):
        return f"{cleanpro(sid, lambda s: s.programar()).estado.value}"

    def factura(sid, *pasos):
        return f"Factura {cleanpro(sid, *pasos).calcular_factura()}"

    def integracion(sid, falla_aviso=False):
        engine = crear_engine()
        notificador = Mock()
        if falla_aviso:
            notificador.notificar_programacion.side_effect = TimeoutError("SMS no disponible")
        with Session(engine) as session:
            servicio = SqlServicioRepository(session)
            app = ProgramacionService(session, notificador)
            try:
                app.programar(cargar_servicios()[sid])
            except Exception as exc:
                texto = f"{type(exc).__name__}; guardado={servicio.obtener(sid) is not None}"
            else:
                texto = (f"{servicio.obtener(sid).estado} guardado; avisos="
                         f"{notificador.notificar_programacion.call_count}; "
                         f"pendientes={len(app.notificaciones_pendientes)}")
        engine.dispose()
        return texto

    completar = [lambda s: s.programar(), lambda s: s.iniciar(), lambda s: s.completar()]
    casos = [
        ("CLN-CP01", "R1 RB-02", "CLN-O001", "Cliente activo, cotización aceptada, 2 servicios",
         "Éxito", "PROGRAMADO", lambda: programado("CLN-O001")),
        ("CLN-CP02", "R1 RB-02", "CLN-O008", "Cotización no aceptada (autorizado=0)", "Error",
         "ServicioNoProgramable", lambda: programado("CLN-O008")),
        ("CLN-CP03", "R1 precondición", "CLN-O022", "Cliente C007 inactivo", "Error",
         "ServicioNoProgramable", lambda: programado("CLN-O022")),
        ("CLN-CP04", "R1 precondición", "CLN-O013", "Solicitud con 0 servicios", "Límite",
         "ServicioNoProgramable", lambda: programado("CLN-O013")),
        ("CLN-CP05", "R1 precondición", "CLN-O005", "Incluye P011 deshabilitado", "Error",
         "ServicioNoProgramable", lambda: programado("CLN-O005")),
        ("CLN-CP06", "R2 RB-07", "CLN-O006", "Programar, iniciar y completar", "Éxito",
         "Factura 2840.00", lambda: factura("CLN-O006", *completar)),
        ("CLN-CP07", "R2 RB-07", "CLN-O007", "Facturar estando PROGRAMADO", "Error",
         "FacturacionNoPermitida", lambda: factura("CLN-O007", lambda s: s.programar())),
        ("CLN-CP08", "R2 RB-11", "CLN-O003", "Acceso denegado tras 15 min (1,491.00)", "Límite",
         "Factura 745.50", lambda: factura("CLN-O003", lambda s: s.programar(),
                                           lambda s: s.registrar_acceso_denegado(15))),
        ("CLN-CP09", "R2 RB-11", "CLN-O004", "Acceso denegado tras 14 min", "Límite",
         "TransicionInvalida", lambda: factura("CLN-O004", lambda s: s.programar(),
                                               lambda s: s.registrar_acceso_denegado(14))),
        ("CLN-CP10", "R3 RB-14", "CLN-O010", "Cargo 350.00 autorizado por coordinador",
         "Éxito", "Factura 7095.00",
         lambda: factura("CLN-O010", en_proceso, con_cargo("350.00", Rol.COORDINADOR),
                         lambda s: s.completar())),
        ("CLN-CP11", "R3 RB-14", "CLN-O011", "Cargo 500.00 sin autorizar", "Error",
         "FacturacionNoPermitida",
         lambda: factura("CLN-O011", en_proceso, con_cargo("500.00"), lambda s: s.completar())),
        ("CLN-CP12", "R3 RB-15", "CLN-O012", "Supervisor intenta autorizar cargo", "Error",
         "AutorizacionDenegada",
         lambda: factura("CLN-O012", en_proceso, con_cargo("200.00", Rol.SUPERVISOR))),
        ("CLN-CP13", "R3 RB-14", "CLN-O014", "Cargo de 0.01 sin autorizar", "Límite",
         "FacturacionNoPermitida",
         lambda: factura("CLN-O014", en_proceso, con_cargo("0.01"), lambda s: s.completar())),
        ("CLN-CP14", "Persistencia", "CLN-O001", "Programar y hacer commit", "Integración",
         "PROGRAMADO guardado", lambda: integracion("CLN-O001")),
        ("CLN-CP15", "Persistencia", "CLN-O002", "Guardar y hacer rollback", "Integración",
         "no guardado", rollback_cleanpro),
        ("CLN-CP16", "Mock notificador", "CLN-O001", "Aviso al cliente al programar",
         "Integración", "avisos=1", lambda: integracion("CLN-O001")),
        ("CLN-CP17", "Mock notificador", "CLN-O008", "Regla falla: no guarda ni avisa",
         "Integración", "ServicioNoProgramable; guardado=False", lambda: integracion("CLN-O008")),
        ("CLN-CP18", "Mock notificador", "CLN-O006", "Falla el aviso (timeout)", "Integración",
         "pendientes=1", lambda: integracion("CLN-O006", falla_aviso=True)),
    ]
    filas = []
    for cid, regla, sid, entrada, tipo, esperado, funcion in casos:
        real = resultado(funcion)
        filas.append({
            "caso_id": cid, "regla": regla, "servicio": sid, "entrada": entrada, "tipo": tipo,
            "resultado_esperado": esperado, "resultado_real": real,
            "estado": "PASA" if esperado in real else "FALLA",
        })
    return filas


if __name__ == "__main__":
    escribir("matriz_pruebas.csv", matriz_base())
    escribir("matriz_autorizacion.csv", matriz_autorizacion())
    escribir("matriz_cleanpro.csv", matriz_cleanpro())
