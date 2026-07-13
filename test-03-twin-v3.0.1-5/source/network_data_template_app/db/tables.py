"""SQLAlchemy ORM table definitions for FullRays Indoor Wireless Twin."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Cell(Base):
    """Cell inventory discovered from EIAP Topology & Inventory."""

    __tablename__ = "cells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cell_urn: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    cell_name: Mapped[str | None] = mapped_column(String(255))
    node_name: Mapped[str | None] = mapped_column(String(255))
    subnet: Mapped[str | None] = mapped_column(String(255))
    cm_handle: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    snapshots: Mapped[list["CellStateSnapshot"]] = relationship(back_populates="cell")
    state_changes: Mapped[list["StateChangeEvent"]] = relationship(back_populates="cell")


class CellStateSnapshot(Base):
    """State snapshot -- one row per cell per poll cycle."""

    __tablename__ = "cell_state_snapshots"
    __table_args__ = (
        Index("idx_snapshots_cell_time", "cell_id", "polled_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cell_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cells.id"), nullable=False
    )
    polled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operational_state: Mapped[str | None] = mapped_column(String(50))
    administrative_state: Mapped[str | None] = mapped_column(String(50))
    poll_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    cell: Mapped["Cell"] = relationship(back_populates="snapshots")


class StateChangeEvent(Base):
    """Detected state transitions between consecutive snapshots."""

    __tablename__ = "state_change_events"
    __table_args__ = (
        Index("idx_events_cell_time", "cell_id", "changed_at"),
        Index("idx_events_time", "changed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cell_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cells.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attribute_name: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(50))
    new_value: Mapped[str] = mapped_column(String(50), nullable=False)

    cell: Mapped["Cell"] = relationship(back_populates="state_changes")
