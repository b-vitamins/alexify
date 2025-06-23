"""Enhanced CLI with massive concurrency support."""

import argparse
import logging
import os
import re
import sys

from .core import find_bib_files, handle_missing, sort_bib_files_by_year
from .core_concurrent import (
    init_concurrent_config,
    run_async_fetch,
    run_async_process,
)
from .search import init_openalex_config


def validate_email(email: str) -> bool:
    """
    Validate email format using a basic regex pattern.
    Returns True if email is valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False

    # Basic email validation pattern
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_pattern, email.strip()) is not None


def validate_numeric_bounds(
    value: int, param_name: str, min_val: int, max_val: int
) -> None:
    """
    Validate that a numeric parameter is within acceptable bounds.
    Exits with error message if validation fails.
    """
    if not isinstance(value, int) or value < min_val or value > max_val:
        logging.error(
            f"Invalid {param_name}: {value}. Must be between {min_val} and {max_val}."
        )
        sys.exit(1)


def validate_path_access(
    path: str, require_readable: bool = True, require_writable: bool = False
) -> None:
    """
    Validate that a path exists and has required permissions.
    Exits with error message if validation fails.
    """
    if not path or not isinstance(path, str):
        logging.error("Path must be a non-empty string.")
        sys.exit(1)

    if not os.path.exists(path):
        logging.error(f"Path does not exist: {path}")
        sys.exit(1)

    if require_readable and not os.access(path, os.R_OK):
        logging.error(f"Path is not readable: {path}")
        sys.exit(1)

    if require_writable and not os.access(path, os.W_OK):
        logging.error(f"Path is not writable: {path}")
        sys.exit(1)


def main():
    """
    Enhanced command-line entry point for 'alexify' with concurrency support.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Silence verbose HTTPX logs from showing request/response details
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Process BibTeX files with OpenAlex data (alexify) - Enhanced Concurrent Version",
        epilog="""
Examples:

  1) Process .bib files with massive concurrency:
     alexify --email you@example.com process /path/to/bib/files --concurrent

  2) Process with custom concurrency settings:
     alexify --email you@example.com process /path/to/bib/files --concurrent \
       --max-requests 50 --max-files 8 --max-entries 30

  3) Fetch OpenAlex JSON with concurrent downloads:
     alexify --email you@example.com fetch /path/to/bib/files -o /path/to/out --concurrent

  4) List entries missing OpenAlex IDs:
     alexify missing /path/to/bib/files
""",
    )
    parser.add_argument(
        "--email",
        default=None,
        help=(
            "Optional email for OpenAlex API requests. "
            "Enables access to the polite pool for better rate limits. "
            "If omitted, requests use the common pool."
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # Subcommand: process
    p_process = sub.add_parser("process", help="Process .bib to add OpenAlex IDs.")
    p_process.add_argument(
        "path", help="File or directory containing original .bib files."
    )
    p_process.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help=(
            "Ask user about uncertain matches interactively. "
            "Note: Interactive mode is disabled when using --concurrent."
        ),
    )
    p_process.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing '-oa.bib' file if present (otherwise skip).",
    )
    p_process.add_argument(
        "--strict",
        action="store_true",
        help="Use stricter thresholds to minimize false positives when matching titles/authors.",
    )
    p_process.add_argument(
        "--concurrent",
        action="store_true",
        help="Enable massive concurrency for processing (recommended for large datasets).",
    )
    p_process.add_argument(
        "--max-requests",
        type=int,
        default=20,
        help="Maximum concurrent API requests (default: 20).",
    )
    p_process.add_argument(
        "--max-files",
        type=int,
        default=4,
        help="Maximum files to process concurrently (default: 4).",
    )
    p_process.add_argument(
        "--max-entries",
        type=int,
        default=20,
        help="Maximum entries to process concurrently per file (default: 20).",
    )
    p_process.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for processing entries (default: 50).",
    )

    # Subcommand: fetch
    p_fetch = sub.add_parser(
        "fetch", help="Fetch JSON data for OpenAlex IDs in processed .bib."
    )
    p_fetch.add_argument(
        "path",
        help="File or directory of .bib files that already have OpenAlex IDs (i.e. '-oa.bib').",
    )
    p_fetch.add_argument(
        "--output-dir",
        "-o",
        required=True,
        help="Directory where JSON results will be stored in subfolders by year.",
    )
    p_fetch.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing .json files if present in the output directory.",
    )
    p_fetch.add_argument(
        "--concurrent",
        action="store_true",
        help="Enable massive concurrency for fetching (recommended for large datasets).",
    )
    p_fetch.add_argument(
        "--max-requests",
        type=int,
        default=20,
        help="Maximum concurrent API requests (default: 20).",
    )
    p_fetch.add_argument(
        "--max-files",
        type=int,
        default=4,
        help="Maximum files to process concurrently (default: 4).",
    )

    # Subcommand: missing
    p_missing = sub.add_parser(
        "missing", help="List entries missing OpenAlex IDs in '-oa.bib'."
    )
    p_missing.add_argument(
        "path", help="File or directory of processed .bib (files ending in '-oa.bib')."
    )

    args = parser.parse_args()

    # Validate email format if provided
    if args.email and not validate_email(args.email):
        logging.error(
            f"Invalid email format: '{args.email}'. Please provide a valid email address."
        )
        sys.exit(1)

    # Validate paths based on command
    if args.command in ["process", "fetch", "missing"]:
        validate_path_access(args.path, require_readable=True)

    if args.command == "fetch":
        # For fetch command, validate output directory
        if not os.path.exists(args.output_dir):
            # Try to create the output directory if it doesn't exist
            try:
                os.makedirs(args.output_dir, exist_ok=True)
                logging.info(f"Created output directory: {args.output_dir}")
            except (OSError, PermissionError) as e:
                logging.error(
                    f"Cannot create output directory '{args.output_dir}': {e}"
                )
                sys.exit(1)
        else:
            validate_path_access(
                args.output_dir, require_readable=True, require_writable=True
            )

    # Validate concurrent processing parameters
    if hasattr(args, "max_requests"):
        validate_numeric_bounds(args.max_requests, "max-requests", 1, 100)
    if hasattr(args, "max_files"):
        validate_numeric_bounds(args.max_files, "max-files", 1, 20)
    if hasattr(args, "max_entries"):
        validate_numeric_bounds(args.max_entries, "max-entries", 1, 100)
    if hasattr(args, "batch_size"):
        validate_numeric_bounds(args.batch_size, "batch-size", 1, 1000)

    if args.command == "process":
        files = find_bib_files(args.path, mode="original")
        sorted_files = sort_bib_files_by_year(files)

        if args.concurrent:
            # Initialize concurrent configuration
            init_concurrent_config(
                max_file_workers=args.max_files,
                max_entry_workers=args.max_entries,
                batch_size=args.batch_size,
            )

            # Note: Interactive mode is not supported in concurrent mode
            if args.interactive:
                logging.warning(
                    "Interactive mode is not supported with --concurrent. Proceeding without interaction."
                )

            # Run with massive concurrency
            run_async_process(
                sorted_files,
                user_interaction=False,  # Disable interaction in concurrent mode
                force=args.force,
                strict=args.strict,
                email=args.email,
                max_concurrent_requests=args.max_requests,
            )
        else:
            # Use original sequential processing
            init_openalex_config(email=args.email)
            from .core import handle_process

            for bf in sorted_files:
                handle_process(bf, args.interactive, args.force, args.strict)

    elif args.command == "fetch":
        files = find_bib_files(args.path, mode="processed")
        sorted_files = sort_bib_files_by_year(files)

        if hasattr(args, "concurrent") and args.concurrent:
            # Initialize concurrent configuration
            init_concurrent_config(max_file_workers=args.max_files)

            # Run with massive concurrency
            run_async_fetch(
                sorted_files,
                args.output_dir,
                args.force,
                email=args.email,
                max_concurrent_requests=args.max_requests,
            )
        else:
            # Use original sequential processing
            init_openalex_config(email=args.email)
            from .core import handle_fetch

            for bf in sorted_files:
                handle_fetch(bf, args.output_dir, args.force)

    elif args.command == "missing":
        files = find_bib_files(args.path, mode="processed")
        sorted_files = sort_bib_files_by_year(files)
        for bf in sorted_files:
            handle_missing(bf)


if __name__ == "__main__":
    main()
