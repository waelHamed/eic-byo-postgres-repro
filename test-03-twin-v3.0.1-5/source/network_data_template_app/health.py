"""
This module provides a simple health check for liveness and readiness probes.
"""

from fastapi_healthchecks.checks import Check, CheckResult


# pylint: disable=too-few-public-methods
class SimpleHealthCheck(Check):
    """
    Simple health check class (to be changed).
    """

    async def __call__(self) -> CheckResult:
        return CheckResult(name="server", passed=True)
