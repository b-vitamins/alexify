"""Tests for concurrent processing functionality."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alexify.core_concurrent import (
    handle_process_concurrent,
    process_bib_entries_by_dois_concurrent,
    score_candidates_concurrent,
)
from alexify.search_async import (
    fetch_all_candidates_for_entry_async,
    fetch_openalex_works_async,
    fetch_openalex_works_by_dois_async,
)


@pytest.mark.asyncio
async def test_fetch_openalex_works_async():
    """Test async search functionality."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "https://openalex.org/W1234", "title": "Test Paper"}]
    }
    mock_client.get.return_value = mock_response

    results = await fetch_openalex_works_async("test query", mock_client)

    assert len(results) == 1
    assert results[0]["id"] == "https://openalex.org/W1234"
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_openalex_works_by_dois_async():
    """Test async DOI batch fetching."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"id": "https://openalex.org/W1234", "doi": "https://doi.org/10.1234/test"}
        ]
    }
    mock_client.get.return_value = mock_response

    dois = ["10.1234/test", "10.5678/missing"]
    results = await fetch_openalex_works_by_dois_async(dois, mock_client)

    assert len(results) == 2
    assert results[0] == "W1234"
    assert results[1] is None


@pytest.mark.asyncio
async def test_process_bib_entries_by_dois_concurrent():
    """Test concurrent DOI processing for BibTeX entries."""
    entries = [
        {"ID": "entry1", "doi": "10.1234/test"},
        {"ID": "entry2", "doi": "10.5678/test2"},
        {"ID": "entry3", "title": "No DOI"},
    ]

    mock_client = AsyncMock()

    with patch(
        "alexify.core_concurrent.fetch_openalex_works_by_dois_async"
    ) as mock_fetch:
        mock_fetch.return_value = ["W1234", "W5678"]

        updated_entries, changed = await process_bib_entries_by_dois_concurrent(
            entries, mock_client
        )

        assert changed == 2
        assert updated_entries[0]["openalex"] == "W1234"
        assert updated_entries[1]["openalex"] == "W5678"
        assert "openalex" not in updated_entries[2]


def test_score_candidates_concurrent():
    """Test concurrent scoring of candidates."""
    entry = {
        "ID": "test",
        "title": "Deep Learning for Computer Vision",
        "author": "Smith, John and Doe, Jane",
        "year": "2023",
    }

    candidates = [
        {
            "id": "https://openalex.org/W1",
            "title": "Deep Learning for Computer Vision",
            "authorships": [{"author": {"display_name": "John Smith"}}],
            "publication_year": 2023,
        },
        {
            "id": "https://openalex.org/W2",
            "title": "Machine Learning Basics",
            "authorships": [{"author": {"display_name": "Bob Jones"}}],
            "publication_year": 2022,
        },
    ]

    # Mock the ProcessPoolExecutor to run synchronously in tests
    with patch("concurrent.futures.ProcessPoolExecutor") as mock_executor:
        mock_executor.return_value.__enter__.return_value.map = lambda f, items: [
            f(item) for item in items
        ]

        scored = score_candidates_concurrent(entry, candidates)

        assert len(scored) == 2
        assert scored[0][0] > scored[1][0]  # First candidate should score higher
        assert scored[0][1]["id"] == "https://openalex.org/W1"


@pytest.mark.asyncio
async def test_fetch_all_candidates_concurrent():
    """Test concurrent fetching of all candidates."""
    mock_client = AsyncMock()

    # Mock responses for different queries
    async def mock_fetch(query, client):
        if "Deep Learning Smith 2023" in query:
            return [{"id": "W1", "title": "Deep Learning"}]
        elif "Deep Learning Smith" in query:
            return [{"id": "W2", "title": "Deep Learning Overview"}]
        elif "Deep Learning" in query:
            return [{"id": "W3", "title": "Deep Learning Basics"}]
        return []

    with patch(
        "alexify.search_async.fetch_openalex_works_async", side_effect=mock_fetch
    ):
        results = await fetch_all_candidates_for_entry_async(
            "Deep Learning", "Smith", "2023", mock_client
        )

        # Should get unique results from all queries
        assert len(results) == 3
        ids = [r["id"] for r in results]
        assert "W1" in ids
        assert "W2" in ids
        assert "W3" in ids


@pytest.mark.asyncio
async def test_handle_process_concurrent_integration():
    """Integration test for concurrent processing."""
    # Create a temporary BibTeX file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
        f.write(
            """
@article{test2023,
    title = {Test Article},
    author = {Smith, John},
    year = {2023},
    doi = {10.1234/test}
}
"""
        )
        temp_file = f.name

    try:
        # Mock the async client and API responses
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock DOI lookup response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [
                    {
                        "id": "https://openalex.org/W1234",
                        "doi": "https://doi.org/10.1234/test",
                    }
                ]
            }
            mock_client.get.return_value = mock_response

            # Run concurrent processing
            await handle_process_concurrent(temp_file, force=True)

            # Check that output file was created
            output_file = temp_file.replace(".bib", "-oa.bib")
            assert Path(output_file).exists()

            # Clean up
            Path(output_file).unlink()
    finally:
        Path(temp_file).unlink()


@pytest.mark.asyncio
async def test_multiple_works_fetch():
    """Test fetching multiple works concurrently."""
    mock_client = AsyncMock()

    # Mock individual work fetches
    async def mock_get(url, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200

        if "W1234" in url:
            mock_response.json.return_value = {"id": "W1234", "title": "Paper 1"}
        elif "W5678" in url:
            mock_response.json.return_value = {"id": "W5678", "title": "Paper 2"}
        else:
            mock_response.status_code = 404
            mock_response.json.return_value = None

        return mock_response

    mock_client.get.side_effect = mock_get

    from alexify.search_async import fetch_multiple_works_async

    results = await fetch_multiple_works_async(["W1234", "W5678", "W9999"], mock_client)

    assert len(results) == 3
    assert results[0] is not None and results[0]["title"] == "Paper 1"
    assert results[1] is not None and results[1]["title"] == "Paper 2"
    assert results[2] is None
