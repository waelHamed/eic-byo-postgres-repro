#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to display steps
print_step() {
    echo -e "${GREEN}=== $1 ===${NC}"
}

# Function to display warnings
print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

# Function to display errors
print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

# Check for required parameters
if [ $# -lt 2 ]; then
    print_error "Missing required parameters"
    echo "Usage: $0 <VERSION> <OUTPUT_DIR>"
    exit 1
fi

VERSION=$1
OUTPUT_DIR=$2

print_step "Setting up the Hello World Python App with PostgreSQL (v$VERSION)"

# Rename Dockerfile template
print_step "Preparing Dockerfile"
if [ -f "Dockerfile-template" ]; then
    cp Dockerfile-template Dockerfile
    sed -i 's/<PYTHON_IMAGE_NAME>/python:3.9-slim/g' Dockerfile
    echo "Dockerfile created from template"
else
    print_error "Dockerfile-template not found"
    exit 1
fi

# Build Docker image
print_step "Building Docker image"
docker build --no-cache . -t proj-eric-oss-drop/eric-oss-hello-world-python-app:$VERSION --build-arg APP_VERSION=$VERSION

# Test run skipped (fails without DB env; not needed for CSAR build)
print_step "Skipping test-run (image will be validated by k8s at deploy)"

# Build CSAR package
print_step "Building CSAR package"

# Create directories
mkdir -p fullrays-sample-db-test
mkdir -p $OUTPUT_DIR

# Copy CSAR directory structure
cp -r ./csar/* ./fullrays-sample-db-test/

# Package rApp helm chart along with database helm chart
print_step "Updating Helm dependencies"
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm dependency update ./charts/eric-oss-hello-world-python-app/
helm package ./charts/eric-oss-hello-world-python-app/ -d ./fullrays-sample-db-test/OtherDefinitions/ASD/

# Detect and pull all required images
print_step "Detecting and pulling required Docker images"

# Create temporary file for image list
IMAGE_LIST_FILE=$(mktemp)

# Run helm template to get all manifests and extract image references
helm template ./charts/eric-oss-hello-world-python-app/ | grep -i "image:" | grep -v "armdocker.rnd.ericsson.se" | sed 's/.*image: *//;s/"//g;s/[ \t]*$//' | sort | uniq > $IMAGE_LIST_FILE

# Pull and retag all required images
echo "Images to be included in the package:"
cat $IMAGE_LIST_FILE
echo ""

# Create a temporary file for retagged images
RETAGGED_LIST_FILE=$(mktemp)

pull_with_fallback() {
  local img="$1"
  if docker pull "$img" 2>/dev/null; then return 0; fi
  local fallback="${img/docker.io\/bitnami\//docker.io/bitnamilegacy/}"
  if [[ "$fallback" != "$img" ]] && docker pull "$fallback"; then
    docker tag "$fallback" "$img"
    return 0
  fi
  return 1
}

while IFS= read -r image; do
  echo "Pulling image: $image"
  pull_with_fallback "$image" || print_warning "Failed to pull $image, it may be included in the package if already available locally"
  
  # Extract image name without repository prefix
  # For example: "docker.io/bitnami/pgpool:4.6.1-debian-12-r0" becomes "bitnami/pgpool:4.6.1-debian-12-r0"
  image_without_repo=$(echo $image | sed 's,^[^/]*/,,')
  
  if [ "$image" != "$image_without_repo" ]; then
    echo "Retagging $image to $image_without_repo"
    docker tag $image $image_without_repo
    echo $image_without_repo >> $RETAGGED_LIST_FILE
  else
    echo $image >> $RETAGGED_LIST_FILE
  fi
done < $IMAGE_LIST_FILE

# Add the main app image to the list
echo "proj-eric-oss-drop/eric-oss-hello-world-python-app:$VERSION" >> $RETAGGED_LIST_FILE

echo "Retagged images to be saved:"
cat $RETAGGED_LIST_FILE
echo ""

# Generate Docker image archive with all retagged images
print_step "Saving Docker images"
docker save $(cat $RETAGGED_LIST_FILE) -o $OUTPUT_DIR/docker.tar
rm $IMAGE_LIST_FILE $RETAGGED_LIST_FILE # Clean up the temporary files

# Create CSAR package
print_step "Creating CSAR package with app-package-tool"
MSYS_NO_PATHCONV=1 docker run --init --rm \
  --volume "$PWD/$OUTPUT_DIR":/tmp/csar/ \
  --volume "$HOME/.docker":/root/.docker \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --workdir /target \
  --volume "$PWD/fullrays-sample-db-test":/target \
  armdocker.rnd.ericsson.se/proj-eric-oss-dev-test/releases/eric-oss-app-package-tool:latest \
  generate --tosca /target/Metadata/Tosca.meta \
  --name fullrays-sample-db-test \
  --images /tmp/csar/docker.tar \
  --helm3 \
  --output /tmp/csar

# Verify CSAR package
print_step "Verifying CSAR package"
ls -la $OUTPUT_DIR/fullrays-sample-db-test.csar
if [ ! -f "$OUTPUT_DIR/fullrays-sample-db-test.csar" ]; then
    print_error "CSAR package was not created"
    exit 1
fi

echo -e "${GREEN}=== CSAR package with PostgreSQL support created successfully ===${NC}"
echo "Package location: $OUTPUT_DIR/fullrays-sample-db-test.csar"
echo "Version: $VERSION"
echo "You can now proceed with onboarding this package to the platform." 