from datetime import datetime, timedelta, timezone

from src.security import can_cancel


def test_owner_within_24h():
    now = datetime.now(timezone.utc)
    assert can_cancel("NEW", 1, 1, False, now - timedelta(hours=1), now)

def test_stranger_denied():
    now = datetime.now(timezone.utc)
    assert not can_cancel("NEW", 1, 2, False, now, now)

def test_shipped_denied_even_admin():
    now = datetime.now(timezone.utc)
    assert not can_cancel("SHIPPED", 1, 1, True, now, now)

def test_expired_denied():
    now = datetime.now(timezone.utc)
    assert not can_cancel("NEW", 1, 1, False, now - timedelta(hours=25), now)


# ---------------------------------------------------------------------------
# Pruebas agregadas por el equipo (E6). Fechas fijas: el resultado no depende del reloj.
# ---------------------------------------------------------------------------
AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def test_admin_cancela_pedido_new_de_otro_usuario():
    assert can_cancel("NEW", 1, 2, True, AHORA - timedelta(hours=48), AHORA)


def test_propietario_exactamente_a_las_24h_se_rechaza():
    assert not can_cancel("NEW", 1, 1, False, AHORA - timedelta(hours=24), AHORA)


def test_propietario_un_segundo_antes_de_24h_se_permite():
    creado = AHORA - timedelta(hours=23, minutes=59, seconds=59)
    assert can_cancel("NEW", 1, 1, False, creado, AHORA)


def test_tercero_no_admin_dentro_de_24h_se_rechaza():
    assert not can_cancel("CONFIRMED", 1, 2, False, AHORA - timedelta(hours=1), AHORA)


def test_sin_now_usa_la_hora_actual():
    assert can_cancel("NEW", 1, 1, False, datetime.now(timezone.utc))
