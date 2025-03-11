# tests/test_matching.py

import pytest
from alexify.matching import (
    clean_bibtex_entry,
    fuzzy_match_authors,
    fuzzy_match_titles,
    match_name_parts,
    normalize_name,
    normalize_text,
    parse_bibtex_authors,
    split_name_components,
)


def test_clean_bibtex_entry():
    entry = {
        "title": "  A Title \nwith   extra \n spaces ",
        "author": " \nJohn Smith \n",
        "year": "2021",
        "abstract": "\n\nThis  is  \n\nan abstract.\n\n",
    }
    result = clean_bibtex_entry(entry)
    assert result["title"] == "A Title with extra spaces"
    assert result["author"] == "John Smith"
    assert result["year"] == "2021"  # unchanged
    assert result["abstract"] == "This  is  an abstract."


def test_normalize_text_basic():
    text = "The Quick Brown Fox, jumped on a tree!"
    # remove stopwords: "the", "on", "a"
    # remove punctuation
    # lower, strip
    # after removing stopwords -> "quick brown fox jumped tree"
    result = normalize_text(text)
    assert result == "quick brown fox jumped tree"


def test_normalize_text_accents():
    text = "Café À la carte!"
    # strip accents -> "Cafe A la carte"
    # remove stopwords? "a", "la"
    # final -> "cafe carte"
    result = normalize_text(text)
    assert result == "cafe carte"


@pytest.mark.parametrize(
    "title1,title2,expected_min_score",
    [
        ("Deep Learning", "Deep Learning", 90),
        ("Neural Networks for Vision", "Neural network: vision", 70),
        ("", "Non-empty", 0),
        (None, "Something", 0),
        ("Something", None, 0),
    ],
)
def test_fuzzy_match_titles(title1, title2, expected_min_score):
    score = fuzzy_match_titles(title1, title2)
    assert score >= 0
    assert score <= 100
    # for the fully identical "Deep Learning" we expect near 100
    if title1 and title2 and title1.lower() == title2.lower():
        assert score >= expected_min_score


def test_normalize_name():
    name = "  Dr. José M. García, Jr.  "
    # Remove punctuation, accents -> "dr jose m garcia jr"
    # lower, strip spaces -> "dr jose m garcia jr"
    result = normalize_name(name)
    assert result == "dr jose m garcia jr"


@pytest.mark.parametrize(
    "input_name,expected_first,expected_mid,expected_last",
    [
        ("John", "", "", "john"),  # single token => last name
        ("John Doe", "john", "", "doe"),
        ("Mary Ann Evans", "mary", "ann", "evans"),
        (
            "  José M. García, Jr.  ",
            "jose",
            "m",
            "garcia jr",
        ),  # check punctuation removal
    ],
)
def test_split_name_components(input_name, expected_first, expected_mid, expected_last):
    first, mid, last = split_name_components(input_name)
    assert first == expected_first
    assert mid == expected_mid
    assert last == expected_last


@pytest.mark.parametrize(
    "bib_author,oa_author,expected_score",
    [
        ("John Smith", "John Smith", 90.0),
        ("John Smith", "Jon Smythe", 0.0),  # last name mismatch => 0
        (
            "Andrew B Jones",
            "A B Jones",
            90.0,
        ),  # last name & partial match for first => ~ high
        ("Andrew B Jones", "Andrew Byron Jones", 90.0),
        ("Hans Müller", "Hans Mueller", 90.0),  # accent mismatch => should still match
        ("J. K. Rowling", "Joanne K Rowling", 90.0),
    ],
)
def test_match_name_parts(bib_author, oa_author, expected_score):
    score = match_name_parts(bib_author, oa_author)
    # If we expect an exact or near exact last name match, score >= 90
    # If last name mismatch, expect 0
    if expected_score == 0.0:
        assert score == 0.0
    else:
        assert score >= expected_score


@pytest.mark.parametrize(
    "bib_authors,oa_authors,expected_range",
    [
        (["John Smith"], ["John Smith"], (90, 100)),  # near perfect
        (["John Smith", "Jack Brown"], ["John Smith", "Jack Brown"], (90, 100)),
        (
            ["John Smith", "Jane Doe"],
            ["Jane Doe", "John Smith"],
            (90, 100),
        ),  # swapped order
        (["John Smith"], ["Joan Smythe"], (0, 10)),  # mismatch
        (
            ["Andrew B. Jones", "Chris P. Bacon"],
            ["Andrew Byron Jones", "C P Bacon"],
            (80, 100),
        ),
        # big difference in list length => penalty
        (["A", "B", "C", "D", "E"], ["A", "B"], (0, 60)),
    ],
)
def test_fuzzy_match_authors(bib_authors, oa_authors, expected_range):
    min_score, max_score = expected_range
    score = fuzzy_match_authors(bib_authors, oa_authors, threshold=70)
    assert score >= 0
    assert score <= 100
    # We only check it’s in the expected bracket
    assert min_score <= score <= max_score


def test_parse_bibtex_authors():
    field = "Smith, John and Doe, Jane Mary and SingleName and Brown, Bob"
    result = parse_bibtex_authors(field)
    # "Smith, John" => "John Smith"
    # "Doe, Jane Mary" => "Jane Mary Doe"
    # "SingleName" => "SingleName" (unchanged)
    # "Brown, Bob" => "Bob Brown"
    assert result == [
        "John Smith",
        "Jane Mary Doe",
        "SingleName",
        "Bob Brown",
    ]
