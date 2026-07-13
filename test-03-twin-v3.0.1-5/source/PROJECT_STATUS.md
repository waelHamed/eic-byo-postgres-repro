# FullRays Indoor Wireless Twin rApp

## Overview

EIAP rApp that monitors cell states on the Ericsson platform, stores history in PostgreSQL, detects state changes, and provides dashboard data to the FullRays Twin Server API. Runs inside the Ericsson EIAP sandbox.

**Type:** EIAP rApp (deployed on Ericsson EIC)
**Communicates with:** FullRays Twin Server API (project 4)
**Directory:** `/fullrays-indoor-wireless-twin/`
**Base:** `eric-oss-network-data-template-app-3.0.1-0`

---

## Architecture

```
Ericsson EIAP Sandbox
+----------------------------------------------+
|  Topology & Inventory API                    |
|  Network Configuration (NCMP) API            |
+------------------+---------------------------+
                   |
                   v
+------------------+---------------------------+
|  Twin rApp (this project)                    |
|  - Polls topology + cell states              |
|  - Stores history in PostgreSQL              |
|  - Detects state changes                     |
|  - Serves dashboard data via REST            |
+------------------+---------------------------+
                   |
                   v (REST API)
+------------------+---------------------------+
|  FullRays Twin Server API (project 4)        |
|  - Powers FullRays Twin Desktop              |
|  - KPI visualization                         |
|  - State change notifications                |
+----------------------------------------------+
```

---

## What Has Been Done

- [x] Scaffolded from Ericsson template, renamed via `set_rapp_name.sh`
- [x] Removed Kafka/PM counter modules (not needed for status monitoring)
- [x] PostgreSQL database layer:
  - `db/tables.py` - Cell, CellStateSnapshot, StateChangeEvent
  - `db/engine.py` - Async SQLAlchemy engine + session factory
- [x] `SitePoller` - periodic EIAP polling:
  - Topology poll: discovers cells, parses 3GPP DN URNs, upserts to DB
  - Configuration poll: fetches operational/administrative states, stores snapshots
  - State change detection on every poll cycle
- [x] `StateTracker` - compares consecutive snapshots, creates change events
- [x] REST API endpoints:
  - `GET /fullrays-twin/dashboard` - Cell counts, state breakdown, recent changes
  - `GET /fullrays-twin/cells` - Paginated cell inventory
  - `GET /fullrays-twin/cells/states/latest` - Latest state per cell
  - `GET /fullrays-twin/cells/{urn}/states` - Historical states (with since/until)
  - `GET /fullrays-twin/events/state-changes` - Filterable state change events
- [x] EIAP integration: OAuth2, mTLS logging, Topology API, NCMP API
- [x] Helm chart: removed Kafka volumes, added DATABASE_URL, PostgreSQL config
- [x] CSAR: removed DataManagement component, kept SecurityManagement, reduced roles
- [x] Prometheus metrics: topology/NCMP counters + `cells_monitored` gauge
- [x] Requirements: sqlalchemy + asyncpg (no confluent-kafka)
- [x] Tests: state tracker with SQLite in-memory, route endpoint tests

---

## What Is Missing

| Item | Priority | Status | Notes |
|------|----------|--------|-------|
| FullRays Server communication | High | Not started | Push state changes to FullRays Twin Server API (project 4) |
| PostgreSQL Helm subchart | High | Not started | Bundle PostgreSQL as Helm dependency for EIAP deployment |
| KPI definitions | Medium | Not started | Define what KPIs to track for monitored sites |
| Docker build & push | High | Not started | Build, tag, push to `armdocker.rnd.ericsson.se` |
| CSAR generation | High | Not started | Run App Package Tool |
| Onboard & deploy to EIC | High | Not started | Full lifecycle |
| Run pytest | Medium | Not started | Verify all tests pass locally |

---

## Database Schema

```
cells
  id, cell_urn (unique), cell_name, node_name, subnet, cm_handle,
  first_seen_at, last_seen_at

cell_state_snapshots
  id, cell_id (FK), polled_at, operational_state, administrative_state, poll_success
  Index: (cell_id, polled_at)

state_change_events
  id, cell_id (FK), changed_at, attribute_name, old_value, new_value
  Index: (cell_id, changed_at), (changed_at)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `network_data_template_app/server.py` | FastAPI app + lifespan (DB + poller init) |
| `network_data_template_app/routes.py` | Dashboard/monitoring API endpoints |
| `network_data_template_app/poller.py` | SitePoller - periodic EIAP polling |
| `network_data_template_app/state_tracker.py` | State change detection + queries |
| `network_data_template_app/db/tables.py` | ORM models |
| `network_data_template_app/db/engine.py` | Async engine + session management |
| `charts/fullrays-indoor-wireless-twin/` | Helm chart (with PostgreSQL config) |
| `csar/` | CSAR packaging (no DataManagement) |
