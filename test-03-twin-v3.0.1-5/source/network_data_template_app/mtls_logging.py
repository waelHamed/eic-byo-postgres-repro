"""This module handles mTLS logging"""

import asyncio
import json
import logging
import os
import ssl
import sys
from datetime import datetime, timezone
from enum import IntEnum

import httpx

from network_data_template_app.config import get_config, get_os_env_string


class Severity(IntEnum):
    """Mapping of logging library severities to log aggregator level names"""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


# pylint: disable=too-many-instance-attributes
class _MTLSLogger:
    """Logger object capable of logging to the console and log aggregator."""

    def __init__(
        self, console_logger: "_ConsoleLogger", mtls_log_level=Severity.INFO
    ) -> None:
        self.console_logger = console_logger
        self.mtls_log_level = mtls_log_level
        self.config = get_config()
        self.ready = asyncio.Event()
        self.log_url = "https://" + self.config.get("log_endpoint")

        # Load configuration
        self.is_cert_available = (
            self.config.get("ca_cert_file_name") != ""
            and self.config.get("ca_cert_file_path") != ""
            and self.config.get("app_cert") != ""
            and self.config.get("app_key") != ""
            and self.config.get("app_cert_file_path") != ""
        )

        if self.is_cert_available:
            self.ca_cert = os.path.join(
                "/",
                self.config.get("ca_cert_file_path"),
                self.config.get("ca_cert_file_name"),
            )
            self.app_cert = os.path.join(
                "/",
                self.config.get("app_cert_file_path"),
                self.config.get("app_cert"),
            )
            self.app_key = os.path.join(
                "/",
                self.config.get("app_cert_file_path"),
                self.config.get("app_key"),
            )

            self.client = self._create_client()
            self.client.headers.update({"Content-Type": "application/json"})
            self.log_queue = asyncio.Queue()

        if self.config.get("log_ctrl_file"):
            log_ctrl_file = self.config.get("log_ctrl_file")
            log_control = json.loads(log_ctrl_file)
            container_name = get_os_env_string("CONTAINER_NAME", "")
            for json_entry in log_control:
                if json_entry.get("container") == container_name:
                    match json_entry.get("severity").lower():
                        case "critical":
                            self.mtls_log_level = Severity.CRITICAL
                        case "error":
                            self.mtls_log_level = Severity.ERROR
                        case "warning":
                            self.mtls_log_level = Severity.WARNING
                        case "debug":
                            self.mtls_log_level = Severity.DEBUG
                    self.console_logger.set_console_log_level(self.mtls_log_level)
                    break
            else:
                self.console_logger.warning(
                    f"Unable to set logging severity from Log Control file. No severity specified for container name '{container_name}'. "
                    "Please ensure the container name is defined correctly in the Log Control file. "
                    f"Defaulting to {self.mtls_log_level.name}."
                )

    async def start_log_sender(self) -> None:
        """Create a background task that will send messages to log aggregator."""

        if self.is_cert_available:
            asyncio.create_task(self.__log_sender_task())
            await self.ready.wait()
        else:
            missing_parameters = ""
            for k, v in self.config.items():
                if v == "":
                    missing_parameters += k + " "
            self.console_logger.error(
                f"Missing TLS logging additional parameter(s): {missing_parameters}"
            )
            self.console_logger.warning("Logs will only appear in stdout")

    def debug(self, message: str) -> None:
        """Log at debug level."""
        self.console_logger.debug(message)
        self.__prepare_and_queue_message(message, Severity.DEBUG)

    def info(self, message: str) -> None:
        """Log at info level."""
        self.console_logger.info(message)
        self.__prepare_and_queue_message(message, Severity.INFO)

    def warning(self, message: str) -> None:
        """Log at warning level."""
        self.console_logger.warning(message)
        self.__prepare_and_queue_message(message, Severity.WARNING)

    def error(self, message: Exception | str, **kwargs) -> None:
        """Log at error level."""
        if isinstance(message, str):
            self.console_logger.error(message)
            self.__prepare_and_queue_message(message, Severity.ERROR)
        else:
            self.console_logger.error(message, **kwargs)

    def critical(self, message: str) -> None:
        """Log at critical level."""
        self.console_logger.critical(message)
        self.__prepare_and_queue_message(message, Severity.CRITICAL)

    def __prepare_and_queue_message(self, message: str, severity: Severity) -> None:
        """Convert message string into json data and enqueue it

        Args:
            message (str): log message to be sent
            severity (Severity): severity of the message
        """

        if self.is_cert_available and severity >= self.mtls_log_level:
            time = datetime.now(timezone.utc).isoformat()
            json_data = {
                "timestamp": time,
                "severity": severity.name.lower(),
                "service_id": self.config.get("service_name"),
                "message": message,
                "version": "0.0.1",
            }
            # Ensure any logging calls from other threads are handled on the main event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            asyncio.run_coroutine_threadsafe(self.log_queue.put(json_data), loop)

    async def __log_sender_task(self):
        """Read json data from the queue and send it to log aggregator"""
        self.ready.set()
        while True:
            json_message = await self.log_queue.get()
            try:
                response = await self.client.post(self.log_url, json=json_message)
                response.raise_for_status()
            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                self.console_logger.error(
                    f"Request failed for mTLS logging: exception={e}"
                )
            finally:
                self.log_queue.task_done()

    def _create_client(self):
        ssl_context = ssl.create_default_context()
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
        ssl_context.load_verify_locations(self.ca_cert)
        ssl_context.load_cert_chain(self.app_cert, self.app_key)

        return httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            timeout=10,
            verify=ssl_context,
        )


class _ConsoleLogger:
    def __init__(self, name: str, console_log_level=None) -> None:
        self.__logger = logging.getLogger(name)
        if not self.__logger.hasHandlers():
            self.__logger.setLevel(console_log_level)
            logger_console_handler = logging.StreamHandler(stream=sys.stdout)
            console_logger_format = logging.Formatter(
                fmt="[%(asctime)s.%(msecs)03d] %(name)s [%(levelname)s] %(message)s",
                datefmt="%d-%m-%Y %H:%M:%S",
            )
            logger_console_handler.setFormatter(console_logger_format)
            logger_console_handler.setLevel(console_log_level)
            self.__logger.addHandler(logger_console_handler)
        else:
            self.__logger.setLevel(console_log_level)

    def debug(self, record: str) -> None:
        """Log at debug level."""
        self.__logger.debug(record)

    def info(self, record: str) -> None:
        """Log at info level."""
        self.__logger.info(record)

    def warning(self, record: str) -> None:
        """Log at warning level."""
        self.__logger.warning(record)

    def error(self, record: Exception | str, **kwargs) -> None:
        """Log at error level."""
        self.__logger.error(record, **kwargs)

    def critical(self, record: str) -> None:
        """Log at critical level."""
        self.__logger.critical(record)

    def set_console_log_level(self, console_log_level) -> None:
        """Set console log level."""
        self.__logger.setLevel(console_log_level)
        for handler in self.__logger.handlers:
            handler.setLevel(console_log_level)

    def get_console_log_level(self) -> Severity:
        """Get console log level."""
        return self.__logger.level


logger = _MTLSLogger(
    console_logger=_ConsoleLogger(
        name=get_config()["container_name"], console_log_level=Severity.INFO
    )
)
