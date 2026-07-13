"""Test configuration for FullRays Indoor Wireless Twin rApp."""

import json
import os
from unittest.mock import AsyncMock, patch
from urllib.parse import urljoin

import pytest
import pytest_asyncio
import respx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi.testclient import TestClient
from httpx import Response

from network_data_template_app.config import get_config
from network_data_template_app.metrics import metrics_registry
from network_data_template_app.mtls_logging import _MTLSLogger, _ConsoleLogger, Severity
from network_data_template_app.oauth import oauth
from network_data_template_app.server import app as test_app


def pytest_generate_tests():
    populate_environment_variables()


def reset_counters():
    for counter in metrics_registry.counters.values():
        counter.reset()


@pytest.fixture(name="mock_apis")
def fixture_mock_apis(config):
    """Setup mock APIs."""
    with respx.mock(assert_all_called=False) as respx_mock:
        login_url = urljoin(
            config.get("eic_host_url"),
            "/auth/realms/master/protocol/openid-connect/token",
        )
        respx_mock.post(login_url) % Response(
            status_code=200,
            json={
                "access_token": "test-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

        log_endpoint = f"https://{config.get('log_endpoint')}"
        respx_mock.post(log_endpoint)
        yield respx_mock


@pytest.fixture
def topology_api(mock_apis, config):
    """Mock the Topology & Inventory API."""
    topology_endpoint = (
        config.get("eic_host_url")
        + "/topology-inventory/v1alpha11/domains/RAN/entity-types/NRCellDU/entities"
    )
    with open("./tests/topology_response.json", "r", encoding="utf-8") as f:
        mock_apis.get(topology_endpoint) % Response(
            status_code=200, json=json.load(f)
        )


@pytest.fixture
def topology_not_ok_api(mock_apis, config):
    """Mock the Topology API returning 500."""
    topology_endpoint = (
        config.get("eic_host_url")
        + "/topology-inventory/v1alpha11/domains/RAN/entity-types/NRCellDU/entities"
    )
    mock_apis.get(topology_endpoint) % Response(status_code=500)


@pytest.fixture
def network_configuration_api(mock_apis, config):
    """Mock the NCMP API."""
    ncmp_endpoint = config.get("eic_host_url") + "/ncmp/v1/ch/"
    with open("./tests/topology_response.json", "r", encoding="utf-8") as f:
        topology_data = json.load(f)
    with open(
        "./tests/topology_get_nr_cell_dus_response.json", "r", encoding="utf-8"
    ) as f:
        cells_response = json.load(f)

    # Mock NCMP responses for each cell
    for source_id_data in cells_response:
        cm_handle = source_id_data.get("cmHandle", "")
        if cm_handle:
            url_pattern = f"{ncmp_endpoint}{cm_handle}"
            mock_apis.get(url=url_pattern) % Response(
                status_code=200,
                json=source_id_data.get("response", {}),
            )


@pytest.fixture
def network_configuration_not_ok_api(mock_apis, config):
    """Mock the NCMP API returning 500."""
    ncmp_endpoint = config.get("eic_host_url") + "/ncmp/v1/ch/"
    mock_apis.get(url__startswith=ncmp_endpoint) % Response(status_code=500)


@pytest.fixture
def config():
    """Return configuration."""
    return get_config()


@pytest.fixture
def no_log_certs():
    """Patch out mTLS certificate loading for tests."""
    with patch(
        "network_data_template_app.mtls_logging._MTLSLogger.__init__",
        return_value=None,
    ):
        yield


@pytest_asyncio.fixture
async def async_oauth_client(mock_apis, no_log_certs) -> AsyncOAuth2Client:
    """Create an async OAuth client for tests."""
    await oauth.setup_client()
    client = await oauth.get_oauth_client()
    yield client
    await oauth.close_client()


@pytest.fixture
def client(mock_apis, no_log_certs):
    """FastAPI test client with mocked dependencies."""
    reset_counters()
    with patch(
        "network_data_template_app.server.init_db",
        new_callable=AsyncMock,
    ), patch(
        "network_data_template_app.server.get_session_factory",
        return_value=AsyncMock(),
    ), patch(
        "network_data_template_app.server.SitePoller",
    ) as mock_poller_cls, patch(
        "network_data_template_app.server.dispose_db",
        new_callable=AsyncMock,
    ):
        mock_poller = AsyncMock()
        mock_poller.last_poll_at = None
        mock_poller_cls.return_value = mock_poller

        with TestClient(test_app) as c:
            yield c


def populate_environment_variables():
    """Populate environment variables for tests."""
    os.environ["EIC_HOST_URL"] = "https://www.eic-host-url.com"
    os.environ["CA_CERT_FILE_NAME"] = "CA_CERT_FILE_NAME"
    os.environ["CA_CERT_FILE_PATH"] = "CA_CERT_MOUNT_PATH"
    os.environ["LOG_ENDPOINT"] = "LOG_ENDPOINT"
    os.environ["APP_KEY"] = "APP_KEY"
    os.environ["APP_CERT"] = "APP_CERT"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
    os.environ["TOPOLOGY_POLL_INTERVAL_MIN"] = "60"
    os.environ["CONFIG_POLL_INTERVAL_MIN"] = "5"
