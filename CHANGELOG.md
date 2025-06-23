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

### Input Validation & Security
- **CLI Argument Validation**: Comprehensive validation of command-line inputs
  - Add email format validation using regex patterns for `--email` arguments
  - Add numeric bounds checking for concurrency parameters (max-requests, max-files, max-entries, batch-size)
  - Add path existence and permission validation for input/output directories
  - Automatic output directory creation with proper error handling
- **API Response Validation**: Add structure validation for OpenAlex API responses
  - Validate response format and required fields (`results`, `id`, `title`)
  - Detect malformed API responses and handle gracefully with informative logging
  - Replace basic structure checks with comprehensive validation functions
- **Runtime Type Checking**: Add type validation to critical functions
  - Parameter type validation in fuzzy matching functions with fallback defaults
  - Bounds checking for weight parameters and thresholds with automatic clamping
  - Input type validation for author lists and other critical data structures

### Performance Optimization
- **LRU Caching**: Add memory-efficient caching to expensive text processing operations
  - Cache text normalization, name normalization, and name component splitting functions
  - Configurable cache sizes (256-512 entries) to balance memory usage and performance
  - Significant speedup for repeated author/title processing operations
- **Bounded Cache Implementation**: Replace unbounded global caches with LRU-based bounded caches
  - Thread-safe `BoundedCache` class with configurable maximum size (1000 entries)
  - Async-safe `AsyncBoundedCache` for concurrent operations
  - Automatic eviction of least recently used entries to prevent memory leaks
- **Algorithm Optimization**: Improve O(n²) fuzzy matching performance
  - Early termination in author matching when threshold is met
  - Reduced computational overhead for large author lists
  - Maintain same matching accuracy with improved speed

### Code Organization & Duplication Elimination
- **Unified CLI Interface**: Consolidate `cli.py` and `cli_concurrent.py` into single interface
  - Remove duplicate CLI file and merge functionality into main CLI
  - Add missing `--max-files` argument to fetch command for consistency
  - Maintain backward compatibility for all existing commands and options
- **HTTP Client Base Classes**: Extract common HTTP request handling into reusable components
  - Create `BaseHTTPClient` abstract class with shared retry logic and configuration
  - Implement `SyncHTTPClient` and `AsyncHTTPClient` subclasses for sync/async operations
  - Eliminate code duplication between `search.py` and `search_async.py` modules
- **Unified Configuration Management**: Centralize configuration handling across modules
  - Thread-safe `ConfigManager` class with centralized configuration storage
  - Unified configuration interface with `get_config()`, `init_config()`, and `set_config_value()` functions
  - Replace scattered global configuration variables with single source of truth
- **OpenAlex Query Builder**: Extract query building logic into reusable utility
  - `OpenAlexQueryBuilder` class with static methods for building search queries
  - Support for search parameters, DOI filters, and work detail parameters
  - Consistent query building patterns across sync and async modules
- **Error Handling Decorators**: Create reusable decorators for common error patterns
  - `@handle_http_errors` and `@handle_async_http_errors` for HTTP request error handling
  - `@handle_file_errors` for file operation error handling
  - `@validate_input` for consistent input validation across functions
  - `@log_performance` and `@log_async_performance` for execution time logging

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
