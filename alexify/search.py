import logging
from typing import Any, Dict, List, Optional

import pyalex
import requests
from requests.exceptions import HTTPError, RequestException

logger = logging.getLogger(__name__)

_SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def init_pyalex_config(
    email: Optional[str] = None,
    max_retries: int = 10,
    backoff: float = 0.5,
    retry_codes: List[int] = [429, 500, 503],
):
    """
    Initialize pyalex configuration parameters for robust usage.
    If `email` is provided, sets pyalex.config.email to that address;
    otherwise does not set the email at all.
    """
    if email:
        pyalex.config.email = email
    pyalex.config.max_retries = max_retries
    pyalex.config.retry_backoff_factor = backoff
    pyalex.config.retry_http_codes = retry_codes


def fetch_openalex_works(query: str) -> List[Dict[str, Any]]:
    """
    Search OpenAlex works for the given query string, caching results.
    Returns a list of works (as dicts).
    """
    if query in _SEARCH_CACHE:
        return _SEARCH_CACHE[query]

    try:
        logger.debug(f"Searching OpenAlex for query: {query}")
        # We'll always fetch up to 50 (the official max "per-page")
        results = pyalex.Works().search(query).get(per_page=50)
        works_list = [dict(r) for r in results]
        _SEARCH_CACHE[query] = works_list
        return works_list
    except (HTTPError, RequestException) as exc:
        logger.error(f"Error searching OpenAlex for '{query}': {exc}")
        return []


def fetch_all_candidates_for_entry(
    title: str, authors_first_author_ln: str, year: str
) -> List[Dict[str, Any]]:
    """
    Perform multiple queries (title alone, title+author, title+year, etc.)
    Merge results (de-duplicate by "id").
    """
    if not title:
        return []

    queries = {title}
    if authors_first_author_ln:
        queries.add(f"{title} {authors_first_author_ln}")
    if year:
        queries.add(f"{title} {year}")
        if authors_first_author_ln:
            queries.add(f"{title} {authors_first_author_ln} {year}")

    merged = {}
    for q in queries:
        works = fetch_openalex_works(q)
        for w in works:
            wid = w.get("id")
            if wid:
                merged[wid] = w

    return list(merged.values())


def fetch_openalex_works_by_dois(dois: List[str]) -> List[str]:
    """
    Fetch OpenAlex Work short IDs for a list of DOIs in batches of up to 50.
    Return a list of same length as dois, each element either the short ID or None.
    """
    openalex_ids = []
    if not dois:
        return openalex_ids

    batch_size = 50
    processed_dois = []
    for doi in dois:
        doi_str = doi.strip().lower()
        # ensure "https://doi.org/" prefix
        if not doi_str.startswith("https://doi.org/"):
            doi_str = f"https://doi.org/{doi_str}"
        processed_dois.append(doi_str)

    with requests.Session() as sess:
        for i in range(0, len(processed_dois), batch_size):
            batch = processed_dois[i : i + batch_size]
            piped = "|".join(batch)
            url = f"https://api.openalex.org/works?filter=doi:{piped}&per-page={batch_size}"
            try:
                resp = sess.get(url)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                # Build a map from the returned DOIs => short IDs
                result_map = {
                    w["doi"].lower(): w["id"].rsplit("/", 1)[-1]
                    for w in results
                    if w.get("doi")
                }

                # For each doi in the batch, see if it's in the result_map
                for doi_item in batch:
                    match_id = result_map.get(doi_item.lower(), None)
                    openalex_ids.append(match_id)

            except RequestException as exc:
                logger.error(f"Error fetching batch {batch}: {exc}")
                # For this batch, fill Nones
                openalex_ids.extend([None] * len(batch))

    return openalex_ids
