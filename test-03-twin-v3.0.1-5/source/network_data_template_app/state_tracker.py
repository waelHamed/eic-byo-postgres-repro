"""State change detection and querying logic."""

from datetime import datetime

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .db.tables import Cell, CellStateSnapshot, StateChangeEvent
from .mtls_logging import logger


async def detect_changes(
    session: AsyncSession,
    cell_id: int,
    current_operational: str | None,
    current_administrative: str | None,
    polled_at: datetime,
) -> list[StateChangeEvent]:
    """
    Compare current state against the most recent previous snapshot.
    Create StateChangeEvent records for any differences.
    """
    stmt = (
        select(CellStateSnapshot)
        .where(
            and_(
                CellStateSnapshot.cell_id == cell_id,
                CellStateSnapshot.polled_at < polled_at,
            )
        )
        .order_by(desc(CellStateSnapshot.polled_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    previous = result.scalar_one_or_none()

    events = []

    if previous is not None:
        if (
            current_operational is not None
            and previous.operational_state != current_operational
        ):
            event = StateChangeEvent(
                cell_id=cell_id,
                changed_at=polled_at,
                attribute_name="operationalState",
                old_value=previous.operational_state,
                new_value=current_operational,
            )
            session.add(event)
            events.append(event)
            logger.info(
                f"State change: cell_id={cell_id} operationalState "
                f"{previous.operational_state} -> {current_operational}"
            )

        if (
            current_administrative is not None
            and previous.administrative_state != current_administrative
        ):
            event = StateChangeEvent(
                cell_id=cell_id,
                changed_at=polled_at,
                attribute_name="administrativeState",
                old_value=previous.administrative_state,
                new_value=current_administrative,
            )
            session.add(event)
            events.append(event)
            logger.info(
                f"State change: cell_id={cell_id} administrativeState "
                f"{previous.administrative_state} -> {current_administrative}"
            )

    return events


async def get_latest_state_per_cell(session: AsyncSession) -> list[dict]:
    """Get the most recent state snapshot for every cell."""
    latest_sub = (
        select(
            CellStateSnapshot.cell_id,
            func.max(CellStateSnapshot.polled_at).label("max_polled_at"),
        )
        .group_by(CellStateSnapshot.cell_id)
        .subquery()
    )

    stmt = (
        select(Cell, CellStateSnapshot)
        .join(CellStateSnapshot, Cell.id == CellStateSnapshot.cell_id)
        .join(
            latest_sub,
            and_(
                CellStateSnapshot.cell_id == latest_sub.c.cell_id,
                CellStateSnapshot.polled_at == latest_sub.c.max_polled_at,
            ),
        )
        .order_by(Cell.cell_name)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "cell_urn": cell.cell_urn,
            "cell_name": cell.cell_name,
            "node_name": cell.node_name,
            "subnet": cell.subnet,
            "polled_at": snapshot.polled_at.isoformat(),
            "operational_state": snapshot.operational_state,
            "administrative_state": snapshot.administrative_state,
        }
        for cell, snapshot in rows
    ]


async def get_state_changes(
    session: AsyncSession,
    cell_urn: str | None = None,
    attribute: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Query state change events with optional filters."""
    conditions = []
    if cell_urn:
        conditions.append(Cell.cell_urn == cell_urn)
    if attribute:
        conditions.append(StateChangeEvent.attribute_name == attribute)
    if since:
        conditions.append(StateChangeEvent.changed_at >= since)
    if until:
        conditions.append(StateChangeEvent.changed_at <= until)

    count_stmt = (
        select(func.count(StateChangeEvent.id))
        .join(Cell, StateChangeEvent.cell_id == Cell.id)
    )
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await session.execute(count_stmt)).scalar_one()

    data_stmt = (
        select(StateChangeEvent, Cell)
        .join(Cell, StateChangeEvent.cell_id == Cell.id)
    )
    if conditions:
        data_stmt = data_stmt.where(and_(*conditions))
    data_stmt = (
        data_stmt.order_by(desc(StateChangeEvent.changed_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(data_stmt)).all()

    items = [
        {
            "cell_urn": cell.cell_urn,
            "cell_name": cell.cell_name,
            "changed_at": event.changed_at.isoformat(),
            "attribute_name": event.attribute_name,
            "old_value": event.old_value,
            "new_value": event.new_value,
        }
        for event, cell in rows
    ]

    return items, total
