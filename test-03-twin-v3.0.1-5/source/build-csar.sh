#!/bin/bash
# build-csar.sh — Build the Twin CSAR (v3.0.1-5+) with bundled postgresql-ha subchart.
#
# Adapted from the EIC "Bring Your Own Database" sample
# (eric-oss-hello-world-python-app-3.2.2-0/build-csar-with-database.sh).
#
# Prereqs:
#   - helm (>= 3)
#   - docker
#   - access to armdocker.rnd.ericsson.se (Ericsson registry) + docker.io (Bitnami)
#   - the eric-oss-app-package-tool image pullable from Ericsson registry
#
# Usage:
#   ./build-csar.sh <VERSION> <OUTPUT_DIR>
# Example:
#   ./build-csar.sh 3.0.1-5 ./csar-output

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
print_step() { echo -e "${GREEN}=== $1 ===${NC}"; }
print_warn() { echo -e "${YELLOW}WARN: $1${NC}"; }
print_err()  { echo -e "${RED}ERR:  $1${NC}" >&2; }

[[ $# -ge 2 ]] || { print_err "Usage: $0 <VERSION> <OUTPUT_DIR>"; exit 1; }
VERSION="$1"
OUTPUT_DIR="$2"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$REPO_ROOT/charts/fullrays-indoor-wireless-twin"
CSAR_SKELETON="$REPO_ROOT/csar"
CSAR_STAGING="$REPO_ROOT/.csar-staging"
APP_NAME="fullrays-indoor-wireless-twin"
IMG_LOCAL="proj-eric-oss-drop/${APP_NAME}:${VERSION}"

mkdir -p "$OUTPUT_DIR"
rm -rf "$CSAR_STAGING"
mkdir -p "$CSAR_STAGING"

print_step "Build app Docker image → $IMG_LOCAL"
docker build --no-cache "$REPO_ROOT" -t "$IMG_LOCAL" --build-arg "APP_VERSION=$VERSION"

print_step "helm dep update — pull postgresql-ha subchart"
helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null 2>&1 || true
helm repo update >/dev/null
helm dependency update "$CHART_DIR"

print_step "Package chart → CSAR staging"
cp -r "$CSAR_SKELETON"/* "$CSAR_STAGING/"
rm -f "$CSAR_STAGING/OtherDefinitions/ASD/${APP_NAME}-"*.tgz
helm package "$CHART_DIR" -d "$CSAR_STAGING/OtherDefinitions/ASD/"

print_step "Discover subchart images from helm template"
IMAGES_FILE=$(mktemp)
RETAGGED_FILE=$(mktemp)
helm template "$CHART_DIR" \
  | grep -E "^\s*image:" \
  | grep -v "armdocker.rnd.ericsson.se" \
  | sed -E 's/^\s*image:\s*//; s/"//g' \
  | sort -u > "$IMAGES_FILE"

echo "Subchart images to bundle:"
cat "$IMAGES_FILE"
echo

print_step "Pull + retag subchart images"
# As of 2025-08, Bitnami moved public images from bitnami/* to bitnamilegacy/*
# on Docker Hub. Try the original path first, then fall back to the legacy path
# and retag back so the chart's default image references keep working.
pull_with_fallback() {
  local img="$1"
  if docker pull "$img" 2>/dev/null; then
    return 0
  fi
  local fallback="${img/docker.io\/bitnami\//docker.io/bitnamilegacy/}"
  if [[ "$fallback" != "$img" ]] && docker pull "$fallback"; then
    docker tag "$fallback" "$img"
    echo "  retagged $fallback → $img"
    return 0
  fi
  return 1
}
while IFS= read -r img; do
  [[ -z "$img" ]] && continue
  echo "  pull $img"
  pull_with_fallback "$img" || { print_err "cannot pull $img from any source"; exit 1; }
  # strip leading registry prefix (docker.io/bitnami/xxx → bitnami/xxx)
  short="${img#*/}"
  if [[ "$img" != "$short" ]]; then
    docker tag "$img" "$short"
    echo "$short" >> "$RETAGGED_FILE"
  else
    echo "$img"    >> "$RETAGGED_FILE"
  fi
done < "$IMAGES_FILE"
echo "$IMG_LOCAL" >> "$RETAGGED_FILE"

print_step "docker save → $CSAR_STAGING/OtherDefinitions/ASD/Images/docker.tar"
mkdir -p "$CSAR_STAGING/OtherDefinitions/ASD/Images"
docker save $(cat "$RETAGGED_FILE") -o "$CSAR_STAGING/OtherDefinitions/ASD/Images/docker.tar"

rm -f "$IMAGES_FILE" "$RETAGGED_FILE"

print_step "Bake CSAR via eric-oss-app-package-tool"
docker run --init --rm \
  --volume "$OUTPUT_DIR:/tmp/csar/" \
  --volume "$HOME/.docker:/root/.docker" \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --workdir /target \
  --volume "$CSAR_STAGING:/target" \
  armdocker.rnd.ericsson.se/proj-eric-oss-dev-test/releases/eric-oss-app-package-tool:latest \
  generate --tosca /target/Metadata/Tosca.meta \
           --name "${APP_NAME}" \
           --images /target/OtherDefinitions/ASD/Images/docker.tar \
           --helm3 \
           --output /tmp/csar

mv -f "$OUTPUT_DIR/${APP_NAME}.csar" "$OUTPUT_DIR/twin-${VERSION}.csar" 2>/dev/null || true

# app-package-tool runs as root inside its container and writes root-owned
# artifacts; hand the CSAR back to the invoking user so SFTP/edit works.
if [[ -f "$OUTPUT_DIR/twin-${VERSION}.csar" ]] && [[ ! -w "$OUTPUT_DIR/twin-${VERSION}.csar" ]]; then
  sudo -n chown "$(id -u):$(id -g)" "$OUTPUT_DIR/twin-${VERSION}.csar" 2>/dev/null \
    || print_warn "run: sudo chown $(id -u):$(id -g) $OUTPUT_DIR/twin-${VERSION}.csar"
fi

print_step "Done"
ls -lh "$OUTPUT_DIR/twin-${VERSION}.csar" 2>/dev/null || ls -lh "$OUTPUT_DIR"/*.csar
echo "Version: $VERSION"
