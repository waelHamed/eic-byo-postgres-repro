"""Tests which cover the app's logging, both to STDOUT and to Log Aggregator"""

import asyncio
import inspect
import json
import os
from unittest.mock import mock_open, patch

import httpx
import pytest
import respx

from network_data_template_app.mtls_logging import _MTLSLogger, _ConsoleLogger, Severity


@pytest.mark.asyncio
async def test_log_stdout_and_not_mtls(no_log_certs, caplog):
    # pylint: disable=unused-argument
    """Ensure log is only sent to STDOUT when missing log certs"""
    message = "Message which should appear in STDOUT"
    exception_message = "Exception which should appear in STDOUT"
    error_message = "Missing TLS logging additional parameter(s): log_ctrl_file app_key app_cert app_cert_file_path"
    await send_log(message, Severity.DEBUG, Severity.CRITICAL)
    await send_log(Exception(exception_message), Severity.ERROR, Severity.ERROR)
    assert message in caplog.text
    assert exception_message in caplog.text
    assert error_message in caplog.text


@pytest.mark.asyncio
async def test_log_level_matching_severity(no_log_certs, caplog):
    """Ensure a log will output if it matches the severity level of the logger"""
    for severity in Severity:
        message = f"Message sent with severity {severity}, should be logged in STDOUT and through POST"
        await send_log(message, severity, severity)
        assert message in caplog.text


@pytest.mark.asyncio
async def test_log_ignored(no_log_certs, caplog):
    """Ensure that a log will be ignored if we set the minimum severity higher"""
    message = "Message which should appear in both STDOUT and sent as a POST request"
    # This test will still call once because the logger announces its log level as INFO severity
    await send_log(message, Severity.INFO, Severity.DEBUG)
    assert not message in caplog.text


@pytest.mark.asyncio
async def test_log_sender_task_success(config, mock_logger, caplog):
    message = f"Test log from {inspect.currentframe().f_code.co_name}"
    mock_logger.log_url = config.get("log_endpoint")
    with respx.mock() as log_endpoint_mock:
        log_endpoint_mock.post(mock_logger.log_url) % httpx.Response(status_code=200)
        task = asyncio.create_task(mock_logger._MTLSLogger__log_sender_task())
        await mock_logger.log_queue.put(message)

        async def check_respx_calls():
            while len(log_endpoint_mock.calls) == 0:
                await asyncio.sleep(0.1)  # Prevents busy-waiting

        await asyncio.wait_for(check_respx_calls(), timeout=1)
        task.cancel()
        assert len(log_endpoint_mock.calls) == 1


@pytest.mark.parametrize("severity", ["debug", "info", "warning", "error", "critical"])
def test_log_control_file_parsing_success(config, no_log_certs, severity):
    mock_logcontrol_json = json.dumps(
        [
            {
                "severity": severity,
                "container": os.environ["CONTAINER_NAME"],
            }
        ]
    )
    os.environ["LOG_CTRL_FILE"] = mock_logcontrol_json
    logger = _MTLSLogger(
        _ConsoleLogger("log-control-test-logger", console_log_level=Severity.INFO)
    )
    assert logger.mtls_log_level.name.lower() == severity
    assert logger.console_logger.get_console_log_level().name.lower() == severity


def test_log_control_file_undefined_container(config, no_log_certs):
    mock_logcontrol_json = json.dumps(
        [
            {
                "severity": "debug",
                "container": "undefined",
            }
        ]
    )
    os.environ["LOG_CTRL_FILE"] = mock_logcontrol_json
    logger = _MTLSLogger(
        _ConsoleLogger("log-control-test-logger", console_log_level=Severity.INFO)
    )
    assert logger.mtls_log_level.name.lower() == "info"
    assert logger.console_logger.get_console_log_level().name.lower() == "info"


def test_logger_with_missing_certs(config, log_control_file):
    with pytest.raises(FileNotFoundError):
        logger = _MTLSLogger(
            _ConsoleLogger("fullrays-twin", console_log_level=10)
        )


################################### HELPERS ###################################
@pytest.mark.asyncio
async def send_log(message, logger_level, log_level):
    """Send a log through the MTLS logger"""
    logger = _MTLSLogger(
        console_logger=_ConsoleLogger(
            name="fullrays-twin", console_log_level=logger_level
        )
    )
    await logger.start_log_sender()
    match log_level:
        case Severity.CRITICAL:
            logger.critical(message)
        case Severity.ERROR:
            logger.error(message)
        case Severity.WARNING:
            logger.warning(message)
        case Severity.INFO:
            logger.info(message)
        case Severity.DEBUG:
            logger.debug(message)
