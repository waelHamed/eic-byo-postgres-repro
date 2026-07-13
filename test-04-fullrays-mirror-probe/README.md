# Test 04 — `fullrays-mirror-probe` @ 3.2.2-0 (distinctive rebuild, fully aligned)

**Purpose:** eliminate any lingering doubt about naming or Helm-state as a cause. Fresh CSAR with a distinctive new app identity AND with the Docker image name aligned to the app name (which the sample's build script does NOT do — see notes below).

## Identity

| Field | Value |
| --- | --- |
| ALM app name | `fullrays-mirror-probe` |
| Chart name | `fullrays-mirror-probe` (Chart.yaml `name:`) |
| Version | `3.2.2-0` |
| Built Docker image | `proj-eric-oss-drop/fullrays-mirror-probe:3.2.2-0` (was `proj-eric-oss-drop/eric-oss-hello-world-python-app:$VERSION` in the sample) |
| App ID | `rapp-ericsson-fullrays-mirror-probe-3-2-2-0` |
| Instance ID | `rapp-ericsson-fullrays-mirror-probe-86724860` |
| CSAR SHA256 | `cc1fcf0edd899188d61a609c9362fd0cb8de0f6aed520e5a69cca7aa05565ddf` |

## Source

Started from the same DevCon sample as test-01, with these changes on top of test-01's changes:

1. Renamed `fullrays-sample-db-test` → `fullrays-mirror-probe` in identity fields.
2. **Image alignment** — the sample's build script hardcodes `docker build -t proj-eric-oss-drop/eric-oss-hello-world-python-app:$VERSION` regardless of app name (see line 50 of the sample's `build-csar-with-database.sh`). This causes the built image name to diverge from the ALM identity. Fixed here by:
    - Changing build script line 50 tag to `proj-eric-oss-drop/fullrays-mirror-probe:$VERSION`.
    - Updating `charts/eric-oss-hello-world-python-app/eric-product-info.yaml` — productName + `images.<KEY>` + `images.<KEY>.name` all set to `fullrays-mirror-probe`.
    - Updating `charts/eric-oss-hello-world-python-app/templates/deployment/deployment.yaml` line 68 — the `imageId` argument to the `.imagePath` template now reads `"fullrays-mirror-probe"`.
    - Result: built image tag + chart-rendered image reference + docker.tar entry all agree on `proj-eric-oss-drop/fullrays-mirror-probe:3.2.2-0`.

Other than that — identical to test-01. Same subchart, same Bitnami fallback patch, same test-run skip.

## Local end-to-end test — passed BEFORE upload

See [local-e2e-test.md](local-e2e-test.md) for the full run.

Setup: docker network + `postgres:15-alpine` container (with the app's default DB creds) + built app image on same network with `POSTGRES_HOST=pg-probe`.

Result:

- `/sample-app/python/health` → 200 `{"database":"OK","status":"Ok"}`
- `/sample-app/python/hello` × 5 → 200 `Hello World!!` each
- `/sample-app/python/visits` → 200 `{"total_visits":5, "hello_endpoint_visits":5, "recent_visits":[...5 rows...]}`
- `SELECT COUNT(*) FROM visits` in Postgres → **5 rows persisted correctly**

**The image works end-to-end locally.** The failure on the platform is NOT in the image or the chart.

## Build

```bash
cd source
./build-csar-with-database.sh 3.2.2-0 ./csar-output
# → csar-output/fullrays-mirror-probe.csar
```

## Deploy params

See [deploy-body.json](deploy-body.json). Same shape as test-01, with app-name substituted:

- `postgresql-ha.global.imageRegistry`: `eic.stsn22p1eic08.stsoss.sero.xgic.ericsson.se/appmgr/images/rapp-ericsson-fullrays-mirror-probe-3-2-2-0`

## Result

**DEPLOY_ERROR** — pgpool + postgresql-{0,1} all `ImagePullBackOff` after ~10 min. Identical failure. See [deploy.log](deploy.log), [poll.log](poll.log).

## What this test rules out

- **Not a rApp naming issue** — distinctive new identity, still fails.
- **Not an image-name mismatch** — docker tag, chart image ref, and docker.tar entry all aligned, still fails.
- **Not a stale Helm state from prior deploys** — this attempt was on a fresh sandbox after a full teardown of prior sample-db-test / twin attempts. First deploy attempt of this app.
- **Not a bug in the built image** — end-to-end local test with real Postgres passes cleanly.

**Conclusion:** the failure is 100% in the platform's `postgresql-ha` subchart image mirror.
