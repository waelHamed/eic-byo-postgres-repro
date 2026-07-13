# Test 01 — `fullrays-sample-db-test` @ 3.2.2-0

**Purpose:** deploy EIC's own DevCon `How-To-Bring-Your-Own-Database` sample, mechanically renamed only, using the sample README's exact `PG_IMAGE_REGISTRY` pattern.

## Identity

| Field | Value |
| --- | --- |
| ALM app name | `fullrays-sample-db-test` |
| Chart name | `fullrays-sample-db-test` (Chart.yaml `name:`) |
| Version | `3.2.2-0` |
| App ID (post-onboard) | `rapp-ericsson-fullrays-sample-db-test-3-2-2-0` |
| Instance ID | `rapp-ericsson-fullrays-sample-db-test-56021667` |
| Component instance name | `fullrays-sample-db-test` |

## Source

Started from `How-To-Bring-Your-Own-Database/eric-oss-hello-world-python-app-3.2.2-0/` DevCon 2025 sample. **Only** modifications from the sample:

1. Global rename `rapp-devcon-database-demo-app` → `fullrays-sample-db-test` in identity fields (AppDescriptor.yaml, ASD yaml, Chart.yaml, values.yaml secret refs, Tosca.meta, build script) — to guarantee no clash with any prior onboard.
2. Renamed ASD file `rapp-devcon-database-demo-appASD.yaml` → `fullrays-sample-db-testASD.yaml`.
3. Added a `docker.io/bitnami/*` → `docker.io/bitnamilegacy/*` fallback in `build-csar-with-database.sh` (Bitnami relocated images 2025-08-28).

Chart structure, subchart version (`postgresql-ha 16.0.5`), Docker image name, `postgresql-ha-credentials`, all templates are otherwise **byte-identical** to the sample.

## Build

```bash
cd source
./build-csar-with-database.sh 3.2.2-0 ./csar-output
# → csar-output/fullrays-sample-db-test.csar (~239 MB)
```

CSAR SHA256 as produced: `8b37d29b0421cf11bd2ee2c0ee012837ac7e1ebed854f0a5217a0d0d6fc492fd`

## Deploy params (userDefinedHelmParameters)

See [deploy-body.json](deploy-body.json).

Key values:

- `postgresql-ha.global.imageRegistry`: **`eic.stsn22p1eic08.stsoss.sero.xgic.ericsson.se/appmgr/images/rapp-ericsson-fullrays-sample-db-test-3-2-2-0`**
    - This is the sample README's exact pattern `<APP_MGR_HOST>/appmgr/images/rapp-ericsson-<APP>-<VER>` with `<APP_MGR_HOST>` set to the EIC host.
- `postgresql-ha.global.imagePullSecrets`: `["hfe-generic-pull-secret"]`
- `postgresql-ha.global.security.allowInsecureImages`: `true`
- `postgresql-ha.global.postgresql.existingSecret`: `fullrays-sample-db-test-postgresql-secret`
- `postgresql-ha.global.pgpool.existingSecret`: `fullrays-sample-db-test-pgpool-secret`
- `postgresql-ha-credentials.postgresql.username` / `.password`: `helloworld` / `MySecurePass123` (chart's values.yaml defaults)

## Result

**DEPLOY_ERROR** — pgpool + postgresql-{0,1} all `ImagePullBackOff` after ~10 min timeout.

```
FAILED: Issue of creating pod(s) by timeout. Pod not found
Pod Name:rapp-devcon-db-pgpool-59d8f476f-884l2,  Reason:ImagePullBackOff
Pod Name:rapp-devcon-db-postgresql-0,            Reason:ImagePullBackOff
Pod Name:rapp-devcon-db-postgresql-1,            Reason:ImagePullBackOff
```

Full logs: [deploy.log](deploy.log), [poll.log](poll.log).
