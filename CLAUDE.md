# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**alexify** is a Python CLI tool and library that enriches BibTeX files with metadata from the OpenAlex academic database. It uses fuzzy matching algorithms to match BibTeX entries by title/DOI and fetches corresponding OpenAlex IDs and metadata.

## Common Development Commands

### Setup and Dependencies
```bash
# Install dependencies using Poetry
poetry install

# Install development dependencies
poetry install --with dev
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=alexify --cov-report=term-missing

# Run a specific test file
poetry run pytest tests/test_core.py

# Run a specific test
poetry run pytest tests/test_core.py::test_function_name
```

### Code Quality
```bash
# Type checking
poetry run mypy alexify
poetry run pyright

# Linting
poetry run ruff check .

# Code formatting
poetry run black .
```

### Building and Running
```bash
# Run the CLI directly through Poetry
poetry run alexify --help

# Build distribution packages
poetry build

# Install locally for development
poetry install
```

## Architecture Overview

### Core Components

1. **CLI Interface (`alexify/cli.py`)**
   - Entry point for the command-line tool
   - Three main subcommands: `process`, `fetch`, and `missing`
   - Email configuration support for OpenAlex polite pool access
   - Support for `--concurrent` flag to enable massive parallelization

2. **Core Processing (`alexify/core.py`)**
   - BibTeX file handling and parsing
   - Year extraction from filenames
   - Batch processing with concurrent execution
   - File discovery and output management

3. **Concurrent Processing (`alexify/core_concurrent.py`)**
   - Async/await implementation for massive parallelization
   - Multi-level concurrency: files, entries, and API requests
   - ProcessPoolExecutor for CPU-intensive operations
   - Configurable concurrency limits and batch sizes

4. **OpenAlex Search (`alexify/search.py`)**
   - API client with exponential backoff retry logic
   - Request caching to minimize API calls
   - Handles both title-based and DOI-based searches
   - Configurable retry attempts and timeouts

5. **Async Search (`alexify/search_async.py`)**
   - Async version of all search functions
   - Semaphore-based rate limiting for concurrent requests
   - Efficient connection pooling with httpx.AsyncClient
   - Support for fetching multiple works concurrently

6. **Fuzzy Matching (`alexify/matching.py`)**
   - Text normalization (accents, punctuation, stopwords)
   - Hybrid scoring using multiple fuzzy matching algorithms
   - Configurable thresholds for strict/normal matching
   - Author list comparison for verification

### Key Design Patterns

- **Concurrent Processing**: Uses ThreadPoolExecutor for parallel API requests
- **Caching**: In-memory cache for API responses to avoid duplicate requests
- **Error Handling**: Comprehensive exception handling with informative error messages
- **Configuration**: Flexible configuration through CLI arguments and function parameters

## Important Notes from AGENTS.md

- Always update CHANGELOG.md before any commit

## Testing Approach

Tests use:
- `pytest` for test framework
- `respx` for mocking HTTP requests to OpenAlex API
- `time-machine` for time-dependent tests
- Type annotations throughout for static analysis

## Development Workflow

1. Make changes to the codebase
2. Run tests to ensure nothing breaks: `poetry run pytest`
3. Run type checking: `poetry run mypy alexify`
4. Run linting: `poetry run ruff check .`
5. Format code: `poetry run black .`
6. Update CHANGELOG.md with changes
7. Commit with conventional commit messages