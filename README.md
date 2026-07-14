# EIC BYO-Postgres Reproduction — `stsn22p1eic08`

**Purpose:** Reproduce the `ImagePullBackOff` failure of `postgresql-ha` subchart images (`pgpool`, `postgresql-repmgr`) that occurs when any rApp using EIC's documented "Bring Your Own Database" pattern is deployed in the `stsn22p1eic08` External Sandbox.

**Reported by:** Wael Abdulaziz — wael.abdulaziz@fullrays.com — team `fullrays`
**Environment:** `stsn22p1eic08.stsoss.sero.xgic.ericsson.se`
**Approval trail:** mTLS provisioning approved 2026-06-20; Postgres provisioning clarification 2026-07-04 (EIC does NOT provision Postgres for rApps — apps must bundle via `postgresql-ha` subchart).

## Executive summary

Five deploy attempts, each in its own subdirectory below. **Every one that reached pod creation failed identically:** three pods (`pgpool` + `postgresql-{0,1}`) stuck in `ImagePullBackOff` regardless of what value we set `postgresql-ha.global.imageRegistry` to. **Every other layer works** — the main app image pulls fine from `armdocker.rnd.ericsson.se`, onboard/init/enable succeed, chart renders cleanly locally, image works end-to-end locally with a real Postgres.

The fault is confined to the platform's Bitnami-subchart image mirror in `stsn22p1eic08` — either missing, mispathed, or documented incorrectly.

## Attempts

| # | Test directory | App name (ALM identity) | App ID | Instance ID | `postgresql-ha.global.imageRegistry` value under test | Result |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | [test-01-fullrays-sample-db-test/](test-01-fullrays-sample-db-test/) | `fullrays-sample-db-test` | `rapp-ericsson-fullrays-sample-db-test-3-2-2-0` | `rapp-ericsson-fullrays-sample-db-test-56021667` | `eic.stsn22p1eic08.stsoss.sero.xgic.ericsson.se/appmgr/images/rapp-ericsson-fullrays-sample-db-test-3-2-2-0` (sample README's exact pattern with `<APP_MGR_HOST>` = EIC host) | **DEPLOY_ERROR** — pgpool + postgresql-{0,1} `ImagePullBackOff` |
| **2** | [test-02-armdocker/](test-02-armdocker/) | (same CSAR as #1) | `rapp-ericsson-fullrays-sample-db-test-3-2-2-0` | `rapp-ericsson-fullrays-sample-db-test-11785075` | `armdocker.rnd.ericsson.se` (same host our main app image pulls from) | **DEPLOY_ERROR** — identical failure |
| **3** | [test-03-twin-v3.0.1-5/](test-03-twin-v3.0.1-5/) | `fullrays-indoor-wireless-twin` (v3.0.1-5) | `rapp-ericsson-fullrays-indoor-wireless-twin-3-0-1-5` | `rapp-ericsson-fullrays-indoor-wireless-twin-58949648` | `.../appmgr/images/rapp-ericsson-fullrays-indoor-wireless-twin-3-0-1-5` (README pattern with Twin's app name) | **DEPLOY_ERROR** — identical failure |
| **4** | [test-04-fullrays-mirror-probe/](test-04-fullrays-mirror-probe/) | `fullrays-mirror-probe` | `rapp-ericsson-fullrays-mirror-probe-3-2-2-0` | `rapp-ericsson-fullrays-mirror-probe-86724860` | `.../appmgr/images/rapp-ericsson-fullrays-mirror-probe-3-2-2-0`. **Distinctive new name + Docker image tag fully aligned across chart + build**. Full end-to-end test with Postgres passed locally. | **DEPLOY_ERROR** — identical failure |
| **5** | [test-05-devcon-8.7.6-6/](test-05-devcon-8.7.6-6/) | `rapp-devcon-database-demo-app` (v8.7.6-6) | `rapp-ericsson-rapp-devcon-database-demo-app-8-7-6-6` | `rapp-ericsson-rapp-devcon-database-demo-app-03211346` | `.../appmgr/images/rapp-ericsson-rapp-devcon-database-demo-app-8-7-6-6`. **EIC sample verbatim, only version bumped to avoid onboard collision.** | **DEPLOY_ERROR** — but hit `"ic" exists` Helm ownership error before pod creation. Related but separate issue; see [test-05 README](test-05-devcon-8.7.6-6/README.md). |

## What we know works

- **Main app image pulls fine** — `armdocker.rnd.ericsson.se/proj-eric-oss-drop/<APP>:<VER>` — cluster nodes CAN reach `armdocker.rnd.ericsson.se` with default credentials.
- **Chart renders cleanly** locally (`helm template test .`) with `postgresql-ha.global.security.allowInsecureImages: true` (required post-Bitnami 2025-08-28 image relocation).
- **Docker.tar inside the CSAR is well-formed** — verified via `manifest.json` extraction, all three images present with correct RepoTags.
- **Onboard + Initialize + Enable + instance-create** all succeed in ALM.
- **Local end-to-end test passes** (see [test-04](test-04-fullrays-mirror-probe/)) — main app + Postgres 15 talking, `/hello` writes visits, `/visits` reads them, rows persist correctly in Postgres.

## Build a CSAR yourself (any test)

```bash
git clone https://github.com/waelHamed/eic-byo-postgres-repro.git
cd eic-byo-postgres-repro/test-01-fullrays-sample-db-test/source
./build-csar-with-database.sh <VERSION> ./csar-output
# result: ./csar-output/<APP-NAME>.csar
```

Prereqs: `docker`, `helm 3`, `jq`, network access to `docker.io/bitnamilegacy/*` and `armdocker.rnd.ericsson.se` (armdocker needs Ericsson VPN).

The build script includes a `docker.io/bitnami/*` → `docker.io/bitnamilegacy/*` fallback because Bitnami relocated their public images on 2025-08-28. Without this patch, `docker pull docker.io/bitnami/pgpool:...` returns 404. This is a MECHANICAL fix, not a behavioural change — the built CSAR still tags the images as `docker.io/bitnami/*` so downstream logic is unchanged.

## What we need from Ecosystem Engineering

1. **What is the correct `postgresql-ha.global.imageRegistry` value for `stsn22p1eic08`?** — please confirm whether the sample README's `<APP_MGR_HOST>/appmgr/images/rapp-ericsson-<APP>-<VER>` pattern applies to this sandbox, and if so, what `<APP_MGR_HOST>` resolves to.
2. **Is the platform's Bitnami-subchart image mirror configured and populated for this sandbox?** — is there a documented registry path/list that we should be pointing `postgresql-ha.global.imageRegistry` at?
3. **Or the exact kubelet `Failed to pull image X` event message** for one of the failed pgpool pods — the `<URL>` in that message tells us the platform's actual attempted path and lets us derive the right registry directly.
4. Is `hfe-generic-pull-secret` the correct pull secret for whatever registry we should be using?
5. **Also (Section 5.5 issue):** how to properly clean up orphan k8s resources left by failed BYO-Postgres deploys, since `undeploy-rapp.sh` alone doesn't clear them and end users have no kubectl access?

## Blocking impact

Our Twin rApp v3.0.1-5 (`fullrays-indoor-wireless-twin`) is blocked on this. Migration to the BYO-Postgres pattern was completed after your team confirmed on 2026-07-04 that EIC does not provision Postgres for rApps. Deployment now blocked on this issue.
