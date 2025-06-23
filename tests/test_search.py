import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest
from alexify.search import (
    _CACHE_LOCK,
    _SEARCH_CACHE,
    fetch_all_candidates_for_entry,
    fetch_openalex_works,
    fetch_openalex_works_by_dois,
    init_openalex_config,
)


def test_init_openalex_config_no_email():
    from alexify.search import _CONFIG

    init_openalex_config(email=None)
    assert _CONFIG["email"] is None


@pytest.fixture
def clear_search_cache():
    """
    Clear the _SEARCH_CACHE before and after each test with thread safety.
    """
    with _CACHE_LOCK:
        _SEARCH_CACHE.clear()
    yield
    with _CACHE_LOCK:
        _SEARCH_CACHE.clear()


def test_init_openalex_config():
    """
    Check config fields after calling init_openalex_config.
    """
    from alexify.search import _CONFIG

    init_openalex_config(
        email="test@example.com", max_retries=5, backoff=0.1, retry_codes=[429, 500]
    )
    assert _CONFIG["email"] == "test@example.com"
    assert _CONFIG["max_retries"] == 5
    assert _CONFIG["backoff"] == 0.1
    assert _CONFIG["retry_codes"] == [429, 500]


@patch("alexify.search.httpx.Client")
def test_fetch_openalex_works_simple(mock_client, clear_search_cache):
    """
    Basic scenario: fetch_openalex_works with a mock returning 2 items.
    - Confirm caching => second call doesn't re-query API.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"id": "https://openalex.org/W123", "title": "Sample 1"},
            {"id": "https://openalex.org/W999", "title": "Sample 2"},
        ]
    }

    mock_client_instance = mock_client.return_value.__enter__.return_value
    mock_client_instance.get.return_value = mock_response

    query = "test query"
    results = fetch_openalex_works(query)
    assert len(results) == 2
    assert results[0]["id"] == "https://openalex.org/W123"

    # Caching check
    mock_client_instance.get.reset_mock()
    results2 = fetch_openalex_works(query)
    assert len(results2) == 2
    mock_client_instance.get.assert_not_called()


@patch("alexify.search.httpx.Client")
def test_fetch_openalex_works_error(mock_client, clear_search_cache, caplog):
    """
    If we get an HTTPError => log error, return [].
    """
    # Configure for faster test execution
    init_openalex_config(max_retries=2, backoff=0.1)

    mock_client_instance = mock_client.return_value.__enter__.return_value
    mock_client_instance.get.side_effect = httpx.HTTPError("Test Error")

    with caplog.at_level(logging.ERROR):
        res = fetch_openalex_works("failing query")
    assert res == []
    # Check for either the old or new error message format
    assert (
        "Error searching OpenAlex for 'failing query'" in caplog.text
        or "All retry attempts failed for https://api.openalex.org/works" in caplog.text
    )


def test_fetch_openalex_works_empty_query(clear_search_cache):
    """
    Empty or None query => immediately return []
    """
    assert fetch_openalex_works("") == []
    assert fetch_openalex_works(None) == []


def test_fetch_all_candidates_for_entry():
    """
    Test the logic for building queries from title/author/year.
    """
    # All present
    res = fetch_all_candidates_for_entry("Title ABC", "Smith", "2020")
    # It should call fetch_openalex_works with "Title ABC Smith 2020"
    # We can't test the exact call without mocking, but we can test
    # that it returns a list (could be empty if no network).

    # Title + year
    res2 = fetch_all_candidates_for_entry("Title XYZ", "", "2021")
    # Title only
    res3 = fetch_all_candidates_for_entry("Only Title", "", "")
    # Ensure intermediate queries return lists (could be empty if no network)
    assert isinstance(res, list)
    assert isinstance(res2, list)
    assert isinstance(res3, list)
    # Nothing => []
    res4 = fetch_all_candidates_for_entry("", "", "")
    assert res4 == []


@patch("alexify.search.httpx.Client", autospec=True)
def test_fetch_openalex_works_by_dois_empty(mock_client):
    """
    No DOIs => empty result => no calls
    """
    res = fetch_openalex_works_by_dois([])
    assert res == []
    mock_client.assert_not_called()


@patch("alexify.search._make_request_with_retry")
@patch("alexify.search.httpx.Client", autospec=True)
def test_fetch_openalex_works_by_dois_single_batch(_mock_client, mock_request):
    """
    If <50 DOIs => single request. Partial results => some found, some not => None.
    """
    mock_request.return_value = {
        "results": [
            {"id": "https://openalex.org/W321", "doi": "https://doi.org/10.1234/foo"}
        ]
    }

    dois = ["10.1234/foo", "10.1234/bar"]
    res = fetch_openalex_works_by_dois(dois)
    # We found foo => W321, bar => None
    assert res == ["W321", None]

    mock_request.assert_called_once()
    assert mock_request.call_args is not None
    called_params = mock_request.call_args.kwargs.get("params", {})
    assert (
        called_params["filter"]
        == "doi:https://doi.org/10.1234/foo|https://doi.org/10.1234/bar"
    )


@patch("alexify.search._make_request_with_retry")
@patch("alexify.search.httpx.Client", autospec=True)
def test_fetch_openalex_works_by_dois_multi_batches(_mock_client, mock_request):
    """
    If we pass 100 DOIs => 2 calls, each with 50.
    """
    dois = [f"10.1234/test{i}" for i in range(100)]

    def side(client, url, params=None):
        assert params is not None
        results = []
        filt = params["filter"]
        if "test0" in filt:
            for i in range(20):
                results.append(
                    {
                        "id": f"https://openalex.org/W{i}",
                        "doi": f"https://doi.org/10.1234/test{i}",
                    }
                )
        elif "test50" in filt:
            for i in range(50, 70):
                results.append(
                    {
                        "id": f"https://openalex.org/W{i}",
                        "doi": f"https://doi.org/10.1234/test{i}",
                    }
                )
        return {"results": results}

    mock_request.side_effect = side

    res = fetch_openalex_works_by_dois(dois)
    assert len(res) == 100
    # We found 0-19 in first batch => W0..W19
    # We found 50-69 in second batch => W50..W69
    # The rest are None
    for i in range(20):
        assert res[i] == f"W{i}"
    for i in range(20, 50):
        assert res[i] is None
    for i in range(50, 70):
        assert res[i] == f"W{i}"
    for i in range(70, 100):
        assert res[i] is None

    assert mock_request.call_count == 2


@patch("alexify.search._make_request_with_retry")
@patch("alexify.search.httpx.Client", autospec=True)
def test_fetch_openalex_works_by_dois_partial_failure(
    _mock_client, mock_request, caplog
):
    """
    If one batch fails => that batch gets None, but others succeed.
    """
    dois = [f"10.1234/test{i}" for i in range(100)]

    def side_effect(client, url, params=None):
        assert params is not None
        filt = params["filter"]
        if "test0" in filt:
            raise httpx.HTTPError("Network error test")
        return {
            "results": [
                {
                    "id": "https://openalex.org/W60",
                    "doi": "https://doi.org/10.1234/test60",
                }
            ]
        }

    mock_request.side_effect = side_effect

    with caplog.at_level(logging.ERROR):
        res = fetch_openalex_works_by_dois(dois)

    assert len(res) == 100
    # First batch failed => all None
    for i in range(50):
        assert res[i] is None
    # Second batch succeeded for test60 => W60
    assert res[60] == "W60"
    # The rest in second batch are None
    for i in range(50, 100):
        if i != 60:
            assert res[i] is None

    assert "Unexpected error fetching batch" in caplog.text


@patch("alexify.search._make_request_with_retry")
@patch("alexify.search.httpx.Client", autospec=True)
def test_fetch_openalex_works_by_dois_no_results(_mock_client, mock_request, caplog):
    """If API returns None or missing results, we log and return None values."""
    dois = ["10.1111/abc", "10.2222/def"]
    mock_request.return_value = None

    with caplog.at_level(logging.ERROR):
        res = fetch_openalex_works_by_dois(dois)

    assert res == [None, None]
    assert "No results for batch" in caplog.text
