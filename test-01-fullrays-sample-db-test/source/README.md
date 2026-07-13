# rApp Devcon Database Demo App

## Disclaimer

> ⚠️ **Important Disclaimer:**
> The instructions below are only applicable if you
> **already have full access** to the EIAP Ecosystem.
> If you do not have this access, **please do not proceed.**

**Note:**
If you need help accessing the EIAP Ecosystem, contact support
at this **email address:** intelligent.automation.platform@ericsson.com

## Introduction

This is a sample rApp that integrates simple Hello World Python App with PostGreSQL database. Main objective 
of this rApp is to showcase how to integrate a database helm chart with an rApp. To demonstrate the database usage the rApp persists user agent and timestamp information every time /hello endpoint is invoked. Persisted information is then exposed using /visits endpoint.

This code is better understood when checked in conjunction with "How to Bring Your Own Databse" session from rApp DevCon 2025.

This rApps provides the following endpoints:

- **/rapp-devcon-database-demo/v1/hello** is a sample endpoint.

- **/rapp-devcon-database-demo/v1/visits** exposes some stats about the usage of /hello endpoint, persisted in database.


## Build CSAR

Build CSAR by running the following command

```bash
./build-csar-with-database.sh 3.2.2-0 ./csar-output
```

This script builds application docker, performs basic validation of the application and builds a CSAR.

## Deploy the rApp

Onboard the rApp using "App Administration" capability available on OSS Portal. Then deploy the rApp using "App Operations" capability available on OSS Portal. Following snippet shows the userDefinedHelm parameters to be used while deploying the rApp.

```json
{
"componentInstances": [
	{
		"name": "fullrays-sample-db-test",
		"properties": {
			"userDefinedHelmParameters": {
				"postgresql-ha.global.imageRegistry": "<APP_MGR_HOST>/appmgr/images/rapp-ericsson-fullrays-sample-db-test-3-2-2-0",
				"postgresql-ha.global.imagePullSecrets": [
					"hfe-generic-pull-secret"
				],
				"postgresql-ha.global.security.allowInsecureImages": true,
				"postgresql-ha.global.postgresql.existingSecret": "fullrays-sample-db-test-postgresql-secret",
				"postgresql-ha.global.pgpool.existingSecret": "fullrays-sample-db-test-pgpool-secret",
				"postgresql-ha-credentials.postgresql.username": "postgres",
				"iamBaseUrl": "<IAM_URL>",
				"logEndpoint": "<LOG_AGGREGATOR_HOST>",
				"platformCaCertSecretName": "<PLATFORM_CACERT_SECRET>",
				"appSecretName": "<APP_CERT_SECRET>",
        "platformCaCertFileName": "<PLATFORM_CA_CERT_FILENAME>",
        "appKeyFileName": "<APP_PRIVATE_KEY>",
        "appCertFileName": "<APP_CERTIFICATE>"
			},
			"namespace": "<NAMESPACE>",
			"timeout": 5
		}
	}
]
}
```

## Onboard APIs and configure RBAC

Onboards app APIs and configure RBAC by running the following command.

```bash
./onboard-api.sh <EIC_HOST> <CLIENT_ID> <CLIENT_SECRET> <APP_NAME>
```

where,

EIC_HOST : EIC Host Name
CLIENT_ID : ID of an IAM client. This client need to have `Exposure_Application_Administrator` and
`UserAdministration_ExtAppRbac_Application_SecurityAdministrator` roles to be able to expose rApp APIs and configure necessary access control on the APIs.
CLIENT_SECRET : Client Secret of the IAM client.
APP_NAME : Name of the application's ClusterIP service(inside k8s). Use `fullrays-sample-db-test` if you have not made any changes to rApp helm chart.

Once this step is successfully completed, rApp APIs will be accessible at `<EIC_HOST>/hub/rapp-devcon-database-demo/v1/<Resource>`. `Devcon_Database_Demo_App_Admin` role must be assigned to any user/client accessing the endpoint.
