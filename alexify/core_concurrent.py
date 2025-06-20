"""Enhanced concurrent version of core functionality."""

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .core import (
    compute_overall_score,
    extract_year_from_filename,
    load_bib_file,
    save_bib_file,
)
from .matching import clean_bibtex_entry
from .search_async import (
    fetch_all_candidates_for_entry_async,
    fetch_multiple_works_async,
    fetch_openalex_works_by_dois_async,
    init_async_config,
)

logger = logging.getLogger(__name__)

# Configuration for concurrent processing
_CONCURRENT_CONFIG = {
    "max_file_workers": 4,  # Process multiple files concurrently
    "max_entry_workers": 20,  # Process entries within a file concurrently
    "max_scoring_workers": 8,  # Score candidates concurrently
    "batch_size": 50,  # Batch size for processing
}


def init_concurrent_config(
    max_file_workers: int = 4,
    max_entry_workers: int = 20,
    max_scoring_workers: int = 8,
    batch_size: int = 50,
):
    """Initialize concurrent processing configuration."""
    _CONCURRENT_CONFIG["max_file_workers"] = max_file_workers
    _CONCURRENT_CONFIG["max_entry_workers"] = max_entry_workers
    _CONCURRENT_CONFIG["max_scoring_workers"] = max_scoring_workers
    _CONCURRENT_CONFIG["batch_size"] = batch_size


async def process_bib_entries_by_dois_concurrent(
    entries: List[Dict[str, Any]], client: httpx.AsyncClient
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Process entries with DOIs concurrently using async API calls.
    Returns (updated_entries, num_changed).
    """
    # Extract DOIs
    dois = []
    doi_indices = []

    for i, entry in enumerate(entries):
        if "doi" in entry and "openalex" not in entry:
            dois.append(entry["doi"])
            doi_indices.append(i)

    if not dois:
        return entries, 0

    logger.info(f"Processing {len(dois)} DOIs concurrently...")

    # Fetch OpenAlex IDs concurrently
    openalex_ids = await fetch_openalex_works_by_dois_async(dois, client)

    # Update entries
    changed = 0
    for idx, oa_id in zip(doi_indices, openalex_ids):
        if oa_id:
            entries[idx]["openalex"] = oa_id
            changed += 1
            logger.debug(
                f"Matched entry {entries[idx].get('ID', 'Unknown')} -> {oa_id}"
            )

    return entries, changed


def _compute_score_for_entry(args: Tuple[Dict[str, Any], Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """Top-level function for multiprocessing - must be pickleable."""
    entry, candidate = args
    return compute_overall_score(entry, candidate), candidate


def score_candidates_concurrent(
    entry: Dict[str, Any], candidates: List[Dict[str, Any]]
) -> List[Tuple[float, Dict[str, Any]]]:
    """Score candidates using multiprocessing for CPU-intensive operations."""
    if not candidates:
        return []

    # Prepare arguments for multiprocessing
    args_list = [(entry, candidate) for candidate in candidates]

    # Use ProcessPoolExecutor for CPU-intensive scoring
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=_CONCURRENT_CONFIG["max_scoring_workers"]
    ) as executor:
        scored = list(executor.map(_compute_score_for_entry, args_list))

    return sorted(scored, reverse=True)


async def process_bib_entry_by_title_async(
    entry: Dict[str, Any],
    client: httpx.AsyncClient,
    user_interaction: bool = False,
    strict: bool = False,
) -> Tuple[bool, bool]:
    """
    Async version of process_bib_entry_by_title.
    Returns (changed, matched).
    """
    if "openalex" in entry:
        return False, True

    # Extract entry info
    entry_clean = clean_bibtex_entry(entry)
    author_lastname = entry_clean.get("author_lastname", "")
    year = entry_clean.get("year", "")
    title = entry_clean.get("title", "")

    if not title:
        logger.debug(f"Entry {entry.get('ID', 'Unknown')} has no title.")
        return False, False

    # Fetch candidates asynchronously
    candidates = await fetch_all_candidates_for_entry_async(
        title, author_lastname, year, client
    )

    if not candidates:
        logger.debug(f"No candidates for {entry.get('ID', 'Unknown')}")
        return False, False

    # Score candidates concurrently
    scored = score_candidates_concurrent(entry, candidates)

    if not scored:
        return False, False

    best_score, best_work = scored[0]

    # Apply matching logic (same as original)
    HIGH_CONFIDENCE = 80
    MAYBE_THRESHOLD = 60 if not strict else 70

    if best_score >= HIGH_CONFIDENCE:
        short_id = best_work["id"].rsplit("/", 1)[-1]
        entry["openalex"] = short_id
        logger.info(
            f"Matched {entry.get('ID', 'Unknown')} -> {short_id} (score: {best_score:.1f})"
        )
        return True, True
    elif best_score >= MAYBE_THRESHOLD:
        if user_interaction:
            # In concurrent mode, we'll skip interactive prompts for now
            logger.info(
                f"Borderline match for {entry.get('ID', 'Unknown')} (score: {best_score:.1f}), skipping in concurrent mode"
            )
            return False, False
        else:
            logger.info(
                f"Low confidence match for {entry.get('ID', 'Unknown')} (score: {best_score:.1f}), skipping"
            )
            return False, False
    else:
        logger.debug(
            f"Best score {best_score:.1f} below threshold for {entry.get('ID', 'Unknown')}"
        )
        return False, False


async def process_entries_batch_async(
    entries: List[Dict[str, Any]],
    client: httpx.AsyncClient,
    user_interaction: bool = False,
    strict: bool = False,
) -> Tuple[int, int]:
    """Process a batch of entries concurrently."""
    tasks = []
    for entry in entries:
        if "doi" not in entry and "openalex" not in entry:
            tasks.append(
                process_bib_entry_by_title_async(
                    entry, client, user_interaction, strict
                )
            )
        else:
            # Create a completed future for entries that already have DOI/OpenAlex
            future = asyncio.create_future()
            future.set_result((False, False))
            tasks.append(future)

    results = await asyncio.gather(*tasks)

    changed = sum(1 for c, _ in results if c)
    matched = sum(1 for _, m in results if m)

    return changed, matched


async def handle_process_concurrent(
    bib_file: str,
    user_interaction: bool = False,
    force: bool = False,
    strict: bool = False,
) -> None:
    """
    Enhanced concurrent version of handle_process.
    Processes entries in batches with massive parallelization.
    """
    logger.info(f"Processing {bib_file} with concurrent mode...")

    # Check if already processed
    outfile = bib_file.replace(".bib", "-oa.bib")
    if os.path.exists(outfile) and not force:
        logger.info(f"{outfile} already exists. Use --force to overwrite.")
        return

    # Load BibTeX file
    db = load_bib_file(bib_file)
    if not db:
        return

    entries = db.entries
    total = len(entries)
    logger.info(f"Processing {bib_file}, # entries: {total}")

    async with httpx.AsyncClient() as client:
        # First, process entries with DOIs concurrently
        entries, changed_dois = await process_bib_entries_by_dois_concurrent(
            entries, client
        )

        # Then process entries without DOIs or OpenAlex IDs
        entries_to_process = [
            e for e in entries if "doi" not in e and "openalex" not in e
        ]

        if entries_to_process:
            logger.info(
                f"Processing {len(entries_to_process)} entries by title search..."
            )

            # Process in batches
            batch_size = _CONCURRENT_CONFIG["batch_size"]
            total_changed = 0
            total_matched = 0

            for i in range(0, len(entries_to_process), batch_size):
                batch = entries_to_process[i : i + batch_size]
                changed, matched = await process_entries_batch_async(
                    batch, client, user_interaction, strict
                )
                total_changed += changed
                total_matched += matched

                # Progress update
                processed = min(i + batch_size, len(entries_to_process))
                logger.info(
                    f"Processed {processed}/{len(entries_to_process)} entries..."
                )
        else:
            total_changed = 0
            total_matched = 0

    # Update and save
    db.entries = entries
    matched_total = sum(1 for e in entries if "openalex" in e)
    logger.info(f"Matched {matched_total}/{total} entries")

    save_bib_file(db, outfile)
    logger.info(f"Saved to {outfile}")


async def handle_fetch_concurrent(
    bib_file: str, output_dir: str, force: bool = False
) -> None:
    """
    Enhanced concurrent version of handle_fetch.
    Fetches OpenAlex data for all entries concurrently.
    """
    db = load_bib_file(bib_file)
    if not db:
        return

    entries = db.entries
    total = len(entries)
    logger.info(f"Fetching for {bib_file}, # entries: {total}")

    # Extract OpenAlex IDs and prepare fetch tasks
    fetch_tasks = []
    entry_indices = []

    for i, entry in enumerate(entries):
        if "openalex" in entry:
            fetch_tasks.append(entry["openalex"])
            entry_indices.append(i)

    if not fetch_tasks:
        logger.info("No entries with OpenAlex IDs to fetch")
        return

    logger.info(f"Fetching {len(fetch_tasks)} works concurrently...")

    async with httpx.AsyncClient() as client:
        # Fetch all works concurrently
        works = await fetch_multiple_works_async(fetch_tasks, client)

    # Save results
    saved = 0
    fname = os.path.basename(bib_file)

    for idx, work in zip(entry_indices, works):
        if work:
            year = extract_year_from_filename(fname)
            if not year and "year" in entries[idx]:
                year = entries[idx]["year"]

            subdir = os.path.join(output_dir, str(year) if year else "unknown-year")
            os.makedirs(subdir, exist_ok=True)

            work_id = work["id"].rsplit("/", 1)[-1]
            outpath = os.path.join(subdir, f"{work_id}.json")

            if not os.path.exists(outpath) or force:
                try:
                    with open(outpath, "w", encoding="utf-8") as f:
                        json.dump(work, f, indent=2, ensure_ascii=False)
                    saved += 1
                    logger.debug(f"Saved {work_id} to {outpath}")
                except Exception as e:
                    logger.error(f"Error saving {work_id}: {e}")

    logger.info(f"Fetched and saved {saved}/{len(fetch_tasks)} works")


def process_files_concurrent(files: List[str], process_func, *args, **kwargs) -> None:
    """
    Process multiple files concurrently using ProcessPoolExecutor.
    This avoids GIL limitations for CPU-intensive operations.
    """
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=_CONCURRENT_CONFIG["max_file_workers"]
    ) as executor:
        futures = []
        for file in files:
            future = executor.submit(process_func, file, *args, **kwargs)
            futures.append((file, future))

        # Wait for completion and handle results
        for file, future in futures:
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing {file}: {e}")


def run_async_process(
    files: List[str],
    user_interaction: bool = False,
    force: bool = False,
    strict: bool = False,
    email: Optional[str] = None,
    max_concurrent_requests: int = 20,
) -> None:
    """
    Run the async processing pipeline for multiple files.
    This is the main entry point for concurrent processing.
    """
    # Initialize async configuration
    init_async_config(email=email, max_concurrent_requests=max_concurrent_requests)

    # Process each file
    async def process_all():
        tasks = []
        for file in files:
            task = handle_process_concurrent(file, user_interaction, force, strict)
            tasks.append(task)

        # Process files with limited concurrency
        sem = asyncio.Semaphore(_CONCURRENT_CONFIG["max_file_workers"])

        async def process_with_sem(task):
            async with sem:
                await task

        await asyncio.gather(*[process_with_sem(task) for task in tasks])

    # Run the async event loop
    asyncio.run(process_all())


def run_async_fetch(
    files: List[str],
    output_dir: str,
    force: bool = False,
    email: Optional[str] = None,
    max_concurrent_requests: int = 20,
) -> None:
    """
    Run the async fetch pipeline for multiple files.
    """
    # Initialize async configuration
    init_async_config(email=email, max_concurrent_requests=max_concurrent_requests)

    # Process each file
    async def fetch_all():
        tasks = []
        for file in files:
            task = handle_fetch_concurrent(file, output_dir, force)
            tasks.append(task)

        # Process files with limited concurrency
        sem = asyncio.Semaphore(_CONCURRENT_CONFIG["max_file_workers"])

        async def fetch_with_sem(task):
            async with sem:
                await task

        await asyncio.gather(*[fetch_with_sem(task) for task in tasks])

    # Run the async event loop
    asyncio.run(fetch_all())
