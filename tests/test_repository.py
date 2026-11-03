import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain import Order
from src.repository import OrderRow, SqlOrderRepository, make_engine


def test_repository_commit():
    engine = make_engine()
    with Session(engine) as session:
        SqlOrderRepository(session).save(1, Order(120))
        session.commit()
        assert session.scalar(select(OrderRow).where(OrderRow.id == 1)).total == 120
    engine.dispose()  # agregado: cierra la conexión de la base en memoria


def test_repository_rollback():
    engine = make_engine()
    with Session(engine) as session:
        SqlOrderRepository(session).save(1, Order(120))
        session.rollback()
        assert session.scalar(select(OrderRow).where(OrderRow.id == 1)) is None
    engine.dispose()  # agregado: cierra la conexión de la base en memoria


# ---------------------------------------------------------------------------
# Pruebas agregadas por el equipo (E4)
# ---------------------------------------------------------------------------
def test_commit_pedido_250_id_2(session):
    SqlOrderRepository(session).save(2, Order(250))
    session.commit()
    row = session.scalar(select(OrderRow).where(OrderRow.id == 2))
    assert (row.id, row.total, row.status) == (2, 250, "NEW")


def test_rollback_no_borra_lo_ya_confirmado(session):
    repo = SqlOrderRepository(session)
    repo.save(1, Order(120))
    session.commit()
    repo.save(2, Order(250))
    session.rollback()
    ids = session.scalars(select(OrderRow.id)).all()
    assert ids == [1]


def test_id_repetido_viola_unicidad_y_se_deshace(session):
    repo = SqlOrderRepository(session)
    repo.save(1, Order(120))
    session.commit()
    repo.save(1, Order(999))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert session.scalar(select(OrderRow).where(OrderRow.id == 1)).total == 120
