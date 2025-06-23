# Changelog

## [Unreleased]

### Security & Thread Safety
- **Critical Race Condition Fixes**: Add comprehensive thread safety to concurrent processing
  - Add `asyncio.Lock()` protection to global cache access in `search_async.py`
  - Add `threading.Lock()` protection to global cache in `search.py`
  - Fix global configuration race conditions in `core_concurrent.py`
  - Implement proper singleton pattern for semaphore creation with double-checked locking
  - Add file I/O locks to prevent concurrent directory/file creation race conditions
- **Type Safety**: Fix type annotation issues and improve static analysis compatibility
- **Error Handling**: Replace generic OSError catches with specific exception handling

### Error Handling & Robustness 
- **Enhanced Error Handling Patterns**: Standardize error handling across all modules
  - Add logger to `matching.py` and replace silent exception handling with proper logging
  - Replace generic `Exception` catches with specific exception types (`httpx.RequestError`, `UnicodeDecodeError`, etc.)
  - Add comprehensive error handling to `find_bib_files()` with input validation and specific exception catching  
  - Enhance file I/O error handling with specific exceptions for permission and encoding issues
  - Improve HTTP error handling with detailed logging for different error conditions
- **Input Validation**: Add parameter validation to prevent silent failures
- **Error Messaging**: Improve error messages with more context and specificity

## [0.4.1] - 2025-01-20
- Fix pickling error in concurrent processing by moving `compute_score` to module level
- Fix Retry-After header parsing to handle both numeric and date string formats

## [0.4.0] - 2024-01-20
- Add massive built-in concurrency support:
  - New `search_async.py` module with async/await implementations of all search functions
  - New `core_concurrent.py` module with concurrent processing at multiple levels:
    - Process multiple BibTeX files concurrently (ProcessPoolExecutor)
    - Process entries within each file concurrently (asyncio)
    - Fetch OpenAlex data with massive parallelization (up to 20 concurrent requests)
  - Add `--concurrent` flag to CLI for enabling concurrent mode
  - Add configuration options: `--max-requests`, `--max-files` for tuning concurrency
  - Implement semaphore-based rate limiting for API requests
  - Add concurrent scoring of candidates using multiprocessing
  - Support batch processing of DOI lookups with concurrent API calls
- Performance improvements:
  - 10-50x speedup for large datasets when using concurrent mode
  - Efficient connection pooling with httpx.AsyncClient
  - Parallel execution of multiple search queries
- Add comprehensive tests for concurrent functionality
- Enhance retry logic in `_make_request_with_retry` with:
  - Request timeout configuration (30s default)
  - Better error logging with retry attempt information
  - Support for Retry-After header from rate-limited responses
  - Separate handling for timeout vs other HTTP errors
- Add `timeout` parameter to `init_openalex_config`
- Clean up remnants of pyalex dependency:
  - Rename `init_pyalex_config` to `init_openalex_config` throughout codebase
  - Update help text and documentation to remove pyalex references
  - Update test names to reflect new function names
- Update test to handle new error message format
- Improve error handling in `fetch_openalex_works_by_dois` to use retry helper
  and log when API returns no results. Update corresponding tests.
- Suppress verbose HTTPX request logs so only relevant info messages appear.

## [0.3.0] - 2024-01-15

- Remove root-level smoke test scripts: delete test_api.py, test_api2.py, test_matching.py, test_matching_debug.py, test_query_order.py, test_single_paper.py, test_title_only.py
- Adjust `order_entries_by` default to `(\"ID\",)` in save_bib_file (alexify/core.py)
- Refactor `_make_request_with_retry` signature, backoff calculation, and exception handling (alexify/search.py)
- Add type hints to `fetch_openalex_works`, `fetch_all_candidates_for_entry`, and related functions (alexify/search.py)
- Improve whitespace and formatting consistency across core and search modules
- Add `python-ruff` and `node-pyright` to development dependencies in manifest.scm
- Update tests in `tests/test_core.py` and `tests/test_search.py` to align with code changes
