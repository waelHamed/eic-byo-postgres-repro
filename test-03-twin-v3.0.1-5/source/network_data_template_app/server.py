"""
FastAPI Application for FullRays Indoor Wireless Twin rApp.
Monitors EIAP cell states, stores history in PostgreSQL, detects changes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_config
from .db.engine import init_db, dispose_db, get_session_factory
from .message_bus_consumer import MessageBusConsumer, start_message_bus_consumer
from .mtls_logging import logger
from .oauth import oauth, synchronous_oauth
from .poller import SitePoller
from .routes import api_router, healthcheck_router


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Async context manager for FastAPI application lifespan.
    Sets up database, OAuth, and site poller on startup.
    """
    await logger.start_log_sender()
    logger.info("Starting up FullRays Indoor Wireless Twin rApp...")

    config = get_config()

    # Initialize database
    await init_db(config["database_url"])
    session_factory = get_session_factory()

    # Initialize OAuth
    await oauth.setup_client()
    synchronous_oauth.setup_client()
    synchronous_client = synchronous_oauth.get_oauth_client()
    async_client = await oauth.get_oauth_client()

    # Start Kafka consumer for PM counter data
    message_bus_consumer = MessageBusConsumer(synchronous_client, async_client)
    consumer_task = await start_message_bus_consumer(message_bus_consumer)

    # Start site poller
    poller = SitePoller(
        async_oauth_client=async_client,
        session_factory=session_factory,
        topology_interval_minutes=int(config["topology_poll_interval"]),
        config_interval_minutes=int(config["config_poll_interval"]),
    )

    # Initial polls
    await poller.poll_topology_and_refresh()
    await poller.poll_configuration()
    poller.start()

    fastapi_app.state.poller = poller
    fastapi_app.state.is_ready = True
    logger.info("FullRays Indoor Wireless Twin rApp is now ready")

    yield

    fastapi_app.state.is_ready = False
    logger.info("FullRays Indoor Wireless Twin rApp is shutting down.")

    poller.stop()
    consumer_task.cancel()
    await oauth.close_client()
    synchronous_oauth.close_client()
    await dispose_db()


app = FastAPI(
    title="FullRays Indoor Wireless Twin rApp",
    description="Monitors EIAP cell states for indoor positioning sites, tracks changes, provides dashboard data.",
    version="3.0.1",
    license={
        "name": "COPYRIGHT FullRays 2026",
    },
    lifespan=lifespan,
    openapi_url=None,
)

app.state.is_ready = False

app.include_router(api_router)
app.include_router(healthcheck_router, prefix="/fullrays-twin/health")
