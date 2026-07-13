"""
Scheduled polling orchestrator for the FullRays Indoor Wireless Twin.
Polls EIAP Topology & Inventory and Network Configuration (NCMP) directly
via OAuth, stores results in PostgreSQL, and detects state changes.
"""

import re
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .db.tables import Cell, CellStateSnapshot
from .mtls_logging import logger
from .network_configuration import get_attributes_for_source_ids
from .state_tracker import detect_changes
from .topology_and_inventory import get_nr_cell_dus, get_sourceids_from_cells

# Regex patterns for extracting fields from 3GPP DN URN strings
_CELL_NAME_RE = re.compile(r"NRCellDU=([^,]+)")
_NODE_NAME_RE = re.compile(r"MeContext=([^,]+)")
_SUBNET_RE = re.compile(r"SubNetwork=([^,]+)")


def _parse_cell_urn(urn: str) -> dict[str, str | None]:
    """Extract cell_name, node_name, and subnet from a 3GPP DN URN."""
    cell_match = _CELL_NAME_RE.search(urn)
    node_match = _NODE_NAME_RE.search(urn)
    subnet_matches = _SUBNET_RE.findall(urn)

    return {
        "cell_name": cell_match.group(1) if cell_match else None,
        "node_name": node_match.group(1) if node_match else None,
        "subnet": "/".join(subnet_matches) if subnet_matches else None,
    }


class SitePoller:
    """Periodically polls EIAP capabilities and stores results in PostgreSQL."""

    MISFIRE_GRACE_TIME = 60

    def __init__(
        self,
        async_oauth_client,
        session_factory: async_sessionmaker[AsyncSession],
        topology_interval_minutes: int = 60,
        config_interval_minutes: int = 5,
    ):
        self.oauth_client = async_oauth_client
        self.session_factory = session_factory
        self.topology_interval = topology_interval_minutes
        self.config_interval = config_interval_minutes
        self.scheduler = AsyncIOScheduler()
        self.last_poll_at: datetime | None = None

    async def poll_topology(self) -> None:
        """Fetch cells from Topology & Inventory and upsert into DB."""
        try:
            cells = await get_nr_cell_dus(self.oauth_client)
            source_ids = get_sourceids_from_cells(cells)
            now = datetime.now(timezone.utc)

            async with self.session_factory() as session:
                for urn in source_ids:
                    parsed = _parse_cell_urn(urn)

                    stmt = select(Cell).where(Cell.cell_urn == urn)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.last_seen_at = now
                        existing.cell_name = parsed["cell_name"]
                        existing.node_name = parsed["node_name"]
                        existing.subnet = parsed["subnet"]
                    else:
                        cell = Cell(
                            cell_urn=urn,
                            cell_name=parsed["cell_name"],
                            node_name=parsed["node_name"],
                            subnet=parsed["subnet"],
                            first_seen_at=now,
                            last_seen_at=now,
                        )
                        session.add(cell)

                await session.commit()
                logger.info(f"Topology poll: upserted {len(source_ids)} cells")

        except Exception as e:
            logger.error(f"Topology poll failed: {e}")

    async def poll_configuration(self) -> None:
        """Fetch cell states from NCMP, store snapshots, detect changes."""
        try:
            op_states = await get_attributes_for_source_ids(
                self.oauth_client, self._get_known_urns(), "operationalState"
            )
            admin_states = await get_attributes_for_source_ids(
                self.oauth_client, self._get_known_urns(), "administrativeState"
            )

            admin_map = {item["id"]: item.get("administrativeState") for item in admin_states}
            now = datetime.now(timezone.utc)

            async with self.session_factory() as session:
                for item in op_states:
                    cell_urn = item["id"]
                    op_state = item.get("operationalState")
                    adm_state = admin_map.get(cell_urn)

                    stmt = select(Cell).where(Cell.cell_urn == cell_urn)
                    result = await session.execute(stmt)
                    cell = result.scalar_one_or_none()

                    if not cell:
                        continue

                    snapshot = CellStateSnapshot(
                        cell_id=cell.id,
                        polled_at=now,
                        operational_state=op_state,
                        administrative_state=adm_state,
                        poll_success=True,
                    )
                    session.add(snapshot)
                    await session.flush()

                    await detect_changes(session, cell.id, op_state, adm_state, now)

                await session.commit()
                self.last_poll_at = now
                logger.info(f"Configuration poll: {len(op_states)} cells")

        except Exception as e:
            logger.error(f"Configuration poll failed: {e}")

    def _get_known_urns(self) -> list[str]:
        """Get URNs from the last topology poll (synchronous helper)."""
        # This will be populated after first topology poll via DB query
        # For now we do a sync approach - the poller caches them
        return getattr(self, "_cached_urns", [])

    async def _refresh_cached_urns(self):
        """Refresh the cached URN list from DB."""
        async with self.session_factory() as session:
            result = await session.execute(select(Cell.cell_urn))
            self._cached_urns = [row[0] for row in result.all()]

    async def poll_topology_and_refresh(self):
        """Poll topology then refresh the URN cache."""
        await self.poll_topology()
        await self._refresh_cached_urns()

    def start(self) -> None:
        """Start the polling scheduler."""
        self.scheduler.add_job(
            self.poll_topology_and_refresh,
            trigger="interval",
            minutes=self.topology_interval,
            misfire_grace_time=self.MISFIRE_GRACE_TIME,
            max_instances=1,
        )
        self.scheduler.add_job(
            self.poll_configuration,
            trigger="interval",
            minutes=self.config_interval,
            misfire_grace_time=self.MISFIRE_GRACE_TIME,
            max_instances=1,
        )
        self.scheduler.start()
        logger.info(
            f"Site poller started: topology every {self.topology_interval}m, "
            f"config every {self.config_interval}m"
        )

    def stop(self) -> None:
        """Shutdown the polling scheduler."""
        self.scheduler.shutdown()
        logger.info("Site poller stopped")
