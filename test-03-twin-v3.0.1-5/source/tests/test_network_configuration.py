# pylint: disable=W0613
# W0613: Unused argument
"""Tests for the methods in network_configuration.py"""

import network_data_template_app.network_configuration as network_configuration
import pytest


@pytest.mark.asyncio
async def test_read_attribute_through_network_configuration(
    mock_apis, network_configuration_api, config, async_oauth_client
):
    """
    Scenario: Call the read_attribute_through_network_configuration() method.
    Expected Outcome: The method should return the attribute value for a given source ID from Network Configuration API.
    Assertion: The returned value should be equal to the expected response.
    """
    url = (
        config.get("eic_host_url")
        + "/ncmp/v1/ch/1/data/ds/ncmp-datastore:passthrough-operational?resourceIdentifier=[NRCellDU=NR01gNodeBRadio00041-1]"
    )

    response = await network_configuration.read_attribute_through_network_configuration(
        async_oauth_client, url, "operationalState"
    )
    assert response == "DISABLED"


@pytest.mark.asyncio
async def test_get_attribute_for_source_id(
    mock_apis, network_configuration_api, config, async_oauth_client
):
    """
    Scenario: Call the get_attribute_for_source_id() method.
    Expected Outcome: The method should return the attribute value for a given source ID.
    Assertion: The returned value should be equal to the expected response.
    """
    source_id = "urn:3gpp:dn:SubNetwork=Europe,SubNetwork=Ireland,MeContext=NR01gNodeBRadio00041,ManagedElement=NR01gNodeBRadio00041,GNBDUFunction=1,NRCellDU=NR01gNodeBRadio00041-1"
    response = await network_configuration.get_attribute_for_source_id(
        async_oauth_client, source_id, "operationalState"
    )
    assert response == {"id": source_id, "operationalState": "DISABLED"}
