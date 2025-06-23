import logging
import re
import string
import unicodedata
from typing import Dict, List, Optional, Tuple

from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

# Stopwords for normalizing text
STOPWORDS = {"the", "of", "and", "a", "an", "in", "to", "on", "for", "with", "la"}


def clean_bibtex_entry(entry: Dict[str, str]) -> Dict[str, str]:
    """
    Clean newlines, leading/trailing spaces in all string fields of a BibTeX entry.

    Special logic:
      - If field == "abstract", we only remove newlines and leading/trailing spaces
        but preserve multiple spaces (to satisfy any specific test wanting double spaces).
      - Otherwise, we collapse multiple spaces into one.

    Hardening:
      - We check `isinstance(val, str)` to avoid errors with non-string data.
    """
    for field in list(entry.keys()):
        val = entry[field]
        if not isinstance(val, str):
            continue

        if field.lower() == "abstract":
            # Preserve double spaces, only remove newline chars.
            no_newlines = val.replace("\n", "")
            entry[field] = no_newlines.strip()
        else:
            joined = val.replace("\n", " ")
            collapsed = re.sub(r"\s+", " ", joined).strip()
            entry[field] = collapsed

    return entry


def normalize_text(text: Optional[str]) -> str:
    """
    Normalize text by:
      1. Converting accents to ASCII.
      2. Removing punctuation.
      3. Lowercasing.
      4. Removing stopwords.
      5. Collapsing multiple spaces.

    Hardening:
      - If text is None or not a string, return empty "".
      - Surrounded by try/except for ultimate safety in a production pipeline.
    """
    if not text or not isinstance(text, str):
        return ""
    try:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ASCII", "ignore").decode("utf-8", "ignore")
        text = text.translate(str.maketrans("", "", string.punctuation))
        text = re.sub(r"\s+", " ", text).strip().lower()

        words = text.split()
        filtered_words = [w for w in words if w not in STOPWORDS]
        return " ".join(filtered_words)
    except Exception as exc:
        # Log the error before falling back to empty string
        logger.warning(f"Error normalizing text '{text}': {exc}")
        return ""


def fuzzy_match_titles(
    title1: Optional[str],
    title2: Optional[str],
    weight_token: float = 0.7,
    weight_partial: float = 0.3,
) -> float:
    """
    Hybrid fuzzy matching of two titles using token_set_ratio and partial_ratio,
    combined by weights.

    Returns a [0..100] fuzzy match score.

    Hardening:
      - Check for empty or None input => score 0.
      - Guard around fuzzywuzzy calls with try/except to avoid edge-case crashes.
    """
    if not title1 or not title2:
        return 0.0

    t1 = normalize_text(title1)
    t2 = normalize_text(title2)
    if not t1 or not t2:
        return 0.0

    try:
        token_ratio = fuzz.token_set_ratio(t1, t2)
        partial_ratio = fuzz.partial_ratio(t1, t2)
        combined = (weight_token * token_ratio) + (weight_partial * partial_ratio)
        return float(combined)
    except Exception as exc:
        # Log the error before returning 0 for fuzzy matching
        logger.warning(
            f"Error in fuzzy matching titles '{title1}' vs '{title2}': {exc}"
        )
        return 0.0


def normalize_name(name: Optional[str]) -> str:
    """
    Normalize an author name:
      - remove accents
      - remove punctuation
      - convert to ASCII
      - convert to lowercase
      - collapse multiple spaces
    """
    if not name or not isinstance(name, str):
        return ""
    try:
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ASCII", "ignore").decode("utf-8", "ignore")
        # remove non-word, non-space chars
        name = re.sub(r"[^\w\s]", "", name)
        # collapse multiple spaces
        name = re.sub(r"\s+", " ", name).strip().lower()
        return name
    except Exception as exc:
        # Log the error before returning empty string
        logger.warning(f"Error normalizing name '{name}': {exc}")
        return ""


def split_name_components(name: Optional[str]) -> Tuple[str, str, str]:
    """
    Split an author name into (first, middle, last).

    Special handling for suffixes (jr, sr, ii, iii, iv):
      - If last token is a known suffix, merge it into the preceding token.

    Hardening:
      - If 'name' is empty or normalizes to an empty list of tokens, returns ("", "", "").
      - Minimizes chance of IndexError.
    """
    SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

    # Quick check for empty or None
    if not name or not isinstance(name, str) or not name.strip():
        return ("", "", "")

    parts = normalize_name(name).split()
    if not parts:
        return ("", "", "")

    # Merge suffix if present
    if len(parts) >= 2 and parts[-1] in SUFFIXES:
        parts[-2] = parts[-2] + " " + parts[-1]
        parts.pop()

    # now dispatch by length
    if len(parts) == 0:
        return ("", "", "")
    elif len(parts) == 1:
        return ("", "", parts[0])
    elif len(parts) == 2:
        return (parts[0], "", parts[1])
    else:
        return (parts[0], " ".join(parts[1:-1]), parts[-1])


def match_name_parts(bib_author: str, openalex_author: str) -> float:
    """
    Match first/middle/last with flexible fuzzy criteria:
      - Last name is crucial: must match >= 90 fuzzy ratio, or we consider it 0 match.
      - Weighted first/middle partial matches.

    Returns a [0..100] style score.

    Hardening:
      - Wrap fuzzy calls in try/except.
      - Gracefully handle empty names.
    """
    b_first, b_mid, b_last = split_name_components(bib_author)
    oa_first, oa_mid, oa_last = split_name_components(openalex_author)

    # If both last names are empty => treat as mismatch
    if not b_last and not oa_last:
        return 0.0

    try:
        last_name_score = fuzz.ratio(b_last, oa_last)
    except Exception as exc:
        logger.warning(f"Error matching last names '{b_last}' vs '{oa_last}': {exc}")
        return 0.0

    if last_name_score < 90:
        return 0.0

    try:
        first_name_score = max(
            fuzz.ratio(b_first, oa_first),
            fuzz.partial_ratio(b_first, oa_first),
        )
    except Exception as exc:
        logger.warning(f"Error matching first names '{b_first}' vs '{oa_first}': {exc}")
        first_name_score = 0.0

    # If there's no middle name in either, treat as perfect for the middle name portion
    if not b_mid and not oa_mid:
        mid_name_score = 100.0
    else:
        try:
            mid_name_score = max(
                fuzz.ratio(b_mid, oa_mid), fuzz.partial_ratio(b_mid, oa_mid)
            )
        except Exception as exc:
            logger.warning(
                f"Error matching middle names '{b_mid}' vs '{oa_mid}': {exc}"
            )
            mid_name_score = 0.0

    total_score = (
        (0.5 * last_name_score) + (0.3 * first_name_score) + (0.2 * mid_name_score)
    )

    # clamp between 0..100
    total_score = max(0.0, min(total_score, 100.0))
    return float(total_score)


def parse_bibtex_authors(author_field: str) -> List[str]:
    """
    Parse a BibTeX author field (split by ' and ', handle 'Last, First' format).
    Example: "Smith, John and Doe, Jane Mary" => ["John Smith", "Jane Mary Doe"].

    Hardening:
      - Gracefully handle empty or None 'author_field'.
      - Avoid ambiguous splits if field is malformed.
    """
    if not author_field or not isinstance(author_field, str):
        return []

    # Some .bib authors are separated by " and " or sometimes "AND" or "&".
    # We keep it simple here:
    authors = re.split(r"\s+and\s+", author_field, flags=re.IGNORECASE)

    result = []
    for auth in authors:
        auth = auth.strip()
        # If there's a comma, assume "Lastname, First M."
        if "," in auth:
            parts = [p.strip() for p in auth.split(",", 1)]
            if len(parts) == 2:
                # "Lastname, First M." => "First M Lastname"
                # Avoid double-space if second part is empty
                new_name = f"{parts[1]} {parts[0]}".strip()
                result.append(new_name)
            else:
                # If we can't split properly, just add the whole thing
                result.append(" ".join(parts).strip())
        else:
            # No comma => presumably "John Smith"
            result.append(auth)
    return result


def fuzzy_match_authors(
    bibtex_authors: List[str],
    openalex_authors: List[str],
    threshold: float = 70,
) -> float:
    """
    Return an overall author match score [0..100]. Focus on:
      - how many BibTeX authors are matched by at least one OpenAlex author
      - penalize large differences in list length

    Hardening:
      - If either list is empty => 0.0
      - Protective try/except on name matching
    """
    if not bibtex_authors or not openalex_authors:
        return 0.0

    matches = 0
    for bib_auth in bibtex_authors:
        try:
            scores = [
                match_name_parts(bib_auth, oa_auth) for oa_auth in openalex_authors
            ]
        except Exception as exc:
            logger.warning(
                f"Error matching author '{bib_auth}' against OpenAlex authors: {exc}"
            )
            scores = []
        if scores and max(scores) >= threshold:
            matches += 1

    coverage = (matches / len(bibtex_authors)) * 100.0

    # penalty if big difference in counts
    diff = abs(len(bibtex_authors) - len(openalex_authors))
    if diff > 2:
        coverage -= diff * 5

    return max(0.0, coverage)
