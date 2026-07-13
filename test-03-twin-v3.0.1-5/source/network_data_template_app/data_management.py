"""
Data Management
https://developer.intelligentautomationplatform.ericsson.net/#capabilities/data-management
"""

import time
from typing import Tuple

import httpx
from authlib.integrations.base_client import MissingTokenError
from authlib.integrations.httpx_client import OAuth2Client
from httpx import HTTPStatusError

from .mtls_logging import logger
from .config import get_config

config = get_config()

# Obtain our rApp's Data Management endpoint by using the auto-generated Client ID.
DATA_MANAGEMENT_URL = f"{config.get('eic_host_url')}/dmm-data-collection-controller/data-access/v2/{config.get('iam_client_id')}/dataJobs"


def _get_data_jobs(client: OAuth2Client) -> list:
    """
    Obtain all data jobs under our client/consumer ID.

    The data_management_url should be the full URL for "Get Data Jobs" including consumer ID as per the API guide:
    https://developer.intelligentautomationplatform.ericsson.net/#capabilities/data-management/api-guide

    The consumer ID is the same as the rApp client ID.

    The response will always be a list, even if it only has one element.
    """
    logger.debug(f"Accessing Data Management at {DATA_MANAGEMENT_URL}")

    max_retries = int(config.get("max_retries"))
    retry_delay = int(config.get("retry_delay"))
    response = None
    for attempt in range(max_retries):
        try:
            response = client.request("get", f"{DATA_MANAGEMENT_URL}")
            response.raise_for_status()
            break
        except (HTTPStatusError, MissingTokenError) as e:
            if attempt < max_retries - 1:
                logger.error(
                    (
                        f"Could not retrieve connection details from Data Management to establish Message Bus connection:"
                        f" {e} Retrying... ({attempt + 1}/{max_retries})"
                    )
                )
                time.sleep(retry_delay * (2**attempt))
            else:
                match e:
                    case MissingTokenError():
                        raise DataManagementError(
                            f"Unable to retrieve token after retrying. ({attempt + 1}/{max_retries})"
                        ) from e
                    case httpx.HTTPStatusError():
                        raise DataManagementError(
                            f"Elapsed retries ({attempt + 1}/{max_retries}) with HTTP error: {e}"
                        ) from e

    logger.debug(f"Retrieved {len(response.json())} data job(s)")

    if len(response.json()) == 1:
        logger.debug(
            f"Retrieved data job '{response.json()[0].get('dataJobName', 'Invalid Data Job')}'"
        )

    if len(response.json()) > 1:
        logger.warning(
            (
                "More than one data job retrieved."
                " Network Data Template App only supports one active data job, unexpected behaviour may occur!"
            )
        )
    if len(response.json()) == 0:
        logger.error(
            "No data job found! Please ensure the data access configuration is defined correctly."
        )
        raise DataManagementError("No data job found!")

    return response.json()


def _parse_message_bus_connection(data_job: dict) -> Tuple[str, str, str]:
    """
    Retrieve the Kafka server, port and topic name from a given data job.
    Returned as a Tuple: (topic, hostname, port)
    """
    hostname = data_job["streamingConfigurationKafka"]["kafkaBootstrapServers"][0][
        "hostname"
    ]
    port = data_job["streamingConfigurationKafka"]["kafkaBootstrapServers"][0][
        "portAddress"
    ]
    topic = data_job["streamingConfigurationKafka"]["topicName"]

    message_bus = (topic, hostname, port)
    logger.debug(f"Parsed connection details for Message Bus: {message_bus}")

    return message_bus


def get_message_bus_details(client: OAuth2Client) -> dict:
    """
    Obtain Message Bus connection details from the data job in your rApp's packaged Data Access Configuration.
    This function will return the Kafka server, port and topic name from Data Management.

    Find your Data Access Configuration in:
        csar/OtherDefinitions/DataManagement/data-access-configuration.json
    """
    data_jobs = _get_data_jobs(client)
    message_bus = _parse_message_bus_connection(data_jobs[0])
    return {"topic": message_bus[0], "hostname": message_bus[1], "port": message_bus[2]}


class DataManagementError(Exception):
    """
    Any error which may occur as a result of Data Management.
    This error should only be raised if all recovery attempts fail -- the rApp should then handle it and shut down if encountered.
    """
