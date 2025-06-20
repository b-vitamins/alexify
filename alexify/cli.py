import argparse
import logging

from .core import (
    find_bib_files,
    handle_fetch,
    handle_missing,
    handle_process,
    sort_bib_files_by_year,
)
from .core_concurrent import (
    init_concurrent_config,
    run_async_fetch,
    run_async_process,
)
from .search import init_openalex_config


def main():
    """
    Command-line entry point for 'alexify'.

    Subcommands:
      - process:  scans original .bib files, tries to find a matching OpenAlex ID
      - fetch:    fetches JSON metadata from OpenAlex for matched entries
      - missing:  lists which entries have not been matched

    Hardening:
      - Thorough argparse usage
      - Basic logging setup
      - Graceful handling of missing path
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
        description="Process BibTeX files with OpenAlex data (alexify).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  1) Process .bib files to add OpenAlex IDs (using your email):
     alexify --email you@example.com process /path/to/bib/files --interactive

  2) Process with massive concurrency (recommended for large datasets):
     alexify --email you@example.com process /path/to/bib/files --concurrent

  3) Fetch OpenAlex JSON for processed .bib files:
     alexify --email you@example.com fetch /path/to/bib/files -o /path/to/out

  4) Fetch with concurrent downloads:
     alexify --email you@example.com fetch /path/to/bib/files -o /path/to/out --concurrent

  5) List entries missing OpenAlex IDs:
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
            "If not set, titles above a certain threshold are auto-accepted."
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
        help="Maximum concurrent API requests when using --concurrent (default: 20).",
    )
    p_process.add_argument(
        "--max-files",
        type=int,
        default=4,
        help="Maximum files to process concurrently when using --concurrent (default: 4).",
    )
    p_process.add_argument(
        "--max-entries",
        type=int,
        default=20,
        help="Maximum entries to process concurrently per file when using --concurrent (default: 20).",
    )
    p_process.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for processing entries when using --concurrent (default: 50).",
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
        help="Maximum concurrent API requests when using --concurrent (default: 20).",
    )

    # Subcommand: missing
    p_missing = sub.add_parser(
        "missing", help="List entries missing OpenAlex IDs in '-oa.bib'."
    )
    p_missing.add_argument(
        "path", help="File or directory of processed .bib (files ending in '-oa.bib')."
    )

    args = parser.parse_args()

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
                user_interaction=False,
                force=args.force,
                strict=args.strict,
                email=args.email,
                max_concurrent_requests=args.max_requests,
            )
        else:
            # Initialize OpenAlex config for sequential processing
            init_openalex_config(email=args.email)
            for bf in sorted_files:
                handle_process(bf, args.interactive, args.force, args.strict)

    elif args.command == "fetch":
        files = find_bib_files(args.path, mode="processed")
        sorted_files = sort_bib_files_by_year(files)

        if args.concurrent:
            # Initialize concurrent configuration
            init_concurrent_config(
                max_file_workers=args.max_files if hasattr(args, "max_files") else 4
            )

            # Run with massive concurrency
            run_async_fetch(
                sorted_files,
                args.output_dir,
                args.force,
                email=args.email,
                max_concurrent_requests=args.max_requests,
            )
        else:
            # Initialize OpenAlex config for sequential processing
            init_openalex_config(email=args.email)
            for bf in sorted_files:
                handle_fetch(bf, args.output_dir, args.force)

    elif args.command == "missing":
        # Initialize OpenAlex config
        init_openalex_config(email=args.email)
        files = find_bib_files(args.path, mode="processed")
        sorted_files = sort_bib_files_by_year(files)
        for bf in sorted_files:
            handle_missing(bf)


if __name__ == "__main__":
    main()
