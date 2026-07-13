"""Tests for state change detection logic."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from network_data_template_app.db.tables import Base, Cell, CellStateSnapshot
from network_data_template_app.state_tracker import detect_changes, get_latest_state_per_cell


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_no_previous_snapshot_no_events(db_session):
    """First snapshot for a cell should not produce any change events."""
    cell = Cell(cell_urn="urn:test:cell1", cell_name="Cell1",
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc))
    db_session.add(cell)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    snapshot = CellStateSnapshot(
        cell_id=cell.id, polled_at=now,
        operational_state="ENABLED", administrative_state="UNLOCKED",
    )
    db_session.add(snapshot)
    await db_session.flush()

    events = await detect_changes(db_session, cell.id, "ENABLED", "UNLOCKED", now)
    assert len(events) == 0


@pytest.mark.asyncio
async def test_operational_state_change_detected(db_session):
    """A change in operational_state should produce one event."""
    cell = Cell(cell_urn="urn:test:cell2", cell_name="Cell2",
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc))
    db_session.add(cell)
    await db_session.flush()

    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    s1 = CellStateSnapshot(
        cell_id=cell.id, polled_at=t1,
        operational_state="ENABLED", administrative_state="UNLOCKED",
    )
    db_session.add(s1)
    await db_session.flush()

    t2 = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    events = await detect_changes(db_session, cell.id, "DISABLED", "UNLOCKED", t2)
    assert len(events) == 1
    assert events[0].attribute_name == "operationalState"
    assert events[0].old_value == "ENABLED"
    assert events[0].new_value == "DISABLED"


@pytest.mark.asyncio
async def test_same_state_no_events(db_session):
    """No change in state should produce zero events."""
    cell = Cell(cell_urn="urn:test:cell3", cell_name="Cell3",
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc))
    db_session.add(cell)
    await db_session.flush()

    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    s1 = CellStateSnapshot(
        cell_id=cell.id, polled_at=t1,
        operational_state="ENABLED", administrative_state="UNLOCKED",
    )
    db_session.add(s1)
    await db_session.flush()

    t2 = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    events = await detect_changes(db_session, cell.id, "ENABLED", "UNLOCKED", t2)
    assert len(events) == 0


@pytest.mark.asyncio
async def test_get_latest_state_per_cell(db_session):
    """Should return most recent snapshot per cell."""
    cell = Cell(cell_urn="urn:test:cell4", cell_name="Cell4",
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc))
    db_session.add(cell)
    await db_session.flush()

    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    db_session.add(CellStateSnapshot(
        cell_id=cell.id, polled_at=t1,
        operational_state="ENABLED", administrative_state="UNLOCKED",
    ))
    db_session.add(CellStateSnapshot(
        cell_id=cell.id, polled_at=t2,
        operational_state="DISABLED", administrative_state="LOCKED",
    ))
    await db_session.flush()

    rows = await get_latest_state_per_cell(db_session)
    assert len(rows) == 1
    assert rows[0]["operational_state"] == "DISABLED"
    assert rows[0]["administrative_state"] == "LOCKED"
