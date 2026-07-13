"""Tests for the Twin rApp routes."""

from network_data_template_app.metrics import SERVICE_PREFIX


def test_get_dashboard(client):
    """GET /dashboard returns summary."""
    response = client.get("/fullrays-twin/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "total_cells" in data
    assert "enabled" in data
    assert "disabled" in data
    assert "recent_state_changes" in data


def test_get_cells(client):
    """GET /cells returns paginated list."""
    response = client.get("/fullrays-twin/cells")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_get_latest_states(client):
    """GET /cells/states/latest returns list."""
    response = client.get("/fullrays-twin/cells/states/latest")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_state_changes(client):
    """GET /events/state-changes returns paginated list."""
    response = client.get("/fullrays-twin/events/state-changes")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_get_metrics(client):
    """GET /metrics returns Prometheus metrics."""
    response = client.get("/fullrays-twin/metrics")
    assert response.status_code == 200
    assert f"{SERVICE_PREFIX}_topology_successful_requests_total" in response.text
    assert f"{SERVICE_PREFIX}_cells_monitored" in response.text


def test_metrics_no_created(client):
    """Metrics should not include _created gauges."""
    response = client.get("/fullrays-twin/metrics")
    assert response.status_code == 200
    assert "_created" not in response.text


def test_health_liveness(client):
    """GET /health/liveness returns 200."""
    response = client.get("/fullrays-twin/health/liveness")
    assert response.status_code == 200


def test_health_readiness(client):
    """GET /health/readiness returns 200."""
    response = client.get("/fullrays-twin/health/readiness")
    assert response.status_code == 200
