"""Persistencia de servicios de CleanPro con SQLAlchemy (adaptador de infraestructura)."""
from decimal import Decimal

from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from src.cleanpro.dominio import Servicio


class Base(DeclarativeBase):
    pass


class ServicioRow(Base):
    __tablename__ = "servicios"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String, nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False)
    # Se guarda en centavos (entero) para no perder exactitud en SQLite.
    total_centavos: Mapped[int] = mapped_column(Integer, nullable=False)

    @property
    def total(self) -> Decimal:
        return Decimal(self.total_centavos) / 100


class SqlServicioRepository:
    def __init__(self, session: Session):
        self.session = session

    def guardar(self, servicio: Servicio) -> None:
        self.session.merge(
            ServicioRow(
                id=servicio.id,
                cliente_id=servicio.cliente.id,
                estado=servicio.estado.value,
                total_centavos=int(servicio.total * 100),
            )
        )

    def obtener(self, servicio_id: str) -> ServicioRow | None:
        return self.session.scalar(select(ServicioRow).where(ServicioRow.id == servicio_id))


def crear_engine(url="sqlite+pysqlite:///:memory:"):
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine
