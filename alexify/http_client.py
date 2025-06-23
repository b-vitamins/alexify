import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class BaseHTTPClient(ABC):
    """Base class for HTTP clients with common configuration and retry logic."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _get_request_params(
        self, additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build base request parameters including email if configured."""
        params = additional_params or {}
        if self.config.get("email"):
            params["mailto"] = self.config["email"]
        return params

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried based on status code and attempt."""
        return (
            status_code in self.config["retry_codes"]
            and attempt < self.config["max_retries"] - 1
        )

    def _get_wait_time(self, retry_after: Optional[str], attempt: int) -> float:
        """Calculate wait time from Retry-After header or exponential backoff."""
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                logger.warning(
                    f"Could not parse Retry-After header '{retry_after}', using default backoff"
                )
        return self.config["backoff"] * (2**attempt)

    @abstractmethod
    def make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[dict]:
        """Make HTTP request with retry logic."""
        pass


class SyncHTTPClient(BaseHTTPClient):
    """Synchronous HTTP client with retry logic."""

    def make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[dict]:
        """Make synchronous HTTP request with retry logic."""
        last_exception = None
        request_params = self._get_request_params(params)

        for attempt in range(self.config["max_retries"]):
            try:
                with httpx.Client() as client:
                    resp = client.get(
                        url, params=request_params, timeout=self.config["timeout"]
                    )

                    # Handle rate limiting and server errors
                    if resp.status_code in self.config["retry_codes"]:
                        if self._should_retry(resp.status_code, attempt):
                            retry_after = resp.headers.get("Retry-After")
                            wait_time = self._get_wait_time(retry_after, attempt)

                            if retry_after:
                                logger.warning(
                                    f"Rate limited. Waiting {wait_time}s as requested by server"
                                )
                            else:
                                logger.warning(
                                    f"HTTP {resp.status_code}. Retrying in {wait_time}s "
                                    f"(attempt {attempt + 1}/{self.config['max_retries']})"
                                )

                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Max retries exceeded for {url}")

                    if resp.status_code == 400:
                        logger.debug(f"Bad request (400) for URL: {url}")
                        if params:
                            logger.debug(f"Parameters: {params}")
                        return None

                    resp.raise_for_status()
                    return resp.json()

            except httpx.TimeoutException as exc:
                last_exception = exc
                if self._should_retry(
                    0, attempt
                ):  # Use 0 for timeout, won't match retry_codes
                    wait_time = self._get_wait_time(None, attempt)
                    logger.warning(
                        f"Request timeout. Retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.config['max_retries']})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(
                    f"Request timeout after {self.config['max_retries']} attempts: {exc}"
                )

            except httpx.HTTPError as exc:
                last_exception = exc
                if self._should_retry(
                    0, attempt
                ):  # Use 0 for HTTP error, won't match retry_codes
                    wait_time = self._get_wait_time(None, attempt)
                    logger.warning(
                        f"HTTP error: {exc}. Retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.config['max_retries']})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(
                    f"HTTP error after {self.config['max_retries']} attempts: {exc}"
                )

        # If we get here, all retries failed
        if last_exception:
            logger.error(f"All retry attempts failed for {url}: {last_exception}")

        return None


class AsyncHTTPClient(BaseHTTPClient):
    """Asynchronous HTTP client with retry logic."""

    def __init__(self, config: Dict[str, Any], client: httpx.AsyncClient):
        super().__init__(config)
        self.client = client

    async def make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[dict]:
        """Make asynchronous HTTP request with retry logic."""
        last_exception = None
        request_params = self._get_request_params(params)

        for attempt in range(self.config["max_retries"]):
            try:
                resp = await self.client.get(
                    url, params=request_params, timeout=self.config["timeout"]
                )

                # Handle rate limiting and server errors
                if resp.status_code in self.config["retry_codes"]:
                    if self._should_retry(resp.status_code, attempt):
                        retry_after = resp.headers.get("Retry-After")
                        wait_time = self._get_wait_time(retry_after, attempt)

                        if retry_after:
                            logger.warning(
                                f"Rate limited. Waiting {wait_time}s as requested by server"
                            )
                        else:
                            logger.warning(
                                f"HTTP {resp.status_code}. Retrying in {wait_time}s "
                                f"(attempt {attempt + 1}/{self.config['max_retries']})"
                            )

                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for {url}")

                if resp.status_code == 400:
                    logger.debug(f"Bad request (400) for URL: {url}")
                    if params:
                        logger.debug(f"Parameters: {params}")
                    return None

                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException as exc:
                last_exception = exc
                if self._should_retry(
                    0, attempt
                ):  # Use 0 for timeout, won't match retry_codes
                    wait_time = self._get_wait_time(None, attempt)
                    logger.warning(
                        f"Request timeout. Retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.config['max_retries']})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(
                    f"Request timeout after {self.config['max_retries']} attempts: {exc}"
                )

            except httpx.HTTPError as exc:
                last_exception = exc
                if self._should_retry(
                    0, attempt
                ):  # Use 0 for HTTP error, won't match retry_codes
                    wait_time = self._get_wait_time(None, attempt)
                    logger.warning(
                        f"HTTP error: {exc}. Retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.config['max_retries']})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(
                    f"HTTP error after {self.config['max_retries']} attempts: {exc}"
                )

        # If we get here, all retries failed
        if last_exception:
            logger.error(f"All retry attempts failed for {url}: {last_exception}")

        return None


def create_sync_client(config: Dict[str, Any]) -> SyncHTTPClient:
    """Factory function to create synchronous HTTP client."""
    return SyncHTTPClient(config)


def create_async_client(
    config: Dict[str, Any], client: httpx.AsyncClient
) -> AsyncHTTPClient:
    """Factory function to create asynchronous HTTP client."""
    return AsyncHTTPClient(config, client)
