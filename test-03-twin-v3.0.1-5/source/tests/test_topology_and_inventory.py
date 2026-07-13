# pylint: disable=W0613,R0801
# W0613: Unused argument
# R0801: Similar lines in 2 files
"""Tests for the methods in topology_and_inventory.py"""

import json
import pytest
import network_data_template_app.topology_and_inventory as topology_and_inventory


@pytest.mark.asyncio
async def test_get_nr_cell_dus_returns_cells(
    topology_api, mock_apis, config, async_oauth_client
):
    """
    Scenario: Call the get_nr_cell_dus() method.
    Expected Outcome: The method should return the cells from Topology & Inventory API.
    Assertion: The returned value should be equal to the expected response JSON.
    """
    with open(
        "./tests/topology_response.json",
        "r",
        encoding="utf-8",
    ) as f:
        response_json = json.load(f)
        response = await topology_and_inventory.get_nr_cell_dus(async_oauth_client)
        assert response == response_json["items"]


def test_get_sourceids_from_cells():
    """
    Scenario: Call the get_sourceids_from_cells() method.
    Expected Outcome: The method should return the source IDs from the cells.
    Assertion: The returned value should be equal to the expected response.
    """
    expected_response = [
        "urn:3gpp:dn:SubNetwork=Europe,SubNetwork=Ireland,MeContext=NR01gNodeBRadio00041,ManagedElement=NR01gNodeBRadio00041,GNBDUFunction=1,NRCellDU=NR01gNodeBRadio00041-1",
        "urn:3gpp:dn:SubNetwork=Europe,SubNetwork=Ireland,MeContext=NR01gNodeBRadio00042,ManagedElement=NR01gNodeBRadio00042,GNBDUFunction=1,NRCellDU=NR01gNodeBRadio00042-1",
        "urn:3gpp:dn:SubNetwork=Europe,SubNetwork=Ireland,MeContext=NR01gNodeBRadio00043,ManagedElement=NR01gNodeBRadio00043,GNBDUFunction=1,NRCellDU=NR01gNodeBRadio00043-1",
    ]
    with open("./tests/cells.json", "r", encoding="utf-8") as f:
        cells = json.load(f)
        assert (
            topology_and_inventory.get_sourceids_from_cells(cells) == expected_response
        )
