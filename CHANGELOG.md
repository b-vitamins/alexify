# Changelog

## [Unreleased]
- Improve error handling in `fetch_openalex_works_by_dois` to use retry helper
  and log when API returns no results. Update corresponding tests.

## [0.3.0]

- Remove root-level smoke test scripts: delete test_api.py, test_api2.py, test_matching.py, test_matching_debug.py, test_query_order.py, test_single_paper.py, test_title_only.py
- Adjust `order_entries_by` default to `(\"ID\",)` in save_bib_file (alexify/core.py)
- Refactor `_make_request_with_retry` signature, backoff calculation, and exception handling (alexify/search.py)
- Add type hints to `fetch_openalex_works`, `fetch_all_candidates_for_entry`, and related functions (alexify/search.py)
- Improve whitespace and formatting consistency across core and search modules
- Add `python-ruff` and `node-pyright` to development dependencies in manifest.scm
- Update tests in `tests/test_core.py` and `tests/test_search.py` to align with code changes