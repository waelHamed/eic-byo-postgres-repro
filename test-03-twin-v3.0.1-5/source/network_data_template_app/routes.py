"""
API routes for the FullRays Indoor Wireless Twin rApp.
Provides dashboard endpoints for cell status monitoring, state history,
and change detection.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi_healthchecks.api.router import HealthcheckRouter, Probe
from prometheus_client import generate_latest
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .db.engine import get_db
from .db.tables import Cell, CellStateSnapshot as CellStateSnapshotDB
from .health import SimpleHealthCheck
from .metrics import metrics_registry
from .mtls_logging import logger
from .state_tracker import get_latest_state_per_cell, get_state_changes

api_router = APIRouter(prefix="/fullrays-twin")

healthcheck_router = HealthcheckRouter(
    Probe(name="liveness", checks=[SimpleHealthCheck()]),
    Probe(name="readiness", checks=[SimpleHealthCheck()]),
)


# ─── Prometheus Metrics ───────────────────────────────────────────────

@api_router.get("/metrics", response_class=Response)
async def metrics():
    """Prometheus metrics in plaintext format."""
    return Response(generate_latest(metrics_registry), media_type="text/plain")


# ─── Dashboard Summary ───────────────────────────────────────────────

@api_router.get("/dashboard")
async def get_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Dashboard summary for FullRays Twin Desktop / rApp Dashboard.
    Returns cell counts, state breakdown, and recent changes.
    """
    latest = await get_latest_state_per_cell(db)

    total = len(latest)
    enabled = sum(1 for r in latest if r["operational_state"] == "ENABLED")
    disabled = sum(1 for r in latest if r["operational_state"] == "DISABLED")
    unknown = total - enabled - disabled

    recent_changes, _ = await get_state_changes(db, limit=10)

    poller = getattr(request.app.state, "poller", None)
    last_poll = poller.last_poll_at.isoformat() if poller and poller.last_poll_at else None

    return JSONResponse({
        "total_cells": total,
        "enabled": enabled,
        "disabled": disabled,
        "unknown": unknown,
        "last_poll_at": last_poll,
        "recent_state_changes": recent_changes,
    })


# ─── Cell Inventory ──────────────────────────────────────────────────

@api_router.get("/cells")
async def list_cells(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List all discovered cells with pagination."""
    count_result = await db.execute(select(func.count(Cell.id)))
    total = count_result.scalar_one()

    stmt = select(Cell).order_by(Cell.cell_name).offset(offset).limit(limit)
    result = await db.execute(stmt)
    cells = result.scalars().all()

    return JSONResponse({
        "items": [
            {
                "cell_urn": c.cell_urn,
                "cell_name": c.cell_name,
                "node_name": c.node_name,
                "subnet": c.subnet,
                "first_seen_at": c.first_seen_at.isoformat(),
                "last_seen_at": c.last_seen_at.isoformat(),
            }
            for c in cells
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    })


@api_router.get("/cells/states/latest")
async def get_latest_states(db: AsyncSession = Depends(get_db)):
    """Get the most recent state for every cell."""
    rows = await get_latest_state_per_cell(db)
    return JSONResponse(rows)


# ─── Cell State History ──────────────────────────────────────────────

@api_router.get("/cells/{cell_urn:path}/states")
async def get_cell_state_history(
    cell_urn: str,
    since: datetime | None = None,
    until: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get historical state snapshots for a specific cell."""
    cell_result = await db.execute(select(Cell).where(Cell.cell_urn == cell_urn))
    cell = cell_result.scalar_one_or_none()
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")

    conditions = [CellStateSnapshotDB.cell_id == cell.id]
    if since:
        conditions.append(CellStateSnapshotDB.polled_at >= since)
    if until:
        conditions.append(CellStateSnapshotDB.polled_at <= until)

    count_stmt = select(func.count(CellStateSnapshotDB.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        select(CellStateSnapshotDB)
        .where(*conditions)
        .order_by(desc(CellStateSnapshotDB.polled_at))
        .offset(offset)
        .limit(limit)
    )
    snapshots = (await db.execute(data_stmt)).scalars().all()

    return JSONResponse({
        "items": [
            {
                "cell_urn": cell.cell_urn,
                "cell_name": cell.cell_name,
                "polled_at": s.polled_at.isoformat(),
                "operational_state": s.operational_state,
                "administrative_state": s.administrative_state,
            }
            for s in snapshots
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    })


# ─── State Change Events ─────────────────────────────────────────────

@api_router.get("/events/state-changes")
async def list_state_changes(
    cell_urn: str | None = None,
    attribute: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List state change events with optional filters."""
    items, total = await get_state_changes(
        db, cell_urn=cell_urn, attribute=attribute,
        since=since, until=until, limit=limit, offset=offset,
    )
    return JSONResponse({
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    })
