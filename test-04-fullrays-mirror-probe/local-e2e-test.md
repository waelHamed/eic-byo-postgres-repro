# Local end-to-end test — proves the mirror-probe image is functional
# Ran: 2026-07-12 (before uploading CSAR to the platform)

# Setup: docker network + Postgres 15 + built app image
docker network create mirror-probe-net

docker run -d --rm \
  --name pg-probe \
  --network mirror-probe-net \
  -e POSTGRES_DB=helloworlddb \
  -e POSTGRES_USER=helloworld \
  -e POSTGRES_PASSWORD=helloworld \
  postgres:15-alpine
# Waited for pg_isready to succeed.

docker run -d --rm \
  --name mirror-probe \
  --network mirror-probe-net \
  -p 8050:8050 \
  -e POSTGRES_HOST=pg-probe \
  proj-eric-oss-drop/fullrays-mirror-probe:3.2.2-0

# Result:
# - /sample-app/python/health  → 200 {"database":"OK","status":"Ok"}
# - /sample-app/python/hello   → 200 "Hello World!!" (x5)
# - /sample-app/python/visits  → 200 {"total_visits":5, "hello_endpoint_visits":5, "recent_visits":[...5 rows...]}
# - SELECT COUNT(*) FROM visits directly in Postgres → 5 rows persisted
#
# Conclusion: bundled main-app image is fully functional end-to-end.
# The failure on the platform is confined to the Bitnami subchart image pull,
# NOT to anything in our built image or chart logic.
