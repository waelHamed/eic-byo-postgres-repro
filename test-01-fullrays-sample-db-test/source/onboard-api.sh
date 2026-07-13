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
if [ $# -lt 4 ]; then
    print_error "Missing required parameters"
    echo "Usage: $0 <EIC_HOST> <IAM_CLIENT_ID> <IAM_CLIENT_SECRET> <APP_NAME>"
    echo "Example: $0 eic.example.com my-client-id my-client-secret fullrays-sample-db-test"
    exit 1
fi

EIC_HOST=$1
IAM_CLIENT_ID=$2
IAM_CLIENT_SECRET=$3
APP_NAME=$4

# API Configuration
API_ID="rapp-devcon-database-demo"
API_NAME="rapp-devcon-database-demo"
API_VERSION="v1"
ENDPOINT_ID="rapp-devcon-database-demo"
SERVER_URL="http://${APP_NAME}:8050"
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

print_step "Onboarding API"

# Create API
print_step "Creating API"
curl -k --location --request POST "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis" \
--header "Authorization: Bearer ${ACCESS_TOKEN}" \
--header "Content-Type: application/json" \
--data "{
  \"serviceCapabilityId\": \"${API_ID}\",
  \"status\": \"active\",
  \"apiName\": \"${API_NAME}\",
  \"apiVersion\": \"${API_VERSION}\",
  \"apiCategory\": \"/APIGM/category/api\",
  \"apiDefinition\": [
    {
      \"operationName\": \"Database demo App Hello\",
      \"urlPattern\": \"/hello\",
      \"methods\": [
        \"GET\"
      ]
    },
    {
      \"operationName\": \"Database demo App Visits\",
      \"urlPattern\": \"/visits\",
      \"methods\": [
        \"GET\"
      ]
    }
  ]
}"
echo

# Create Endpoint
print_step "Creating Endpoint"
curl -k --location --request POST "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}/endpoints" \
--header "Authorization: Bearer ${ACCESS_TOKEN}" \
--header "Content-Type: application/json" \
--data "{
  \"endpointId\": \"${ENDPOINT_ID}\",
  \"serverUrl\": \"${SERVER_URL}\",
  \"prefixPath\": \"/sample-app/python\"
}"
echo

# Bind Authorization Plugin
print_step "Binding Authorization Plugin"
curl -k --location --request PUT "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}/phases/auth/plugin-list" \
--header "Authorization: Bearer ${ACCESS_TOKEN}" \
--header "Content-Type: application/json" \
--data "[
  {
    \"name\": \"requestPartyTokenInterceptor\"
  }
]"
echo

# Configure Authorization Plugin
print_step "Configuring Authorization Plugin"
curl -k --location --request PUT "https://${EIC_HOST}/hub/apiprovisioning/v1/admin/v3/apis/${API_ID}/plugins/requestPartyTokenInterceptor/configuration" \
--header "Authorization: Bearer ${ACCESS_TOKEN}" \
--header "Content-Type: application/json" \
--data "{
  \"configurationSchemaVersion\": \"v0\",
  \"configuration\": {
    \"defaultResourceServer\": \"eo\"
  }
}"
echo

print_step "Managing Access Control"

# Add RBAC Policy
print_step "Adding RBAC Policy"
curl -k --location --request POST "https://${EIC_HOST}/idm/rolemgmt/v1/extapp/rbac" \
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
        \"name\": \"database_demo_app_hello\",
        \"type\": \"urn:eo:resources:extrapp\",
        \"ownerManagedAccess\": false,
        \"uris\": [
          \"/${API_NAME}/${API_VERSION}/hello\"
        ],
        \"scopes\": [
          {
            \"name\": \"PATCH\"
          },
          {
            \"name\": \"DELETE\"
          },
          {
            \"name\": \"GET\"
          },
          {
            \"name\": \"POST\"
          },
          {
            \"name\": \"PUT\"
          }
        ]
      },
      {
        \"name\": \"database_demo_app_visits\",
        \"type\": \"urn:eo:resources:extrapp\",
        \"ownerManagedAccess\": false,
        \"uris\": [
          \"/${API_NAME}/${API_VERSION}/visits\"
        ],
        \"scopes\": [
          {
            \"name\": \"PATCH\"
          },
          {
            \"name\": \"DELETE\"
          },
          {
            \"name\": \"GET\"
          },
          {
            \"name\": \"POST\"
          },
          {
            \"name\": \"PUT\"
          }
        ]
      }
    ],
    \"policies\": [
      {
        \"name\": \"${APP_DISPLAY_NAME} Hello Policy\",
        \"type\": \"role\",
        \"logic\": \"POSITIVE\",
        \"decisionStrategy\": \"UNANIMOUS\",
        \"config\": {
          \"roles\": \"[{\\\"id\\\":\\\"Devcon_Database_Demo_App_Admin\\\",\\\"required\\\":false}]\"
        }
      },
      {
        \"name\": \"${APP_DISPLAY_NAME} Visits Policy\",
        \"type\": \"role\",
        \"logic\": \"POSITIVE\",
        \"decisionStrategy\": \"UNANIMOUS\",
        \"config\": {
          \"roles\": \"[{\\\"id\\\":\\\"Devcon_Database_Demo_App_Admin\\\",\\\"required\\\":false}]\"
        }
      },
      {
        \"name\": \"${APP_DISPLAY_NAME} Hello Permission\",
        \"type\": \"scope\",
        \"logic\": \"POSITIVE\",
        \"decisionStrategy\": \"AFFIRMATIVE\",
        \"config\": {
          \"resources\": \"[\\\"database_demo_app_hello\\\"]\",
          \"scopes\": \"[\\\"GET\\\",\\\"PUT\\\",\\\"POST\\\",\\\"DELETE\\\",\\\"PATCH\\\"]\",
          \"applyPolicies\": \"[\\\"${APP_DISPLAY_NAME} Hello Policy\\\"]\"
        }
      },
      {
        \"name\": \"${APP_DISPLAY_NAME} Visits Permission\",
        \"type\": \"scope\",
        \"logic\": \"POSITIVE\",
        \"decisionStrategy\": \"AFFIRMATIVE\",
        \"config\": {
          \"resources\": \"[\\\"database_demo_app_visits\\\"]\",
          \"scopes\": \"[\\\"GET\\\",\\\"PUT\\\",\\\"POST\\\",\\\"DELETE\\\",\\\"PATCH\\\"]\",
          \"applyPolicies\": \"[\\\"${APP_DISPLAY_NAME} Visits Policy\\\"]\"
        }
      }
    ],
    \"scopes\": [
      {
        \"name\": \"GET\"
      },
      {
        \"name\": \"POST\"
      },
      {
        \"name\": \"DELETE\"
      },
      {
        \"name\": \"PUT\"
      },
      {
        \"name\": \"PATCH\"
      }
    ]
  }
}"
echo

print_step "API Onboarding and Access Control Setup Complete"
echo "The API has been onboarded and access control has been configured."
echo "To access the /rapp-devcon-database-demo/v1/hello and /rapp-devcon-database-demo/v1/visits endpoints, assign the 'Devcon_Database_Demo_App_Admin' role to your client." 