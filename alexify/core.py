import concurrent.futures
import json
import logging
import os
import re
from typing import Dict, List, Optional

import bibtexparser
from bibtexparser.bparser import BibTexParser

from .search import fetch_openalex_works_by_dois

logger = logging.getLogger("alexify.core")


def load_bib_file(bib_path: str) -> Optional[bibtexparser.bibdatabase.BibDatabase]:
    """
    Safely load a BibTeX file, returning a BibDatabase object or None on error.

    Hardening:
      - Check if file is accessible
      - Use try/except to handle parse errors
    """
    if not os.path.isfile(bib_path):
        logger.error(f"Bib file does not exist or is not a file: {bib_path}")
        return None
    try:
        parser = BibTexParser(common_strings=True)
        with open(bib_path, "r") as f:
            return bibtexparser.load(f, parser)
    except (FileNotFoundError, PermissionError) as exc:
        logger.error(f"File access error loading {bib_path}: {exc}")
        return None
    except (UnicodeDecodeError, UnicodeError) as exc:
        logger.error(f"Unicode encoding error loading {bib_path}: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Unexpected error loading {bib_path}: {exc}")
        return None


def save_bib_file(bib_path: str, bib_db: bibtexparser.bibdatabase.BibDatabase) -> None:
    """
    Save the updated bib_db to bib_path. Each entry should have "ENTRYTYPE" and uppercase "ID"
    to avoid writer crashes with bibtexparser.

    Hardening:
      - Use try/except for file write
      - If it fails, log the error
    """
    from bibtexparser.bwriter import BibTexWriter

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = ("ID",)

    try:
        with open(bib_path, "w") as out:
            out.write(writer.write(bib_db))
        logger.info(f"Saved BibTeX to: {bib_path}")
    except (FileNotFoundError, PermissionError) as exc:
        logger.error(f"File access error saving {bib_path}: {exc}")
    except (UnicodeEncodeError, UnicodeError) as exc:
        logger.error(f"Unicode encoding error saving {bib_path}: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error saving {bib_path}: {exc}")


def find_bib_files(path: str, mode: str = "original") -> List[str]:
    """
    Recursively find .bib files with comprehensive error handling.

    mode='original' => only .bib not ending in '-oa.bib'
    mode='processed' => only .bib files ending in '-oa.bib'
    """
    found = []

    # Validate input parameters
    if not isinstance(path, str) or not path.strip():
        logger.error("Invalid path provided: must be a non-empty string")
        return found

    if mode not in ("original", "processed"):
        logger.error(f"Invalid mode '{mode}': must be 'original' or 'processed'")
        return found

    try:
        # Check if path exists
        if not os.path.exists(path):
            logger.error(f"Path does not exist: {path}")
            return found

        # Handle file path
        if os.path.isfile(path):
            try:
                if mode == "original":
                    if path.endswith(".bib") and not path.endswith("-oa.bib"):
                        found.append(path)
                else:  # processed
                    if path.endswith("-oa.bib"):
                        found.append(path)
            except (OSError, PermissionError) as exc:
                logger.error(f"Error accessing file {path}: {exc}")

        # Handle directory path
        elif os.path.isdir(path):
            try:
                for root, _, files in os.walk(path):
                    # Skip books directories
                    if "books" in root:
                        continue

                    try:
                        for f in files:
                            try:
                                if mode == "original":
                                    if f.endswith(".bib") and not f.endswith("-oa.bib"):
                                        found.append(os.path.join(root, f))
                                else:
                                    if f.endswith("-oa.bib"):
                                        found.append(os.path.join(root, f))
                            except (OSError, ValueError) as exc:
                                logger.warning(
                                    f"Error processing file {f} in {root}: {exc}"
                                )
                                continue
                    except (OSError, PermissionError) as exc:
                        logger.warning(f"Error accessing directory {root}: {exc}")
                        continue

            except (OSError, PermissionError) as exc:
                logger.error(f"Error walking directory {path}: {exc}")

        else:
            logger.error(f"Path {path} is neither file nor directory")

    except (OSError, PermissionError) as exc:
        logger.error(f"Error accessing path {path}: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error processing path {path}: {exc}")

    return found


def extract_year_from_filename(filename: str) -> Optional[int]:
    """
    Attempt to extract a 4-digit year from the filename. Return int or None.

    Hardening:
      - If no 4-digit match, return None
    """
    m = re.search(r"(\d{4})", filename)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def sort_bib_files_by_year(bib_files: List[str]) -> List[str]:
    """
    Sort .bib files by any 4-digit year found in their filenames.

    Hardening:
      - If no year found, they go at the end.
    """
    with_year = []
    without_year = []
    for bf in bib_files:
        fname = os.path.basename(bf)
        yr = extract_year_from_filename(fname)
        if yr:
            with_year.append((yr, bf))
        else:
            without_year.append((None, bf))
    with_year.sort(key=lambda x: x[0])
    sorted_list = [b[1] for b in with_year]
    sorted_list.extend([b[1] for b in without_year])
    return sorted_list


def process_bib_entries_by_dois(entries_with_dois: List[Dict[str, str]]) -> bool:
    """
    Fetch OpenAlex IDs for entries with DOIs (in batch) and update them if found.
    Return True if any were updated.

    Hardening:
      - If no entries, return False
      - The fetch is done in a single call to 'fetch_openalex_works_by_dois'.
      - If fetch fails or partially fails, we handle it gracefully.
    """
    if not entries_with_dois:
        return False

    dois = [ent.get("doi", "").strip() for ent in entries_with_dois]
    results = fetch_openalex_works_by_dois(dois)

    modified = False
    for entry, wid in zip(entries_with_dois, results):
        if wid:
            entry["openalex"] = wid
            logger.info(f"[DOI MATCH] {entry.get('title', '')} => {wid}")
            modified = True
    return modified


def compute_metadata_score(entry: Dict[str, str], work: Dict) -> float:
    """
    Simple year-based scoring logic, returning [0..100].

    Hardening:
      - If year is not an integer, skip. If missing publication_year, skip
    """
    meta = 50.0
    bib_year_str = entry.get("year", "").strip()
    oa_year = work.get("publication_year")
    if bib_year_str and oa_year:
        try:
            bib_year = int(bib_year_str)
            diff = abs(bib_year - int(oa_year))
            if diff == 0:
                meta += 10
            elif diff == 1:
                meta += 5
            elif diff <= 5:
                meta -= 5
            else:
                meta -= 15
        except ValueError:
            # If can't convert, do nothing
            pass

    return max(0.0, min(meta, 100.0))


def compute_overall_score(entry: Dict[str, str], work: Dict) -> float:
    """
    Weighted combo: Title (50%), Authors (30%), Metadata (20%).

    Hardening:
      - Use safe calls to fuzzy match.
      - If 'authorships' is missing or not a list, handle gracefully.
    """
    from .matching import fuzzy_match_authors, fuzzy_match_titles, parse_bibtex_authors

    # Title
    title_score = fuzzy_match_titles(entry.get("title"), work.get("title"))

    # Authors
    authors_bib = parse_bibtex_authors(entry.get("author", ""))
    authlist_oa = []
    authorships = work.get("authorships")
    if isinstance(authorships, list):
        for a in authorships:
            if (
                isinstance(a, dict)
                and "author" in a
                and a["author"]
                and isinstance(a["author"], dict)
                and a["author"].get("display_name")
            ):
                authlist_oa.append(a["author"]["display_name"])

    author_score = fuzzy_match_authors(authors_bib, authlist_oa)

    # Metadata
    m_score = compute_metadata_score(entry, work)

    overall = (0.5 * title_score) + (0.3 * author_score) + (0.2 * m_score)
    return max(0.0, min(overall, 100.0))


def process_bib_entry_by_title(
    entry: Dict[str, str], user_interaction: bool = False, strict: bool = False
):
    """
    Attempt fuzzy matching if there's no 'openalex' yet. Return (changed, matched).

    Hardening:
      - If there's no title, skip
      - If fuzzy scoring leads to an error, treat as mismatch
    """
    from .matching import (
        clean_bibtex_entry,
        parse_bibtex_authors,
        split_name_components,
    )
    from .search import fetch_all_candidates_for_entry

    if "openalex" in entry:
        logger.debug(f"Entry already has openalex: {entry['openalex']}, skipping.")
        return (False, True)

    clean_bibtex_entry(entry)
    title = entry.get("title", "")
    if not title:
        return (False, False)

    # Extract first author last name
    authors = parse_bibtex_authors(entry.get("author", ""))
    first_author_ln = ""
    if authors:
        _, _, last = split_name_components(authors[0])
        first_author_ln = last

    year = entry.get("year", "").strip()
    candidates = fetch_all_candidates_for_entry(title, first_author_ln, year)
    if not candidates:
        return (False, False)

    # Compute fuzzy scores
    scored = []
    for w in candidates:
        sc = compute_overall_score(entry, w)
        scored.append((sc, w))
    scored.sort(key=lambda x: x[0], reverse=True)

    # Define thresholds
    if strict:
        high_thresh = 90
        maybe_thresh = 70
    else:
        high_thresh = 85
        maybe_thresh = 60

    best_score, best_work = scored[0]
    wid = best_work.get("id", "")

    # If best is high => auto accept
    if best_score >= high_thresh:
        wid = _extract_short_id_if_needed(wid)
        entry["openalex"] = wid
        logger.info(f"[HIGH] {title} => {wid} (score={best_score:.1f})")
        return (True, True)

    # If best is in maybe range => interactive if requested, else accept
    if best_score >= maybe_thresh:
        if user_interaction:
            accepted = _user_prompt_for_candidate(entry, best_work, best_score)
            if accepted:
                wid = _extract_short_id_if_needed(wid)
                entry["openalex"] = wid
                logger.info(f"User accepted => {entry['openalex']}")
                return (True, True)
            else:
                return (False, False)
        else:
            wid = _extract_short_id_if_needed(wid)
            entry["openalex"] = wid
            logger.info(f"[MED] {title} => {wid} (score={best_score:.1f})")
            return (True, True)

    # If below threshold => no match
    return (False, False)


def _extract_short_id_if_needed(wid: str) -> str:
    """
    If wid starts with "https://openalex.org/", return only the short portion.
    Else return as-is.
    """
    if wid.startswith("https://openalex.org/"):
        return wid.rsplit("/", 1)[-1]
    return wid


def _user_prompt_for_candidate(entry: Dict[str, str], work: Dict, score: float) -> bool:
    """
    Prompt the user to accept/reject a candidate match.
    Returns True if user accepts, False otherwise.
    """
    print("\n--- Potential Match Found ---")
    print(f"BibTeX Title: {entry.get('title', 'N/A')}")
    print(f"OpenAlex Title: {work.get('title', 'N/A')}")
    print(
        f"BibTeX Year: {entry.get('year', 'N/A')} vs. OA Year: {work.get('publication_year', 'N/A')}"
    )
    print(f"Score: {score:.1f}/100")
    print(f"OpenAlex ID: {work.get('id', '')}")
    resp = input("Accept match? (y/n) ").lower().strip()
    return resp.startswith("y")


def handle_process(bib_file: str, user_interaction: bool, force: bool, strict: bool):
    """
    - If new_bib exists and not forced => skip
    - load the bib
    - process DOIs => increment success_count
    - process title => success/fail
    - log final

    Hardening:
      - Guard for empty or None DB
    """
    new_bib = os.path.splitext(bib_file)[0] + "-oa.bib"
    if os.path.exists(new_bib) and not force:
        logger.info(
            f"Skipping {bib_file}, {new_bib} already present (use --force to overwrite)."
        )
        return

    db = load_bib_file(bib_file)
    if not db:
        return

    entries = db.entries
    logger.info(f"Processing {bib_file}, # entries: {len(entries)}")

    with_dois = [e for e in entries if isinstance(e.get("doi"), str) and e["doi"]]
    without_dois = [
        e for e in entries if not isinstance(e.get("doi"), str) or not e.get("doi")
    ]

    modified = False
    success_count = 0
    fail_count = 0

    # Step A: batch fetch by DOIs
    doi_modified = process_bib_entries_by_dois(with_dois)
    if doi_modified:
        modified = True
    for e in with_dois:
        if "openalex" in e:
            success_count += 1

    # Step B: process title-based
    for e in without_dois:
        changed, matched = process_bib_entry_by_title(e, user_interaction, strict)
        if changed:
            modified = True
        if matched:
            success_count += 1
        else:
            fail_count += 1

    if modified:
        save_bib_file(new_bib, db)
        logger.info(f"Wrote updated file => {new_bib}")
    else:
        logger.info("No changes made, skipping write.")

    total_entries = len(entries)
    logger.info(
        f"Done: {bib_file} => matched {success_count} / {total_entries}. Unmatched: {fail_count}."
    )


def handle_fetch(bib_file: str, output_dir: str, force: bool):
    """
    For each entry with openalex => fetch JSON => store in <output_dir>/<year>/<ID>.json

    Hardening:
      - parallel fetch with ThreadPoolExecutor
      - if a fetch fails, logs error
    """
    db = load_bib_file(bib_file)
    if not db:
        return

    entries = db.entries
    total = len(entries)
    logger.info(f"Fetching for {bib_file}, # entries: {total}")

    def do_fetch(e):
        if "openalex" in e:
            return _fetch_and_save_work(e["openalex"], bib_file, output_dir, force)
        return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(do_fetch, entries))

    fetched = sum(1 for r in results if r)
    logger.info(f"Fetched {fetched}/{total} from {bib_file}")


def _fetch_and_save_work(
    work_id: str, bib_file: str, out_dir: str, force: bool
) -> bool:
    """
    Fetch a single work_id from OpenAlex API. Save as JSON.

    Hardening:
      - If file already exists and not force => skip.
      - If anything fails => return False.
    """
    import httpx
    from .search import _CONFIG, _make_request_with_retry

    fname = os.path.basename(bib_file)
    year = extract_year_from_filename(fname)
    subdir = os.path.join(out_dir, str(year) if year else "unknown-year")

    try:
        os.makedirs(subdir, exist_ok=True)
    except PermissionError as e:
        logger.error(f"Permission error creating {subdir}: {e}")
        return False

    outpath = os.path.join(subdir, f"{work_id}.json")
    if os.path.exists(outpath) and not force:
        logger.debug(f"{outpath} exists, skipping fetch.")
        return False

    try:
        # Fetch work from OpenAlex API
        url = f"https://api.openalex.org/works/{work_id}"
        params = {}
        if _CONFIG["email"]:
            params["mailto"] = _CONFIG["email"]

        with httpx.Client() as client:
            data = _make_request_with_retry(client, url, params)

            if not data:
                logger.warning(f"No Work found for {work_id}")
                return False

            with open(outpath, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved: {outpath}")
            return True
    except (FileNotFoundError, PermissionError) as exc:
        logger.error(f"File access error saving work {work_id}: {exc}")
        return False
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.error(f"HTTP error fetching work {work_id}: {exc}")
        return False
    except (json.decoder.JSONDecodeError, TypeError) as exc:
        logger.error(f"JSON serialization error for work {work_id}: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error fetching {work_id}: {exc}")
        return False


def handle_missing(bib_file: str):
    """
    List entries lacking 'openalex'.

    Hardening:
      - If bib cannot be loaded, do nothing
      - Count them, log a summary
    """
    db = load_bib_file(bib_file)
    if not db:
        return

    missing_count = 0
    for e in db.entries:
        if "openalex" not in e:
            logger.info(f"No openalex => Title: {e.get('title', 'N/A')}")
            missing_count += 1
    logger.info(f"Total missing from {bib_file}: {missing_count}")
