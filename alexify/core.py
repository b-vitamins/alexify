# alexify/core.py

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
    """Safely load a BibTeX file, returning a bibdatabase object or None on error."""
    if not os.path.isfile(bib_path):
        logger.error(f"Bib file does not exist or is not a file: {bib_path}")
        return None
    try:
        parser = BibTexParser(common_strings=True)
        with open(bib_path, "r") as f:
            return bibtexparser.load(f, parser)
    except Exception as exc:
        logger.error(f"Failed to load {bib_path}: {exc}")
        return None


def save_bib_file(bib_path: str, bib_db: bibtexparser.bibdatabase.BibDatabase) -> None:
    """
    Save the updated bib_db to bib_path. Each entry should have "ENTRYTYPE" and uppercase "ID"
    to avoid writer crashes with bibtexparser.
    """
    from bibtexparser.bwriter import BibTexWriter

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None

    try:
        with open(bib_path, "w") as out:
            out.write(writer.write(bib_db))
        logger.info(f"Saved BibTeX to: {bib_path}")
    except Exception as exc:
        logger.error(f"Failed to save {bib_path}: {exc}")


def find_bib_files(path: str, mode: str = "original") -> List[str]:
    """
    Recursively find .bib files.

    mode='original' => only .bib not ending in '-oa.bib'
    mode='processed' => only .bib files ending in '-oa.bib'
    """
    found = []
    if os.path.isfile(path):
        if mode == "original":
            if path.endswith(".bib") and not path.endswith("-oa.bib"):
                found.append(path)
        else:  # processed
            if path.endswith("-oa.bib"):
                found.append(path)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            if "books" in root:
                continue
            for f in files:
                if mode == "original":
                    if f.endswith(".bib") and not f.endswith("-oa.bib"):
                        found.append(os.path.join(root, f))
                else:
                    if f.endswith("-oa.bib"):
                        found.append(os.path.join(root, f))
    else:
        logger.error(f"Path {path} is neither file nor directory.")
    return found


def extract_year_from_filename(filename: str) -> Optional[int]:
    """Attempt to extract a 4-digit year from the filename. Return int or None."""
    m = re.search(r"(\d{4})", filename)
    if m:
        return int(m.group(1))
    return None


def sort_bib_files_by_year(bib_files: List[str]) -> List[str]:
    """Sort .bib files by any 4-digit year found in their filenames."""
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
    """Simple year-based scoring logic, returning [0..100]."""
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
            pass
    return max(0.0, min(meta, 100.0))


def compute_overall_score(entry: Dict[str, str], work: Dict) -> float:
    """
    Weighted combo: Title (50%), Authors(30%), Metadata(20%).
    """
    from .matching import fuzzy_match_authors, fuzzy_match_titles, parse_bibtex_authors

    title_score = fuzzy_match_titles(entry.get("title"), work.get("title"))
    authors_bib = parse_bibtex_authors(entry.get("author", ""))

    # Gather openalex authors
    authlist_oa = []
    authorships = work.get("authorships")
    if isinstance(authorships, list):
        for a in authorships:
            if a and a.get("author") and a["author"].get("display_name"):
                authlist_oa.append(a["author"]["display_name"])

    author_score = fuzzy_match_authors(authors_bib, authlist_oa)
    m_score = compute_metadata_score(entry, work)

    return (0.5 * title_score) + (0.3 * author_score) + (0.2 * m_score)


def process_bib_entry_by_title(
    entry: Dict[str, str], user_interaction: bool = False, strict: bool = False
):
    """
    Attempt fuzzy matching if there's no 'openalex' yet. Return (changed, matched).
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

    authors = parse_bibtex_authors(entry.get("author", ""))
    first_author_ln = ""
    if authors:
        _, _, last = split_name_components(authors[0])
        first_author_ln = last

    year = entry.get("year", "").strip()
    candidates = fetch_all_candidates_for_entry(title, first_author_ln, year)
    if not candidates:
        return (False, False)

    scored = []
    for w in candidates:
        sc = compute_overall_score(entry, w)
        scored.append((sc, w))
    scored.sort(key=lambda x: x[0], reverse=True)

    if strict:
        high_thresh = 90
        maybe_thresh = 70
    else:
        high_thresh = 85
        maybe_thresh = 60

    best_score, best_work = scored[0]
    wid = best_work.get("id", "")

    if best_score >= high_thresh:
        if wid.startswith("https://openalex.org/"):
            wid = wid.rsplit("/", 1)[-1]
        entry["openalex"] = wid
        logger.info(f"[HIGH] {title} => {wid} (score={best_score:.1f})")
        return (True, True)

    if best_score >= maybe_thresh:
        if user_interaction:
            accepted = _user_prompt_for_candidate(entry, best_work, best_score)
            if accepted:
                if wid.startswith("https://openalex.org/"):
                    wid = wid.rsplit("/", 1)[-1]
                entry["openalex"] = wid
                logger.info(f"User accepted => {entry['openalex']}")
                return (True, True)
            else:
                return (False, False)
        else:
            if wid.startswith("https://openalex.org/"):
                wid = wid.rsplit("/", 1)[-1]
            entry["openalex"] = wid
            logger.info(f"[MED] {title} => {wid} (score={best_score:.1f})")
            return (True, True)

    return (False, False)


def _user_prompt_for_candidate(entry: Dict[str, str], work: Dict, score: float) -> bool:
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
    If new_bib exists and not forced => skip
    load the bib
    process DOIs => increment success_count for each that has openalex
    process title => success/fail
    log final
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

    with_dois = [e for e in entries if "doi" in e]
    without_dois = [e for e in entries if "doi" not in e]

    modified = False
    success_count = 0
    fail_count = 0

    # Step A: batch fetch by DOIs
    doi_modified = process_bib_entries_by_dois(with_dois)
    if doi_modified:
        modified = True
    # Now any entry that got an ID => success_count
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
    from .search import pyalex

    fname = os.path.basename(bib_file)
    year = extract_year_from_filename(fname)
    subdir = os.path.join(out_dir, str(year) if year else "unknown-year")

    try:
        os.makedirs(subdir, exist_ok=True)
    except PermissionError:
        pass

    outpath = os.path.join(subdir, f"{work_id}.json")
    if os.path.exists(outpath) and not force:
        logger.debug(f"{outpath} exists, skipping fetch.")
        return False

    try:
        res = pyalex.Works()[work_id]
        if not res:
            logger.warning(f"No Work found for {work_id}")
            return False
        with open(outpath, "w") as f:
            json.dump(res, f, indent=2)
        logger.info(f"Saved: {outpath}")
        return True
    except Exception as exc:
        logger.error(f"Failed fetching {work_id}: {exc}")
        return False


def handle_missing(bib_file: str):
    """List entries lacking 'openalex'."""
    db = load_bib_file(bib_file)
    if not db:
        return
    missing_count = 0
    for e in db.entries:
        if "openalex" not in e:
            logger.info(f"No openalex => Title: {e.get('title', 'N/A')}")
            missing_count += 1
    logger.info(f"Total missing from {bib_file}: {missing_count}")
