# Test 03 — FullRays Indoor Wireless Twin rApp v3.0.1-5

**Purpose:** deploy our own production rApp (fullrays-indoor-wireless-twin) using the same BYO-Postgres pattern. This was actually our FIRST failed attempt — motivating the reproduction with EIC's own sample in tests 01, 02, 04.

## Identity

| Field | Value |
| --- | --- |
| ALM app name | `fullrays-indoor-wireless-twin` |
| Version | `3.0.1-5` |
| App ID | `rapp-ericsson-fullrays-indoor-wireless-twin-3-0-1-5` |
| Instance ID (last DEPLOY_ERROR) | `rapp-ericsson-fullrays-indoor-wireless-twin-58949648` |

## Source

Full source in [source/](source/) — this is our production Twin rApp. Chart layout follows the EIC pattern:

- FastAPI backend (Python + SQLAlchemy async + asyncpg) — indoor wireless network digital twin
- Chart at `charts/fullrays-indoor-wireless-twin/`
- **`Chart.yaml`** adds `postgresql-ha 16.0.5` dep in the same way as the sample.
- **`values.yaml`** configures `postgresql-ha:` block with `fullnameOverride: "fullrays-twin-db"`, DB `twindb`, credentials `twin`/`twin`.
- **`templates/postgresql-secrets.yaml`** renders `<name>-postgresql-secret` and `<name>-pgpool-secret` (identical shape to the sample's template).
- **`templates/deployment/deployment.yaml`** sets `DATABASE_URL` env to `postgresql+asyncpg://twin:twin@fullrays-twin-db-pgpool:5432/twindb` (composed at render time from subchart values).

## Deploy params

See [deploy-body.json](deploy-body.json).

Key values (mirror the sample README pattern, adapted for Twin's app name):

- `postgresql-ha.global.imageRegistry`: `eic.stsn22p1eic08.stsoss.sero.xgic.ericsson.se/appmgr/images/rapp-ericsson-fullrays-indoor-wireless-twin-3-0-1-5`
- `postgresql-ha.global.imagePullSecrets`: `["hfe-generic-pull-secret"]`
- `postgresql-ha.global.security.allowInsecureImages`: `true`
- `postgresql-ha.global.postgresql.existingSecret`: `fullrays-indoor-wireless-twin-postgresql-secret`
- `postgresql-ha.global.pgpool.existingSecret`: `fullrays-indoor-wireless-twin-pgpool-secret`
- `postgresql-ha-credentials.postgresql.username` / `.password`: `twin` / `twin`

## Result

**DEPLOY_ERROR** — pgpool + postgresql-{0,1} all `ImagePullBackOff` after ~10 min. First occurrence of this failure mode, prior to the sample-based reproductions.

Full pod-level message:
```
Pod Name:less-twin-56665d7cff-gsx6w, Reason:CrashLoopBackOff    (main app image DID pull — crash is DB connection retry; expected)
Pod Name:fullrays-twin-db-pgpool-5d4b7489c-x7jwt, Reason:ImagePullBackOff
Pod Name:fullrays-twin-db-postgresql-0, Reason:ContainerCreating
Pod Name:fullrays-twin-db-postgresql-1, Reason:ContainerCreating
```

Full logs from earlier attempts not preserved for this iteration since the sample-based tests below reproduce the exact same issue more cleanly. Note however: the main app pod (`less-twin-...`) successfully pulled from `armdocker.rnd.ericsson.se/proj-eric-oss-drop/fullrays-indoor-wireless-twin:3.0.1-5` — proving `armdocker.rnd.ericsson.se` is reachable from cluster nodes with default credentials.
