# Test 05 — DevCon sample verbatim @ v8.7.6-6 (control test)

**Purpose:** ultimate control test. Take EIC's `How-To-Bring-Your-Own-Database` DevCon sample **completely unmodified except for a version bump** (3.2.2-0 → 8.7.6-6, to avoid onboard collision) and try to deploy it. If this fails too, absolute proof the failure isn't attributable to any rename or code change on our side.

## Identity

| Field | Value |
| --- | --- |
| ALM app name | `rapp-devcon-database-demo-app` (sample's original name, unchanged) |
| Chart name | `rapp-devcon-database-demo-app` (Chart.yaml `name:` unchanged) |
| Version | **`8.7.6-6`** (bumped from sample's `3.2.2-0`) |
| App ID | `rapp-ericsson-rapp-devcon-database-demo-app-8-7-6-6` |
| Instance ID | `rapp-ericsson-rapp-devcon-database-demo-app-03211346` |
| CSAR SHA256 | `2c0a834c6bb95571557f6ce4ad9a05685e00ca9a2fd50e29943778cda49fcfd1` |

## Source

Started from the DevCon sample verbatim. **Only** modifications:

1. **Version bump** in 5 files:
   - `version` file: `3.2.2-0` → `8.7.6-6`
   - `charts/eric-oss-hello-world-python-app/Chart.yaml` — `version:` field
   - `csar/Definitions/AppDescriptor.yaml` — `APPVersion` + `NameofComponent.Version`
   - `csar/OtherDefinitions/ASD/rapp-devcon-database-demo-appASD.yaml` — `asdApplicationVersion` + `artifactId` tgz filename
   - `charts/eric-oss-hello-world-python-app/eric-product-info.yaml` — `tag: "8.7.6-6"`
2. **Same two mechanical build-script patches as before:** test-run skip + `docker.io/bitnami/*` → `docker.io/bitnamilegacy/*` fallback (Bitnami 2025-08-28 relocation).

**App name unchanged.** Chart name unchanged. Docker image name unchanged. Only the version bumped.

## Build

```bash
cd source
./build-csar-with-database.sh 8.7.6-6 ./csar-output
# → csar-output/rapp-devcon-database-demo-app.csar
```

## Deploy params

See [deploy-body.json](deploy-body.json).

- `postgresql-ha.global.imageRegistry`: `eic.stsn22p1eic08.stsoss.sero.xgic.ericsson.se/appmgr/images/rapp-ericsson-rapp-devcon-database-demo-app-8-7-6-6`
- Other values match sample README + `values.yaml` defaults.

## Result — HIT A DIFFERENT ISSUE

**DEPLOY_ERROR after 29 seconds** — did NOT reach pod creation. Hit a **Helm ownership conflict** on a resource ending in `-ic`:

```
"ic" exists and cannot be imported into the current release: invalid ownership metadata;
annotation validation error: key "meta.helm.sh/release-name" must equal
"49261774-e9db-477a-84b4-55c52d10db42": current value is "328578cf-2783-4fae-93d2-4b08ef5549a6"
```

Full logs: [deploy.log](deploy.log), [poll.log](poll.log).

## Why this happened — related secondary issue

At the time of this deploy, an earlier DEPLOY_ERROR attempt (`fullrays-mirror-probe` from test-04) was still ONBOARDED in the sandbox. Both charts use the postgresql-ha subchart with the **same** `fullnameOverride: "rapp-devcon-db"` (the sample's default). Both chart releases try to create the same-named k8s resources (like the one ending in `-ic`). Helm refused to hijack the ones owned by the earlier release.

**This is a related but separate bug** — failed BYO-Postgres deploys leave orphan k8s resources that `~/undeploy-rapp.sh` doesn't clear, and end users have no kubectl access to sweep manually.

If Ecosystem Engineering can:

1. Cleanly undeploy all prior failed attempts (k8s-level sweep, not just ALM-level).
2. Then let us retry test-05 — we'd expect it to hit the SAME pgpool `ImagePullBackOff` as tests 01–04, giving us the fifth data point and closing the loop.

## What this test proves anyway

Even without reaching pod creation, this attempt confirms:

- **The onboard succeeded** — ALM accepted the verbatim DevCon sample CSAR with only a version bump. So the CSAR format, ASD, AppDescriptor, and helm package are all valid.
- **The Helm-ownership error occurred at DEPLOY, meaning the release attempt got past all ALM validation gates** — the block is at k8s-level resource ownership check.
- **The same `fullnameOverride` collision would recur for any user trying to redeploy the sample after a prior failure**, until orphan resources are cleaned up.
