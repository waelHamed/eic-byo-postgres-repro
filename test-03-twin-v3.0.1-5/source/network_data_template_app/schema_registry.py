"""
This module provides functionality for interacting with Avro schemas and deserializing Avro messages.

More details:
[Schema Registry API](https://developer.intelligentautomationplatform.ericsson.net/#capabilities/messagebus/schemaregistry-developer-guide-rest-api?chapter=schema-registry-api-guide)
"""

# Standard library imports
import io
from typing import Optional

# Third-party imports
import avro.io
import avro.errors
import avro.schema
from async_lru import alru_cache
from authlib.integrations.base_client import MissingTokenError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import HTTPStatusError

# Local application imports
from .mtls_logging import logger
from .metrics import metrics_registry


@alru_cache
async def get_schema(
    eic_host_url: str, client: AsyncOAuth2Client, schema_id: str
) -> Optional[avro.schema.Schema]:
    """
    Fetches the Avro schema associated with a given schema ID from the schema registry.

    The schema registry serves as a centralized location for storing and managing Avro schemas,
    ensuring uniformity and compatibility in data serialization across different services.

    Args:
        eic_host_url (str): EIC host url.
        client (AsyncOAuth2Client): The OAuth2 client used for authenticating and communicating
        with the schema registry.
        schema_id (str): A unique identifier for the schema to be retrieved.

    Returns:
        avro.schema.Schema | None: The Avro schema if successfully fetched,
        or None if an error occurs during retrieval.
    """
    try:
        schema_registry_url = eic_host_url + "/schema-registry-sr"
        schema_response = await client.request(
            "GET", f"{schema_registry_url}/view/schemas/ids/{schema_id}"
        )

        # Check if the HTTP request was successful (status code 200)
        if not schema_response.is_success:
            metrics_registry.counters.get("schema_registry_failed_requests").inc()
            schema_response.raise_for_status()
        metrics_registry.counters.get("schema_registry_successful_requests").inc()

        # Parse the retrieved JSON schema and return it
        schema = avro.schema.parse(schema_response.json()["schema"])
        return schema

    except HTTPStatusError as http_err:
        # Log an error message for timeout issues
        logger.error(
            f"HTTPS error while fetching schema from schema registry {http_err}"
        )
    except MissingTokenError as missing_token:
        # Log an error message for missing token exceptions
        logger.error(
            f"Missing token while fetching schema from schema registry {missing_token}"
        )
    return None


def deserialize_message(
    avro_value: bytes, schema: avro.schema.Schema, schema_id: str
) -> Optional[dict]:
    """
    Deserializes an Avro-encoded message into a Python dictionary based on the provided schema.

    This function takes an Avro-encoded message, validates it against the given schema,
    and deserializes it into a dictionary for further processing.

    Args:
        avro_value (bytes): The Avro-encoded message in binary format to be deserialized.
        schema (avro.schema.Schema): The Avro schema used to validate and deserialize the message.
        schema_id (str): The unique identifier for the schema used in validation.

    Returns:
        Optional[dict]: A dictionary representing the deserialized message if successful,
        or None if deserialization fails or an error occurs.
    """
    try:
        # Initialize a BinaryDecoder to parse the Avro-encoded binary data.
        # This is required for decoding serialized Avro messages into structured records.
        value_reader = avro.io.BinaryDecoder(io.BytesIO(avro_value))

        # Set up a DatumReader that will use the provided schema to interpret the binary data.
        # This ensures that the deserialized message aligns with the expected Avro structure.
        reader = avro.io.DatumReader(schema)

        # Deserialize the Avro binary data into a Python object using the provided schema.
        # This converts the raw Avro bytes into a usable dictionary-like structure.
        deserialized_value = reader.read(value_reader)
        return deserialized_value

    except avro.errors.AvroTypeException as avro_type_err:
        logger.error(f"Avro type error for schema ID {schema_id}: {avro_type_err}")
    except avro.errors.AvroException as avro_schema_err:
        # Catching other specific Avro-related exceptions
        logger.error(f"Avro schema error for schema ID {schema_id}: {avro_schema_err}")
    return None
