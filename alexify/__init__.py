# alexify/__init__.py

__version__ = "0.4.0"

# Import key functions for ease of use
from .cli import main as cli_main
from .core import find_bib_files, handle_fetch, handle_missing, handle_process
from .matching import fuzzy_match_authors, fuzzy_match_titles, normalize_text
from .search import (
    fetch_openalex_works,
    fetch_openalex_works_by_dois,
    init_openalex_config,
)

# Define what gets imported when using `from alexify import *`
__all__ = [
    "__version__",
    "find_bib_files",
    "handle_process",
    "handle_fetch",
    "handle_missing",
    "fuzzy_match_titles",
    "fuzzy_match_authors",
    "normalize_text",
    "fetch_openalex_works",
    "fetch_openalex_works_by_dois",
    "init_openalex_config",
    "cli_main",
]
