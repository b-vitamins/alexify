import asyncio
import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


def validate_openalex_response(data: Any, endpoint_type: str = "works") -> bool:
    """
    Validate OpenAlex API response structure.
    Returns True if response is valid, False otherwise.
    """
    if not data or not isinstance(data, dict):
        logger.warning(f"Invalid {endpoint_type} response: not a dictionary")
        return False

    # Check for required top-level fields
    if "results" not in data:
        logger.warning(f"Invalid {endpoint_type} response: missing 'results' field")
        return False

    if not isinstance(data["results"], list):
        logger.warning(f"Invalid {endpoint_type} response: 'results' is not a list")
        return False

    # Validate individual work entries if present
    if endpoint_type == "works" and data["results"]:
        for i, work in enumerate(data["results"][:5]):  # Check first 5 entries
            if not isinstance(work, dict):
                logger.warning(f"Invalid work entry {i}: not a dictionary")
                continue

            # Check for essential work fields
            if "id" not in work:
                logger.warning(f"Work entry {i} missing 'id' field")
                continue

            if "title" not in work:
                logger.warning(f"Work entry {i} missing 'title' field")

    return True


class AsyncBoundedCache:
    """Async thread-safe bounded cache with LRU eviction policy."""

    def __init__(self, maxsize: int = 1000):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get value from cache, moving key to end (most recently used)."""
        async with self._lock:
            if key not in self._cache:
                return None
            # Move to end (most recently used)
            value = self._cache.pop(key)
            self._cache[key] = value
            return value

    async def put(self, key: str, value: List[Dict[str, Any]]) -> None:
        """Put value in cache, evicting oldest if necessary."""
        async with self._lock:
            if key in self._cache:
                # Update existing key (move to end)
                self._cache.pop(key)
            elif len(self._cache) >= self._maxsize:
                # Remove oldest item (first in OrderedDict)
                self._cache.popitem(last=False)

            self._cache[key] = value

    async def clear(self) -> None:
        """Clear the cache."""
        async with self._lock:
            self._cache.clear()


# Async thread-safe bounded cache for search results
_ASYNC_SEARCH_CACHE = AsyncBoundedCache(maxsize=1000)

# Configuration for OpenAlex API
_CONFIG = {
    "email": None,
    "max_retries": 10,
    "backoff": 0.5,
    "retry_codes": [429, 500, 503],
    "timeout": 30.0,
    "max_concurrent_requests": 20,  # Maximum concurrent API requests
}


def init_async_config(
    email: Optional[str] = None,
    max_retries: int = 10,
    backoff: float = 0.5,
    retry_codes: List[int] = [429, 500, 503],
    timeout: float = 30.0,
    max_concurrent_requests: int = 20,
):
    """Initialize configuration for async OpenAlex API usage."""
    _CONFIG["email"] = email
    _CONFIG["max_retries"] = max_retries
    _CONFIG["backoff"] = backoff
    _CONFIG["retry_codes"] = retry_codes
    _CONFIG["timeout"] = timeout
    _CONFIG["max_concurrent_requests"] = max_concurrent_requests


async def _make_request_with_retry_async(
    client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
) -> Optional[dict]:
    """Make async HTTP request with retry logic."""
    last_exception = None

    for attempt in range(_CONFIG["max_retries"]):
        try:
            resp = await client.get(url, params=params, timeout=_CONFIG["timeout"])

            # Handle rate limiting and server errors
            if resp.status_code in _CONFIG["retry_codes"]:
                if attempt < _CONFIG["max_retries"] - 1:
                    # Check for Retry-After header
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            # Try to parse as seconds (integer)
                            wait_time = float(retry_after)
                        except ValueError:
                            # If it's a date string, use default backoff
                            wait_time = _CONFIG["backoff"] * (2**attempt)
                            logger.warning(
                                f"Could not parse Retry-After header '{retry_after}', using default backoff"
                            )
                        logger.warning(
                            f"Rate limited. Waiting {wait_time}s as requested by server"
                        )
                    else:
                        wait_time = _CONFIG["backoff"] * (2**attempt)
                        logger.warning(
                            f"HTTP {resp.status_code}. Retrying in {wait_time}s (attempt {attempt + 1}/{_CONFIG['max_retries']})"
                        )

                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries exceeded for {url}")

            if resp.status_code == 400:
                # Bad request - log and return None instead of retrying
                logger.debug(f"Bad request (400) for URL: {url}")
                if params:
                    logger.debug(f"Parameters: {params}")
                return None

            resp.raise_for_status()
            return resp.json()

        except httpx.TimeoutException as exc:
            last_exception = exc
            if attempt < _CONFIG["max_retries"] - 1:
                wait_time = _CONFIG["backoff"] * (2**attempt)
                logger.warning(
                    f"Request timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{_CONFIG['max_retries']})"
                )
                await asyncio.sleep(wait_time)
                continue
            logger.error(
                f"Request timeout after {_CONFIG['max_retries']} attempts: {exc}"
            )

        except httpx.HTTPError as exc:
            last_exception = exc
            if attempt < _CONFIG["max_retries"] - 1:
                wait_time = _CONFIG["backoff"] * (2**attempt)
                logger.warning(
                    f"HTTP error: {exc}. Retrying in {wait_time}s (attempt {attempt + 1}/{_CONFIG['max_retries']})"
                )
                await asyncio.sleep(wait_time)
                continue
            logger.error(f"HTTP error after {_CONFIG['max_retries']} attempts: {exc}")

    # If we get here, all retries failed
    if last_exception:
        logger.error(f"All retry attempts failed for {url}: {last_exception}")

    return None


async def fetch_openalex_works_async(
    query: Optional[str], client: httpx.AsyncClient
) -> List[Dict[str, Any]]:
    """
    Async search OpenAlex works for the given query string, caching results.
    Returns a list of works (as dicts).
    """
    if not query or not isinstance(query, str):
        return []

    # Check cache first
    cached_result = await _ASYNC_SEARCH_CACHE.get(query)
    if cached_result is not None:
        return cached_result

    try:
        logger.info(f"Searching OpenAlex for query: {query}")

        # Build parameters
        params = {
            "search": query,
            "per_page": 50,  # OpenAlex max per page
        }
        if _CONFIG["email"]:
            params["mailto"] = _CONFIG["email"]

        data = await _make_request_with_retry_async(
            client, "https://api.openalex.org/works", params=params
        )

        if data and validate_openalex_response(data, "works"):
            works_list = data["results"]
            # Update cache
            await _ASYNC_SEARCH_CACHE.put(query, works_list)
            return works_list
        return []

    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.error(f"HTTP error searching OpenAlex for '{query}': {exc}")
        return []
    except Exception as exc:
        logger.error(f"Unexpected error searching OpenAlex for '{query}': {exc}")
        return []


async def fetch_all_candidates_for_entry_async(
    title: str, authors_first_author_ln: str, year: str, client: httpx.AsyncClient
) -> List[Dict[str, Any]]:
    """
    Async version of fetch_all_candidates_for_entry.
    Given a BibTeX entry's title, first author lastname, and year, attempt
    to find all candidate Works from the OpenAlex API.
    """
    title_cleaned = title.replace("{", "").replace("}", "").strip() if title else ""
    author_cleaned = (
        authors_first_author_ln.replace("{", "").replace("}", "").strip()
        if authors_first_author_ln
        else ""
    )
    year_cleaned = year.strip() if year else ""

    if not title_cleaned:
        logger.debug("No title provided; returning []")
        return []

    # Build list of queries to try in order
    queries_to_try = []

    # First priority: all components if available
    if title_cleaned and author_cleaned and year_cleaned:
        queries_to_try.append(f"{title_cleaned} {author_cleaned} {year_cleaned}")
    elif title_cleaned and year_cleaned:
        queries_to_try.append(f"{title_cleaned} {year_cleaned}")

    # Second priority: title + author (no year)
    if title_cleaned and author_cleaned:
        query_with_author = f"{title_cleaned} {author_cleaned}"
        if query_with_author not in queries_to_try:
            queries_to_try.append(query_with_author)

    # Third priority: title only
    if title_cleaned and title_cleaned not in queries_to_try:
        queries_to_try.append(title_cleaned)

    # Try each query strategy concurrently and collect all results
    all_results = []
    seen_ids = set()

    # Execute queries concurrently
    tasks = [fetch_openalex_works_async(query, client) for query in queries_to_try]
    results_lists = await asyncio.gather(*tasks)

    for query, results in zip(queries_to_try, results_lists):
        if results:
            logger.info(f"Found {len(results)} results with query: {query}")
            # Add unique results
            for result in results:
                work_id = result.get("id")
                if work_id and work_id not in seen_ids:
                    seen_ids.add(work_id)
                    all_results.append(result)
            # If we have good results from title-only search, we can stop
            if len(all_results) >= 10 and query == title_cleaned:
                break

    logger.info(f"Total unique results collected: {len(all_results)}")
    return all_results


async def fetch_openalex_works_by_dois_async(
    dois: List[str], client: httpx.AsyncClient
) -> List[Optional[str]]:
    """
    Async version of fetch_openalex_works_by_dois.
    Given a list of DOIs, return a list of corresponding OpenAlex IDs,
    or None for each DOI that could not be resolved.

    Processes DOIs in batches concurrently.
    """
    if not dois:
        return []

    # Preprocess DOIs to the format expected by OpenAlex
    processed_dois = []
    for doi in dois:
        if doi:
            # Ensure DOI has https://doi.org/ prefix
            if not doi.startswith("http"):
                doi = f"https://doi.org/{doi}"
            processed_dois.append(doi)
        else:
            processed_dois.append(None)

    batch_size = 50
    openalex_ids: List[Optional[str]] = [None] * len(processed_dois)

    # Create tasks for all batches
    tasks = []
    batch_indices = []

    for i in range(0, len(processed_dois), batch_size):
        batch = processed_dois[i : i + batch_size]
        valid_dois = [d for d in batch if d is not None]

        if valid_dois:
            piped = "|".join(valid_dois)
            params = {"filter": f"doi:{piped}", "per_page": batch_size}

            # Add email if configured
            if _CONFIG["email"]:
                params["mailto"] = _CONFIG["email"]

            tasks.append(
                _make_request_with_retry_async(
                    client, "https://api.openalex.org/works", params=params
                )
            )
            batch_indices.append((i, batch))

    # Execute all batch requests concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for (batch_start, batch), result in zip(batch_indices, results):
        if isinstance(result, Exception):
            logger.error(f"Error fetching batch starting at {batch_start}: {result}")
            continue

        if not result or not validate_openalex_response(result, "works"):
            logger.error(f"Invalid or no results for batch starting at {batch_start}")
            continue

        # Build a map from returned DOIs => short IDs
        result_map = {}
        # At this point result is guaranteed to be a valid dict due to the checks above
        assert isinstance(result, dict)
        for w in result.get("results", []):
            if w.get("doi"):
                # Lowercase for consistency
                doi_key = w["doi"].lower()
                # Convert from "https://openalex.org/Wxxxx"
                short_id = w["id"].rsplit("/", 1)[-1]
                result_map[doi_key] = short_id

        # Map results back to original positions
        for idx, doi_item in enumerate(batch):
            if doi_item is not None:
                openalex_ids[batch_start + idx] = result_map.get(doi_item.lower(), None)

    return openalex_ids


# Semaphore for rate limiting concurrent requests with thread safety
_request_semaphore: Optional[asyncio.Semaphore] = None
_semaphore_lock = asyncio.Lock()


async def get_request_semaphore() -> asyncio.Semaphore:
    """Get or create the request semaphore for rate limiting with thread safety."""
    global _request_semaphore
    if _request_semaphore is None:
        async with _semaphore_lock:
            if _request_semaphore is None:  # Double-checked locking
                _request_semaphore = asyncio.Semaphore(
                    _CONFIG["max_concurrent_requests"]
                )
    return _request_semaphore


async def fetch_work_details_async(
    openalex_id: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Fetch detailed work information for a single OpenAlex ID."""
    url = f"https://api.openalex.org/works/{openalex_id}"

    semaphore = await get_request_semaphore()
    async with semaphore:
        try:
            params = {}
            if _CONFIG["email"]:
                params["mailto"] = _CONFIG["email"]

            data = await _make_request_with_retry_async(client, url, params=params)
            return data
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.error(f"HTTP error fetching work {openalex_id}: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Unexpected error fetching work {openalex_id}: {exc}")
            return None


async def fetch_multiple_works_async(
    openalex_ids: List[str], client: httpx.AsyncClient
) -> List[Optional[Dict[str, Any]]]:
    """Fetch details for multiple OpenAlex IDs concurrently."""
    tasks = [fetch_work_details_async(oid, client) for oid in openalex_ids]
    return await asyncio.gather(*tasks)
