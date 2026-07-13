"""
This module provides functionality to interact with the
'Network Configuration' capability and retrieve attributes for
source IDs. It uses asynchronous operations for parallel processing
and thread pooling to improve performance when making requests.

More details: [Network Configuration](https://developer.intelligentautomationplatform.ericsson.net/#capabilities/network-configuration)

Modules:
- asyncio: Used for asynchronous programming.
- concurrent.futures: Used for creating thread pools.
- urllib.parse: For URL encoding and decoding.
- requests: To make HTTP requests.
- eiid_access_id: Contains helper functions for Network Configuration URL creation.
- config: Retrieves configuration settings.
"""

import asyncio
import time
from typing import Optional
from urllib.parse import urlencode, unquote

from authlib.integrations.httpx_client import AsyncOAuth2Client
from eiid_access_id import network_configuration_url_helper
from eiid_access_id.network_configuration_url_helper import DataStoreType
from httpx import HTTPStatusError

from .config import get_config
from .mtls_logging import logger
from .metrics import metrics_registry


async def get_attributes_for_source_ids(
    client: AsyncOAuth2Client, list_of_source_ids: list[str], attribute: str
) -> list[dict[str, str | None]]:
    """
    Retrieve relevant attributes for each source ID in the provided list. This is done through individual calls to Network Configuration
    for each source ID provided in the list.

    If your use case demands a much larger amount of cells, consider implementing a scalable solution by
    following this section of the Network Configuration Developer Guide:
    https://developer.intelligentautomationplatform.ericsson.net/#capabilities/network-configuration/developer-guide?chapter=read-cm-data-for-multiple-network-elements

    Args:
        client (AsyncOAuth2Client): The AsyncOAuth2Client for API requests.
        list_of_source_ids (list[str]): A list of source IDs to retrieve attributes for.
        attribute (str): The attribute type to supply in the retrieval of attributes.
    """

    # Create tasks to concurrently fetch attributes for each source ID
    logger.debug(
        f"Event loop obtained, creating {len(list_of_source_ids)} tasks for fetching attributes concurrently"
    )
    start_time = time.perf_counter()
    tasks = [
        get_attribute_for_source_id(client, param, attribute)
        for param in list_of_source_ids
    ]
    # Gather results from all tasks
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed_time = time.perf_counter() - start_time
    logger.debug(f"Fetched attributes in {elapsed_time:.4f} seconds")

    return results


async def get_attribute_for_source_id(
    client: AsyncOAuth2Client, source_id: str, attribute: str
) -> dict[str, str | None]:
    """
    Fetch the relevant attribute for a given source ID.

    Args:
        client (AsyncOAuth2Client): The AsyncOAuth2Client for API requests.
        source_id (str): The source ID for which the attribute should be retrieved.
        attribute (str): The attribute type to supply in the retrieval of the attribute.

    Returns:
        dict[str, str | None]: A dictionary containing the source ID and the requested attribute (or None, if attribute retrieval fails).
    """
    # Translate externalIds to configuration operational URL
    # Data Store Type - Defines the behavior of Network Configuration with incoming requests
    #                   Read more: https://developer.intelligentautomationplatform.ericsson.net/#capabilities/topology-inventory/eiid-id-lib-guide-topology-inventory
    network_configuration_read_url = (
        network_configuration_url_helper.url_data_from_prefixed_fdn(
            source_id,
            f"{get_config()['eic_host_url']}",
            DataStoreType.PASSTHROUGH_OPERATIONAL,
        ).get_network_configuration_url()
    )

    # Read the current attribute from Network Configuration
    current_attribute = ""
    try:
        current_attribute = await read_attribute_through_network_configuration(
            client, network_configuration_read_url, attribute
        )
        metrics_registry.counters.get("network_configuration_successful_requests").inc()
    except HTTPStatusError as e:
        metrics_registry.counters.get("network_configuration_failed_requests").inc()
        logger.error(
            f"Failed to get '{attribute}' for '{source_id}': {e.response.status_code} {e.response.text}"
        )
    finally:
        response = {"id": source_id, attribute: current_attribute}
    return response
    # If the attribute is found, return it in a dictionary


async def read_attribute_through_network_configuration(
    client: AsyncOAuth2Client, network_configuration_url: str, attribute: str
) -> Optional[str]:
    """
    Read the attribute using the Network Configuration capability.

    Args:
        client (AsyncOAuth2Client): The AsyncOAuth2Client for API requests.
        network_configuration_url (str): The constructed URL endpoint for making the API request.
        attribute (str): The attribute type to supply in the retrieval of the attribute.
    """
    # Split the URL and parameters for the request
    url, params = network_configuration_url.split("?")
    resource_identifier_key, resource_identifier_value = params.split("=", 1)

    # Prepare the params for the request
    params = {
        resource_identifier_key: unquote(resource_identifier_value),
        "options": f"(fields=attributes/{attribute})",
    }
    # URL encode the parameters
    encoded_params = urlencode(params, safe="[]()")

    # Perform the GET request to fetch the attribute
    response = await client.request("GET", url=url, params=encoded_params, timeout=5000)

    # Raise an exception for bad responses
    response.raise_for_status()

    if response.is_success:
        # Extract the attribute value from the response JSON
        attribute_value = (
            response.json()
            .get("NRCellDU", [{}])[0]
            .get("attributes", {})
            .get(attribute)
        )
        return attribute_value

    # Return None if attribute retrieval fails
    return None
