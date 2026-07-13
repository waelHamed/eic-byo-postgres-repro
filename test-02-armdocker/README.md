# Test 02 — same CSAR as [test-01](../test-01-fullrays-sample-db-test/), different `PG_IMAGE_REGISTRY`

**Purpose:** rule out that our first registry value was the only broken one. Try a different plausible registry that we know is reachable (`armdocker.rnd.ericsson.se`).

## Identity

| Field | Value |
| --- | --- |
| ALM app name | `fullrays-sample-db-test` |
| Version | `3.2.2-0` |
| App ID | `rapp-ericsson-fullrays-sample-db-test-3-2-2-0` |
| Instance ID | `rapp-ericsson-fullrays-sample-db-test-11785075` |

## Source

**Same CSAR** as test-01 — see [test-01/source/](../test-01-fullrays-sample-db-test/source/). Nothing rebuilt.

## Deploy params — only `postgresql-ha.global.imageRegistry` differs

See [deploy-body.json](deploy-body.json).

- `postgresql-ha.global.imageRegistry`: **`armdocker.rnd.ericsson.se`**
    - Rationale: the CSAR's main app image is `armdocker.rnd.ericsson.se/proj-eric-oss-drop/eric-oss-hello-world-python-app:3.2.2-0` and it pulls fine. Testing whether armdocker has a `bitnami/*` sub-namespace.

All other userDefinedHelmParameters identical to test-01.

## Result

**DEPLOY_ERROR** — pgpool + postgresql-{0,1} all `ImagePullBackOff` after ~10 min. Identical failure to test-01.

```
FAILED: Issue of creating pod(s) by timeout. Pod not found
Pod Name:rapp-devcon-db-pgpool-86f66bd8db-6km5h,  Reason:ImagePullBackOff
Pod Name:rapp-devcon-db-postgresql-0,             Reason:ImagePullBackOff
Pod Name:rapp-devcon-db-postgresql-1,             Reason:ImagePullBackOff
```

Full logs: [deploy.log](deploy.log), [poll.log](poll.log).
