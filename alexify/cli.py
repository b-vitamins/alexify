import argparse
import logging

from .core import (
    find_bib_files,
    handle_fetch,
    handle_missing,
    handle_process,
    sort_bib_files_by_year,
)
from .search import init_pyalex_config


def main():
    """
    Command-line entry point for 'alexify'.

    This CLI provides three primary subcommands:

        1) process  => scans original .bib files, attempts to find a matching
                       OpenAlex ID by either DOI or fuzzy matching on title and authors.
                       Outputs a new '-oa.bib' file containing these OpenAlex IDs.

        2) fetch    => using a previously processed '-oa.bib' file with OpenAlex IDs,
                       fetch JSON metadata from OpenAlex for each matched entry,
                       storing JSON in the specified output directory (organized by year).

        3) missing  => reports which entries are missing an OpenAlex ID in a '-oa.bib' file.

    Global Argument:
        --email: Sets the email used by the Pyalex library. If unspecified, Pyalex
                 will make requests without attaching any email contact. This is
                 generally discouraged, so please provide an email when possible.

    Example Usage:

        # 1) Process .bib files to add OpenAlex IDs (specify your email):
        poetry run alexify --email you@example.com process /path/to/bib/files --interactive

        # 2) Fetch OpenAlex JSON records for the newly-created '-oa.bib' files:
        poetry run alexify --email you@example.com fetch /path/to/bib/files -o /path/to/out

        # 3) Show which entries lack any OpenAlex ID:
        poetry run alexify missing /path/to/bib/files

    Returns:
        None

    Raises:
        SystemExit: If argparse encounters invalid options or missing parameters.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Process BibTeX files with OpenAlex data (alexify).",
        epilog="""
Examples:

  1) Process .bib files to add OpenAlex IDs (using your email):
     poetry run alexify --email you@example.com process /path/to/bib/files --interactive

  2) Fetch OpenAlex JSON for processed .bib files:
     poetry run alexify --email you@example.com fetch /path/to/bib/files -o /path/to/out

  3) List entries missing OpenAlex IDs:
     poetry run alexify missing /path/to/bib/files
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--email",
        default=None,
        help=(
            "Optional email to configure in pyalex.config.email. "
            "If omitted, no email is set, and requests are made without contact info."
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

    # Subcommand: missing
    p_missing = sub.add_parser(
        "missing", help="List entries missing OpenAlex IDs in '-oa.bib'."
    )
    p_missing.add_argument(
        "path", help="File or directory of processed .bib (files ending in '-oa.bib')."
    )

    args = parser.parse_args()

    # Initialize pyalex config for robust usage
    init_pyalex_config(email=args.email)

    if args.command == "process":
        files = find_bib_files(args.path, mode="original")
        sorted_files = sort_bib_files_by_year(files)
        for bf in sorted_files:
            handle_process(bf, args.interactive, args.force, args.strict)

    elif args.command == "fetch":
        files = find_bib_files(args.path, mode="processed")
        sorted_files = sort_bib_files_by_year(files)
        for bf in sorted_files:
            handle_fetch(bf, args.output_dir, args.force)

    elif args.command == "missing":
        files = find_bib_files(args.path, mode="processed")
        sorted_files = sort_bib_files_by_year(files)
        for bf in sorted_files:
            handle_missing(bf)


if __name__ == "__main__":
    main()
