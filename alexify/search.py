import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}

# Configuration for OpenAlex API
_CONFIG = {
    "email": None,
    "max_retries": 10,
    "backoff": 0.5,
    "retry_codes": [429, 500, 503],
}


def init_pyalex_config(
    email: Optional[str] = None,
    max_retries: int = 10,
    backoff: float = 0.5,
    retry_codes: List[int] = [429, 500, 503],
):
    """
    Initialize configuration parameters for OpenAlex API usage.
    If `email` is provided, it will be added to API requests for polite pool access.
    """
    _CONFIG["email"] = email
    _CONFIG["max_retries"] = max_retries
    _CONFIG["backoff"] = backoff
    _CONFIG["retry_codes"] = retry_codes


def _make_request_with_retry(
    client: httpx.Client, url: str, params: Optional[Dict[str, Any]] = None
) -> Optional[dict]:
    """
    Make HTTP request with retry logic.
    """
    for attempt in range(_CONFIG["max_retries"]):
        try:
            resp = client.get(url, params=params)
            if resp.status_code in _CONFIG["retry_codes"]:
                if attempt < _CONFIG["max_retries"] - 1:
                    time.sleep(_CONFIG["backoff"] * (2**attempt))
                    continue
            if resp.status_code == 400:
                # Bad request - log and return None instead of retrying
                logger.debug(f"Bad request (400) for URL: {url}")
                if params:
                    logger.debug(f"Parameters: {params}")
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            if attempt < _CONFIG["max_retries"] - 1:
                time.sleep(_CONFIG["backoff"] * (2**attempt))
                continue
            raise
    return None


def fetch_openalex_works(query: Optional[str]) -> List[Dict[str, Any]]:
    """
    Search OpenAlex works for the given query string, caching results.
    Returns a list of works (as dicts).

    Hardening:
      - If query is empty or None, return [] immediately.
      - Cache results to avoid repeated calls for the same query.
      - Catch HTTP errors => log & return [].
    """
    if not query or not isinstance(query, str):
        return []

    if query in _SEARCH_CACHE:
        return _SEARCH_CACHE[query]

    try:
        logger.debug(f"Searching OpenAlex for query: {query}")

        # Build parameters
        params = {
            "search": query,
            "per_page": 50,  # OpenAlex max per page
        }
        if _CONFIG["email"]:
            params["mailto"] = _CONFIG["email"]

        with httpx.Client() as client:
            data = _make_request_with_retry(
                client, "https://api.openalex.org/works", params=params
            )

            if data and "results" in data:
                works_list = data["results"]
                _SEARCH_CACHE[query] = works_list
                return works_list
            return []

    except Exception as exc:
        logger.error(f"Error searching OpenAlex for '{query}': {exc}")
        return []


def fetch_all_candidates_for_entry(
    title: str, authors_first_author_ln: str, year: str
) -> List[Dict[str, Any]]:
    """
    Given a BibTeX entry's title, first author lastname, and year, attempt
    to find all candidate Works from the OpenAlex API.

    Heuristics:
      - First try with all available components (title + author + year)
      - If no results and we have year, try without year
      - If still no results and we have author, try title only
      - Otherwise => return [].

    Returns a list of works (each a dict).
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

    # Try each query strategy and collect all results
    all_results = []
    seen_ids = set()

    for query in queries_to_try:
        logger.debug(f"Trying query: {query}")
        results = fetch_openalex_works(query)
        if results:
            logger.debug(f"Found {len(results)} results with query: {query}")
            # Add unique results
            for result in results:
                work_id = result.get("id")
                if work_id and work_id not in seen_ids:
                    seen_ids.add(work_id)
                    all_results.append(result)
            # If we have good results from title-only search, we can stop
            if len(all_results) >= 10 and query == title_cleaned:
                break

    logger.debug(f"Total unique results collected: {len(all_results)}")
    return all_results


def fetch_openalex_works_by_dois(dois: List[str]) -> List[Optional[str]]:
    """
    Given a list of DOIs, return a list of corresponding OpenAlex IDs,
    or None for each DOI that could not be resolved.

    Processes DOIs in batches of 50 (the API max).
    """
    if not dois:
        return []

    openalex_ids = []

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

    with httpx.Client() as client:
        for i in range(0, len(processed_dois), batch_size):
            batch = processed_dois[i : i + batch_size]

            # For mapping results after fetch
            local_results = [None] * len(batch)

            # Build the filter portion
            valid_dois = [d for d in batch if d is not None]
            if not valid_dois:
                openalex_ids.extend(local_results)
                continue

            piped = "|".join(valid_dois)
            params = {"filter": f"doi:{piped}", "per_page": batch_size}

            # Add email if configured
            if _CONFIG["email"]:
                params["mailto"] = _CONFIG["email"]

            try:
                data = _make_request_with_retry(
                    client, "https://api.openalex.org/works", params=params
                )
                if not data or "results" not in data:
                    logger.error(f"No results for batch {batch}")
                    openalex_ids.extend(local_results)
                    continue

                results = data.get("results", [])
                # Build a map from returned DOIs => short IDs
                result_map = {}
                for w in results:
                    if w.get("doi"):
                        # Lowercase for consistency
                        doi_key = w["doi"].lower()
                        # Convert from "https://openalex.org/Wxxxx"
                        short_id = w["id"].rsplit("/", 1)[-1]
                        result_map[doi_key] = short_id

                # For each doi in the batch, see if it is in result_map
                for idx, doi_item in enumerate(batch):
                    if doi_item is None:
                        local_results[idx] = None
                    else:
                        local_results[idx] = result_map.get(doi_item.lower(), None)

            except httpx.HTTPError as exc:
                logger.error(f"Error fetching batch {batch}: {exc}")
            except Exception as exc:
                logger.error(f"Unhandled error fetching batch {batch}: {exc}")

            openalex_ids.extend(local_results)

    return openalex_ids
