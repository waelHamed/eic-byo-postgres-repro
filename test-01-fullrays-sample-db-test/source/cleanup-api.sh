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
if [ $# -lt 3 ]; then
    print_error "Missing required parameters"
    echo "Usage: $0 <EIC_HOST> <IAM_CLIENT_ID> <IAM_CLIENT_SECRET>"
    echo "Example: $0 eic.example.com my-client-id my-client-secret"
    exit 1
fi

EIC_HOST=$1
IAM_CLIENT_ID=$2
IAM_CLIENT_SECRET=$3

# API Configuration
API_ID="rapp-devcon-database-demo"
ENDPOINT_ID="rapp-devcon-database-demo"
APP_DISPLAY_NAME="Devcon Database Demo App"

print_step "Generating Access Token"
# Generate access token using client credentials
ACCESS_TOKEN=$(curl -k --request POST \
"https://${EIC_HOST}/auth/realms/master/protocol/openid-connect/token" \
--header 'content-type: application/x-www-form-urlencoded' \
--data "grant_type=client_credentials&client_id=${IAM_CLIENT_ID}&client_secret=${IAM_CLIENT_SECRET}" | jq -r '.access_token')
echo

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    print_error "Failed to obtain access token"
    exit 1
fi

print_step "Cleaning up RBAC Resources"

# Remove RBAC Policies
print_step "Removing RBAC Policies"
curl -k --location --request DELETE "https://${EIC_HOST}/idm/rolemgmt/v1/extapp/rbac" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer ${ACCESS_TOKEN}" \
--data "{
    \"tenant\": \"master\",
    \"roles\": [
        {
            \"name\": \"Devcon_Database_Demo_App_Admin\"
        }
    ],
    \"authorization\": {
        \"resources\": [
            {
                \"name\": \"database_demo_app_hello\"
            },
            {
                \"name\": \"database_demo_app_visits\"
            }
        ],
        \"policies\": [
            {
                \"name\": \"${APP_DISPLAY_NAME} Hello Policy\"
            },
            {
                \"name\": \"${APP_DISPLAY_NAME} Visits Policy\"
            },
            {
                \"name\": \"${APP_DISPLAY_NAME} Hello Permission\"
            },
            {
                \"name\": \"${APP_DISPLAY_NAME} Visits Permission\"
            }
        ]
    }
}"
echo

print_step "Cleaning up API Resources"

# # Remove Authorization Plugin Configuration
# print_step "Removing Authorization Plugin Configuration"
# curl -k --location --request DELETE "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}/plugins/requestPartyTokenInterceptor/configuration" \
# --header "Authorization: Bearer ${ACCESS_TOKEN}"

# # Remove Authorization Plugin Binding
# print_step "Removing Authorization Plugin Binding"
# curl -k --location --request DELETE "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}/phases/auth/plugin-list" \
# --header "Authorization: Bearer ${ACCESS_TOKEN}"

# Remove Endpoint
print_step "Removing Endpoint"
curl -k --location --request DELETE "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}/endpoints/${ENDPOINT_ID}" \
--header "Authorization: Bearer ${ACCESS_TOKEN}"
echo

# Remove API
print_step "Removing API"
curl -k --location --request DELETE "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}" \
--header "Authorization: Bearer ${ACCESS_TOKEN}"
echo

print_step "Cleanup Complete"
echo "All resources have been successfully removed." 