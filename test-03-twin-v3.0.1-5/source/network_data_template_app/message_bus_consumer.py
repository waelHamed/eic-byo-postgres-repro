"""
This module implements interactions with the 'Data Management' capability,
enabling subscription to a message bus and consumption of PM Counters.

More details:
[Data Management](https://developer.intelligentautomationplatform.ericsson.net/#capabilities/data-management)
[Message Bus](https://developer.intelligentautomationplatform.ericsson.net/#capabilities/messagebus)
"""

import asyncio
import sys
import time
from functools import partial
from typing import Optional

import avro.schema
from authlib.integrations.httpx_client import OAuth2Client, AsyncOAuth2Client
from confluent_kafka import Consumer, KafkaException, Message

from .config import get_config
from .data_management import get_message_bus_details, DataManagementError
from .mtls_logging import logger
from .metrics import metrics_registry
from .schema_registry import get_schema, deserialize_message
from .topology_and_inventory import get_nr_cell_dus, get_sourceids_from_cells

FDN_PREFIX = "urn:3gpp:dn:"
AVRO_MAGIC_BYTE_COUNT = 5
NODE_FDN_HEADER_KEY = "nodeFDN"
MO_TYPE_HEADER_KEY = "moType"

fdn_to_pm_counter_status = {}


def _get_message_bus_connection_details(client: OAuth2Client) -> dict[str, str]:
    """Get the message bus connection details. If an exception is thrown here, it is fatal and will result in the app closing."""
    try:
        message_bus_details = get_message_bus_details(client)
    except DataManagementError as e:
        logger.critical(
            (
                f"Error occurred while retrieving message bus connection details: {e}"
                " Please contact your platform administrator. Exiting..."
            )
        )
        sys.exit(1)
    return message_bus_details


def _parse_message_headers(
    headers: list[tuple[str, Optional[bytes]]],
) -> list[list[str | bytes | None]]:
    """Parse and decode message headers."""
    parsed_headers = []
    for header in headers:
        if isinstance(header, tuple):
            formatted_header = [
                value.decode("utf-8") if isinstance(value, bytes) else value or ""
                for value in header
            ]
            parsed_headers.append(formatted_header)
    return parsed_headers


def _extract_schema_id(parsed_headers: list[list[str | bytes | None]]):
    """Extract schema ID from parsed headers."""
    return next(
        (header[1] for header in parsed_headers if header[0] == "schemaID"), None
    )


def _is_relevant_motype(
    parsed_headers: list[list[str | bytes | None]], motype: str = "NRCellDU_GNBDU"
) -> bool:
    """Check if the parsed headers contain the relevant moType."""
    logger.debug(f"Checking for relevant moType: {motype}")

    for header_message in parsed_headers:
        if header_message[0] == MO_TYPE_HEADER_KEY and header_message[1] == motype:
            metrics_registry.counters.get("filtered_messages_by_motype").inc()
            return True
    return False


def _is_relevant_node_fdn(
    parsed_headers: list[list[str | bytes | None]], prefixed_fdns: list[str]
) -> bool:
    """Check if the parsed headers contain the relevant nodeFdn."""
    logger.debug("Checking for relevant nodeFdn")

    for header_message in parsed_headers:
        if header_message[0] == NODE_FDN_HEADER_KEY:
            node_fdn_value = header_message[1]
            if any(node_fdn_value in fdn for fdn in prefixed_fdns):
                logger.debug(f"nodeFDN matched: {node_fdn_value}")
                return True
    return False


def _set_counter_status(
    deserialized_message: dict, prefixed_fdns: list[str], urn_dn_prefix_mo_fdn: str
):
    """If our message has counters for any of our FDNs, set `True` for that FDN in our status map."""
    if urn_dn_prefix_mo_fdn in prefixed_fdns:
        metrics_registry.counters.get("filtered_messages_by_fdn").inc()
        if deserialized_message.get("pmCounters") is not None:
            fdn_to_pm_counter_status[urn_dn_prefix_mo_fdn] = True
            logger.debug(f"PM kafka message counter status: {fdn_to_pm_counter_status}")


# pylint: disable=too-many-instance-attributes, disable=too-few-public-methods
class MessageBusConsumer:
    """
    A class for managing interactions with the message bus.

    This class provides methods to build the necessary configuration, subscribe to the message bus, and consume messages.

    Attributes:
        config: Configuration settings loaded from environment variables.
        schema: Schema used for decoding messages.
        prefixed_fdns: The FDNs of the cells which the application will query attributes and filter PM counters for.
        client: The synchronous OAuth client which will be used for consumption.
        async_client: Asynchronous client used for retrieval of the message schema.
        consumer: A confluent_kafka consumer client.
        messages_consumed: Total number of messages consumed.
        filtered_messages: Total number of messages filtered for NRCellDU.
        filtered_messages_by_motype: Metric: Number of messages that have been filtered by MO Type
        filtered_messages_by_fdn: Metric: Number of messages that are relevant to the cells collected at startup
        complete_batches_consumed: Metric: Total number of complete batches consumed
        incomplete_batches_consumed: Metric: Total number of batches which have reached timeout that are partially filled
        empty_batches_consumed: Metric: Total number of batches which have reached timeout with zero messages

    Methods:
        collect_counters: Begin PM counter collection infinitely.
        _consume_messages: Dispatch consumption to a separate thread and handle the resulting messages.
        _subscribe_to_topic: Fetch subscription details from Data Management and subscribe the consumer.
        _fetch_prefixed_fdns: By default, get 10 cells from Topology & Inventory.
            This populates the module variable `fdn_to_pm_counter_status` with their FDNs.
        _get_token_consumer_client_callback: Callback for the consumer config to use the HTTPX client token.
    """

    def __init__(
        self,
        client: OAuth2Client,
        async_client: AsyncOAuth2Client,
        consumer: Consumer = None,
    ):
        """
        Initializes an instance of the class.

        Args:
            client (OAuth2Client): The OAuth2 client used to interact with the IAM service.
            async_client (AsyncOAuth2Client): The AsyncOAuth2Client client used to fetch the avro schema.
            consumer (Consumer, optional): A Kafka consumer instance subscribed to the specified topic.
        """
        self.config: dict[str, str] = get_config()
        self.schema: avro.schema.Schema
        self.prefixed_fdns: list[str] = []

        self.client: OAuth2Client = client
        self.async_client: AsyncOAuth2Client = async_client
        self.consumer: Consumer = consumer or self._initialize_consumer()

        self.messages_consumed = metrics_registry.counters.get("messages_consumed")
        self.filtered_messages_by_motype = metrics_registry.counters.get(
            "filtered_messages_by_motype"
        )
        self.filtered_messages_by_fdn = metrics_registry.counters.get(
            "filtered_messages_by_fdn"
        )
        self.complete_batches_consumed = metrics_registry.counters.get(
            "complete_batch_of_messages_consumed"
        )
        self.incomplete_batches_consumed = metrics_registry.counters.get(
            "partial_batch_of_messages_consumed"
        )
        self.empty_batches_consumed = metrics_registry.counters.get(
            "empty_batch_of_messages_consumed"
        )

    async def collect_counters(self):
        """
        Continuously collect PM counters from the Message Bus.
        This method is meant to be used with asyncio.create_task, hence it catches CancelledError and handles cleanup as such.

        - Calls an API to initialize Topology data. It then enters an infinite loop, where it:
            - Consumes messages asynchronously from the message bus.
            - Logs total messages consumed and filtered messages.
            - Updates PM counter status.
        """
        try:
            await self._fetch_prefixed_fdns()

            logger.debug("Starting to collect PM counters from the message bus.")
            while True:
                await self._consume_messages()
        except asyncio.CancelledError:
            logger.info("Consumer is now closing.")
            self.consumer.close()

    async def _consume_messages(self):
        """
        Consume messages from Kafka.

        It performs the following steps:
        - Fetches messages from the Kafka consumer in batches.
        - Calls handle_valid_message api for further processing
        """
        batch_size = int(self.config.get("consumer_message_batch_size"))
        consumer_timeout = float(self.config.get("consumer_timeout"))
        try:
            messages = await asyncio.to_thread(
                self.consumer.consume, num_messages=batch_size, timeout=consumer_timeout
            )
            messages_length = len(messages)
            if messages_length > 0:
                self.messages_consumed.inc(messages_length)
                if messages_length < batch_size:
                    self.incomplete_batches_consumed.inc()
                else:
                    self.complete_batches_consumed.inc()
            else:
                self.empty_batches_consumed.inc()
            messages = [
                message
                for message in messages
                if message and not self.__is_error(message)
            ]
            logger.debug(f"Got {len(messages)} msgs in this batch.")
            start_time = time.perf_counter()
            await asyncio.gather(
                *(self.__handle_valid_message(message) for message in messages)
            )
            elapsed_time = time.perf_counter() - start_time
            logger.debug(f"Deserialized a batch in {elapsed_time:.4f} seconds")
        except KafkaException as e:
            self.__handle_kafka_error(e)
        except RuntimeError as e:
            logger.critical(f"Tried to consume after consumer was closed: {e}")
            sys.exit(1)

    def _initialize_consumer(self) -> Consumer:
        """Subscribe to the message bus."""
        message_bus_connection_details = _get_message_bus_connection_details(
            self.client
        )
        consumer_config = self.__build_consumer_config(
            message_bus_connection_details, self.config
        )
        consumer = Consumer(consumer_config)
        topic = message_bus_connection_details.get("topic")
        try:
            consumer.subscribe([topic])
            logger.debug(f"Subscribed to Kafka topic: {topic}")
            return consumer
        except KafkaException as e:
            self.__handle_kafka_error(e)
            return None

    async def _fetch_prefixed_fdns(self):
        """
        Query Topology & Inventory for cell information. By default, this will receive 10 cells.

        This method:
        - Fetches cells from the topology API.
        - Extracts `sourceIds` for NRCellDU.
        - Initializes `fdn_to_pm_counter_status` with `False` for each extracted source ID.
        """
        logger.debug("Querying Topology & Inventory for cell data.")
        cells = await get_nr_cell_dus(self.async_client)
        self.prefixed_fdns = get_sourceids_from_cells(cells)
        fdn_to_pm_counter_status.update({fdn: False for fdn in self.prefixed_fdns})
        logger.debug(
            f"Topology cell data from Topology API: {fdn_to_pm_counter_status}"
        )

    def _get_token_consumer_client_callback(self, _):
        """
        Provide the confluent_kafka client access to our HTTPX client's token.
        The confluent_kafka oauth_cb expects expiry time to be time since epoch.
        """
        token_expiry_leeway_seconds = 5
        logger.debug("Fetching access token for message bus consumer")
        token = self.client.fetch_token()
        access_token = token["access_token"]
        expiry_time = time.time() + token["expires_in"] - token_expiry_leeway_seconds
        return access_token, expiry_time

    async def __handle_valid_message(self, message: Message):
        """
        Asynchronously process a valid Kafka message.

        This method will:
        - Decode header
        - Extract schema ID
        - If MO type is relevant, pass the message on for further processing

        Args:
            message: A Kafka message object that has been validated.
        """
        parsed_headers = _parse_message_headers(message.headers())
        mo_type_matched = _is_relevant_motype(parsed_headers)

        if mo_type_matched:
            node_fdn_matched = _is_relevant_node_fdn(parsed_headers, self.prefixed_fdns)

            if node_fdn_matched:
                schema_id = _extract_schema_id(parsed_headers)

                if not schema_id:
                    logger.warning(
                        "Received a message without a schema ID in its headers"
                    )
                    return

                self.schema = await get_schema(
                    self.config.get("eic_host_url"), self.async_client, schema_id
                )

                await self.__process_message(message, schema_id)

    async def __process_message(self, message: Message, schema_id: str):
        """
        Process a Kafka message end-to-end.

        This method extracts and processes a message's contents by:
        - Deserializing the message
        - Retrieving the full prefixed_fdn from a received message
        - Storing the latest ROP time
        - Flags any matching prefixed_fdn if PM counters for it were received
        """
        avro_value = message.value()[AVRO_MAGIC_BYTE_COUNT:]
        deserialized_message = deserialize_message(avro_value, self.schema, schema_id)

        urn_dn_prefix_mo_fdn = (
            FDN_PREFIX
            + deserialized_message.get("dnPrefix")
            + ","
            + deserialized_message.get("moFdn")
        )
        logger.debug(f"urn_dnPrefix_moFdn from message: {urn_dn_prefix_mo_fdn}")

        _set_counter_status(
            deserialized_message, self.prefixed_fdns, urn_dn_prefix_mo_fdn
        )

    def __build_consumer_config(
        self, conn_details: dict[str, str], config: dict[str, str]
    ) -> dict[str, str]:
        """
        Build the configuration required to connect and consume from the message bus.

        Refer to [How to consume a message](https://developer.intelligentautomationplatform.ericsson.net/#capabilities/messagebus/developer-guide?chapter=how-to-consume-a-message) section for more details.
        """
        consumer_config = {
            "group.id": config.get("iam_client_id") + "-consumer-group",
            "bootstrap.servers": conn_details["hostname"]
            + ":"
            + str(conn_details["port"]),
            "isolation.level": "read_committed",
            "auto.offset.reset": "latest",
            "error_cb": self.__handle_kafka_error,
            "sasl.mechanisms": "OAUTHBEARER",
            "oauth_cb": partial(self._get_token_consumer_client_callback),
            "sasl.oauthbearer.config": "oauth_cb",
            "security.protocol": "SASL_SSL",
            "ssl.ca.location": config.get("kafka_cert_file_path"),
        }

        return consumer_config

    def __handle_kafka_error(self, err):
        """
        Handle error messages received from Kafka.

        Since all exceptions are caught by confluent_kafka, it's not possible to exit directly if an error is fatal, so the consumer
        is closed and the application exit is handled when another consume is attempted.

        More info:
        https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html#kafka-client-configuration
        """
        if isinstance(err, KafkaException):
            err = err.args[0]  # retrieve the KafkaError wrapped in this exception
        if err.fatal():
            logger.critical(
                f"Fatal error occurred while consuming messages from Kafka. App will close shortly. {err}"
            )
            self.consumer.close()  # use sys.exit later when we try to consume with a closed consumer
        else:
            logger.error(f"An error occurred while interacting with Kafka: {err}")

    def __is_error(self, message: Message) -> bool:
        """
        Check if the received Kafka message contains an error and handle it appropriately.
        For more details on handling Kafka message errors, refer to: [confluent_kafka.Message.error](https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html#confluent_kafka.Message.error)
        """
        if message.error():
            self.__handle_kafka_error(message.error())
            return True
        return False


async def start_message_bus_consumer(
    message_bus_consumer: MessageBusConsumer,
) -> asyncio.Task:
    """Starts the message bus consumer task."""
    return asyncio.create_task(message_bus_consumer.collect_counters())
