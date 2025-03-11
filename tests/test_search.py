import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
from alexify.search import (
    _SEARCH_CACHE,
    fetch_all_candidates_for_entry,
    fetch_openalex_works,
    fetch_openalex_works_by_dois,
    init_pyalex_config,
)


def test_init_pyalex_config_no_email():
    import pyalex

    # Make sure to reset or store original email if needed
    init_pyalex_config(email=None)
    # Verify that pyalex.config.email was not set
    # (It may still be something if previously set, so
    #  you might want to store the old value and check if it's unchanged.)
    # For a simple check, you might do something like:
    assert pyalex.config.email is None or pyalex.config.email == ""


@pytest.fixture
def clear_search_cache():
    """
    Clear the _SEARCH_CACHE before and after each test.
    """
    _SEARCH_CACHE.clear()
    yield
    _SEARCH_CACHE.clear()


def test_init_pyalex_config():
    """
    Check pyalex.config fields after calling init_pyalex_config.
    """
    import pyalex

    init_pyalex_config(
        email="test@example.com", max_retries=5, backoff=0.1, retry_codes=[429, 500]
    )
    assert pyalex.config.email == "test@example.com"
    assert pyalex.config.max_retries == 5
    assert pyalex.config.retry_backoff_factor == 0.1
    assert pyalex.config.retry_http_codes == [429, 500]


@patch("alexify.search.pyalex.Works")
def test_fetch_openalex_works_simple(mock_works, clear_search_cache):
    """
    Basic scenario: fetch_openalex_works with a mock returning 2 items.
    - Confirm caching => second call doesn't re-query pyalex.
    """
    mock_search = MagicMock()
    mock_search.get.return_value = [
        {"id": "https://openalex.org/W123", "title": "Sample 1"},
        {"id": "https://openalex.org/W999", "title": "Sample 2"},
    ]
    mock_works.return_value.search.return_value = mock_search

    query = "test query"
    results = fetch_openalex_works(query)
    assert len(results) == 2
    assert results[0]["id"] == "https://openalex.org/W123"

    # Caching check
    mock_works.return_value.search.reset_mock()
    results2 = fetch_openalex_works(query)
    assert len(results2) == 2
    mock_works.return_value.search.assert_not_called()


@patch("alexify.search.pyalex.Works")
def test_fetch_openalex_works_error(mock_works, clear_search_cache, caplog):
    """
    If we get an HTTPError => log error, return [].
    """
    from requests.exceptions import HTTPError

    mock_search = MagicMock()
    mock_search.get.side_effect = HTTPError("Test Error")
    mock_works.return_value.search.return_value = mock_search

    with caplog.at_level(logging.ERROR):
        res = fetch_openalex_works("failing query")
        assert res == []
        assert "Error searching OpenAlex for 'failing query': Test Error" in caplog.text


@patch("alexify.search.fetch_openalex_works")
def test_fetch_all_candidates_for_entry_no_title(mock_fetch, clear_search_cache):
    """
    If title is empty => no queries => returns []
    """
    out = fetch_all_candidates_for_entry("", "Smith", "2021")
    assert out == []
    mock_fetch.assert_not_called()


@patch("alexify.search.fetch_openalex_works")
def test_fetch_all_candidates_for_entry_variants(mock_fetch, clear_search_cache):
    """
    Multiple queries => we deduplicate by id.
    """

    def side(q):
        if q == "Neural Networks":
            return [{"id": "W1"}, {"id": "W2"}]
        elif q == "Neural Networks Smith":
            return [{"id": "W2"}, {"id": "W3"}]
        elif q == "Neural Networks 2020":
            return [{"id": "W4"}]
        elif q == "Neural Networks Smith 2020":
            return [{"id": "W5"}]
        else:
            return []

    mock_fetch.side_effect = side

    out = fetch_all_candidates_for_entry("Neural Networks", "Smith", "2020")
    # W1, W2, W3, W4, W5 => deduplicated
    ids = sorted([x["id"] for x in out])
    assert ids == ["W1", "W2", "W3", "W4", "W5"]
    # 4 queries used
    assert mock_fetch.call_count == 4


@patch("alexify.search.requests.Session", autospec=True)
def test_fetch_openalex_works_by_dois_empty(mock_session):
    """
    No DOIs => empty result => no calls
    """
    res = fetch_openalex_works_by_dois([])
    assert res == []
    mock_session.assert_not_called()


@patch("alexify.search.requests.Session", autospec=True)
def test_fetch_openalex_works_by_dois_single_batch(mock_session):
    """
    If <50 DOIs => single request. Partial results => some found, some not => None.
    """
    mock_sess = mock_session.return_value.__enter__.return_value
    # Suppose the response only has one of them
    mock_sess.get.return_value = resp = MagicMock()
    resp.json.return_value = {
        "results": [
            {"id": "https://openalex.org/W321", "doi": "https://doi.org/10.1234/foo"}
        ]
    }

    dois = ["10.1234/foo", "10.1234/bar"]
    res = fetch_openalex_works_by_dois(dois)
    # We found foo => W321, bar => None
    assert res == ["W321", None]

    # Check final URL
    mock_sess.get.assert_called_once()
    url_called = mock_sess.get.call_args[0][0]
    # Must have "doi:https://doi.org/10.1234/foo|https://doi.org/10.1234/bar"
    assert "doi:https://doi.org/10.1234/foo|https://doi.org/10.1234/bar" in url_called


@patch("alexify.search.requests.Session", autospec=True)
def test_fetch_openalex_works_by_dois_multi_batches(mock_session):
    """
    If we pass 100 DOIs => 2 calls, each with 50.
    We'll simulate partial success in each batch.
    """
    all_dois = [f"10.9999/test{i}" for i in range(100)]
    mock_sess = mock_session.return_value.__enter__.return_value

    def side(url, *args, **kwargs):
        # first batch => test0..test49
        if "test0" in url:
            # We'll only find test0 => "W0"
            data = {
                "results": [
                    {
                        "id": "https://openalex.org/W0",
                        "doi": "https://doi.org/10.9999/test0",
                    }
                ]
            }
            r = MagicMock()
            r.json.return_value = data
            return r
        else:
            # second batch => test50..test99
            # We'll only find test50 => "W50"
            data = {
                "results": [
                    {
                        "id": "https://openalex.org/W50",
                        "doi": "https://doi.org/10.9999/test50",
                    }
                ]
            }
            r = MagicMock()
            r.json.return_value = data
            return r

    mock_sess.get.side_effect = side

    results = fetch_openalex_works_by_dois(all_dois)
    assert len(results) == 100
    # Only index0 => "W0", index50 => "W50", the rest None
    assert results[0] == "W0"
    for i in range(1, 50):
        assert results[i] is None
    assert results[50] == "W50"
    for i in range(51, 100):
        assert results[i] is None

    assert mock_sess.get.call_count == 2


@patch("alexify.search.requests.Session", autospec=True)
def test_fetch_openalex_works_by_dois_partial_failure(mock_session, caplog):
    """
    We pass 53 DOIs => batch1: 50, batch2: 3.
    - 1st batch partial success => find test0 => "W0", the rest => None
    - 2nd batch => entire request fails => all None
    => final => ["W0", None, None..(49 times).., None, None, None]
    """
    all_dois = [f"10.9999/test{i}" for i in range(53)]
    mock_sess = mock_session.return_value.__enter__.return_value

    def side_effect(url, *args, **kwargs):
        if "test50" in url:
            # second batch => error
            raise requests.exceptions.RequestException("Network error test")
        else:
            # first batch => partial => only test0
            data = {
                "results": [
                    {
                        "id": "https://openalex.org/W0",
                        "doi": "https://doi.org/10.9999/test0",
                    }
                ]
            }
            r = MagicMock()
            r.json.return_value = data
            return r

    mock_sess.get.side_effect = side_effect

    with caplog.at_level(logging.ERROR):
        results = fetch_openalex_works_by_dois(all_dois)
        assert len(results) == 53
        # index0 => "W0", index1..49 => None, index50..52 => None from error
        assert results[0] == "W0"
        for i in range(1, 53):
            assert results[i] is None
        # confirm error log
        assert "Error fetching batch" in caplog.text
        assert "Network error test" in caplog.text
