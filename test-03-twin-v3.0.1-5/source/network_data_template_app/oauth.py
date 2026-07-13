"""
This module implements an asynchronous http client with automatic token refreshing.
"""

import os

from urllib.parse import urljoin
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client

from .config import get_config


class OAuth:
    """Create and manage an OAuth-enabled HTTPX session."""

    def __init__(self):
        self.oauth_client = None
        self.token = None

    async def setup_client(self):
        """Set up an AsyncOAuth2Client with automatic token refreshing."""
        config = get_config()

        login_path = "/auth/realms/master/protocol/openid-connect/token"
        login_url = urljoin(config.get("eic_host_url"), login_path)

        cert = os.path.join(
            "/", config.get("ca_cert_file_path"), config.get("ca_cert_file_name")
        )
        self.oauth_client = AsyncOAuth2Client(
            config.get("iam_client_id"),
            config.get("iam_client_secret"),
            scope="openid",
            token_endpoint=login_url,
            verify=cert,
        )
        try:
            self.token = await self.oauth_client.fetch_token()
        except:
            self.token = None

    async def set_oauth_client(self, oauth_client: AsyncOAuth2Client):
        """Set the AsyncOAuth2Client"""
        if self.oauth_client:
            await self.oauth_client.aclose()
        self.oauth_client = oauth_client
        try:
            self.token = await self.oauth_client.fetch_token()
        except:
            self.token = None

    async def get_oauth_client(self) -> AsyncOAuth2Client:
        """Get the AsyncOAuth2Client"""
        if not self.token:
            if self.oauth_client:
                await self.oauth_client.aclose()
            await self.setup_client()
        return self.oauth_client

    async def close_client(self):
        """Close the client if we are cleaning up."""
        await self.oauth_client.aclose()


oauth = OAuth()


class SynchronousOAuth:
    """Create and manage an OAuth-enabled HTTPX session."""

    def __init__(self):
        self.oauth_client = None
        self.token = None

    def setup_client(self):
        """Set up an OAuth2Client with automatic token refreshing."""
        config = get_config()

        login_path = "/auth/realms/master/protocol/openid-connect/token"
        login_url = urljoin(config.get("eic_host_url"), login_path)

        cert = os.path.join(
            "/", config.get("ca_cert_file_path"), config.get("ca_cert_file_name")
        )

        self.oauth_client = OAuth2Client(
            config.get("iam_client_id"),
            config.get("iam_client_secret"),
            scope="openid",
            token_endpoint=login_url,
            verify=cert,
        )

        try:
            self.token = self.oauth_client.fetch_token()
        except:
            self.token = None

    def set_oauth_client(self, oauth_client: OAuth2Client):
        """Set the OAuth2Client"""
        if self.oauth_client:
            self.oauth_client.close()
        self.oauth_client = oauth_client
        try:
            self.token = self.oauth_client.fetch_token()
        except:
            self.token = None

    def get_oauth_client(self) -> OAuth2Client:
        """Get the OAuth2Client"""
        if not self.token:
            self.setup_client()
        return self.oauth_client

    def close_client(self):
        """Close the client if we are cleaning up."""
        self.oauth_client.close()


synchronous_oauth = SynchronousOAuth()
