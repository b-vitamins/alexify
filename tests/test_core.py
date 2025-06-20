import logging
from unittest.mock import MagicMock, mock_open, patch

import pytest
from alexify.core import (
    compute_metadata_score,
    compute_overall_score,
    extract_year_from_filename,
    find_bib_files,
    handle_fetch,
    handle_missing,
    handle_process,
    load_bib_file,
    process_bib_entries_by_dois,
    process_bib_entry_by_title,
    save_bib_file,
    sort_bib_files_by_year,
)
from bibtexparser.bibdatabase import BibDatabase


@pytest.fixture
def mock_logger(caplog):
    """
    Capture logs from "alexify.core" at DEBUG level
    so we see everything in caplog.text.
    """
    caplog.set_level(logging.DEBUG, logger="alexify.core")
    return caplog


##########################
# load_bib_file
##########################


@patch("os.path.isfile", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="""
@article{test1,
  title={Sample Title},
  author={Smith, John},
  year={2021}
}
""",
)
def test_load_bib_file_success(mock_file, mock_isfile, tmp_path):
    fake_path = str(tmp_path / "test.bib")
    db = load_bib_file(fake_path)
    assert db is not None
    assert len(db.entries) == 1
    e = db.entries[0]
    assert e["title"] == "Sample Title"
    assert e["author"] == "Smith, John"
    assert e["year"] == "2021"


@patch("os.path.isfile", return_value=False)
def test_load_bib_file_no_such_file(mock_isfile, mock_logger):
    res = load_bib_file("/not/exist.bib")
    assert res is None
    assert (
        "Bib file does not exist or is not a file: /not/exist.bib" in mock_logger.text
    )


@patch("os.path.isfile", return_value=True)
@patch("builtins.open", side_effect=Exception("Failure reading file"))
def test_load_bib_file_exception(mock_open_f, mock_isfile, mock_logger):
    res = load_bib_file("/fake/path.bib")
    assert res is None
    assert "Failed to load /fake/path.bib: Failure reading file" in mock_logger.text


##########################
# save_bib_file
##########################


@patch("builtins.open", new_callable=mock_open)
def test_save_bib_file_success(mock_file, tmp_path):
    db = BibDatabase()
    db.entries = [
        {
            "ENTRYTYPE": "article",
            "ID": "testid",
            "title": "Test Title",
            "author": "Doe, Jane",
            "year": "2022",
        }
    ]
    out_path = str(tmp_path / "output.bib")
    save_bib_file(out_path, db)

    mock_file.assert_called_once_with(out_path, "w")
    handle = mock_file()
    written_data = ""
    for call_arg in handle.write.call_args_list:
        written_data += call_arg[0][0]
    assert "title = {Test Title}" in written_data
    assert "author = {Doe, Jane}" in written_data
    assert "year = {2022}" in written_data


@patch("os.path.isfile", return_value=True)
@patch("builtins.open")
def test_save_bib_file_failure(open_mock, isfile_mock, mock_logger):
    db = BibDatabase()
    db.entries = [{"ENTRYTYPE": "article", "ID": "xyz"}]
    open_mock.side_effect = Exception("Disk error")
    save_bib_file("/some/path.bib", db)
    assert "Failed to save /some/path.bib: Disk error" in mock_logger.text


##########################
# find_bib_files
##########################


@patch("os.path.isfile", return_value=True)
def test_find_bib_files_file_original(mock_isfile, tmp_path):
    test_path = str(tmp_path / "myfile.bib")
    found = find_bib_files(test_path, mode="original")
    assert found == [test_path]


@patch("os.path.isfile", return_value=True)
def test_find_bib_files_file_processed(mock_isfile, tmp_path):
    test_path = str(tmp_path / "myfile-oa.bib")
    found = find_bib_files(test_path, mode="processed")
    assert found == [test_path]


@patch("os.path.isfile", return_value=False)
@patch("os.path.isdir", return_value=False)
def test_find_bib_files_bad_path(mock_isdir, mock_isfile, mock_logger):
    out = find_bib_files("/nowhere", "original")
    assert out == []
    assert "Path /nowhere is neither file nor directory." in mock_logger.text


@patch("os.path.isdir", return_value=True)
@patch("os.walk")
def test_find_bib_files_dir_original(mock_walk, mock_isdir):
    mock_walk.return_value = [
        ("/root", [], ["file1.bib", "file2-oa.bib", "notbib.txt"]),
        ("/root/books", [], ["ignore.bib"]),
    ]
    result = find_bib_files("/root", "original")
    assert result == ["/root/file1.bib"]


@patch("os.path.isdir", return_value=True)
@patch("os.walk")
def test_find_bib_files_dir_processed(mock_walk, mock_isdir):
    mock_walk.return_value = [
        ("/root", [], ["file1.bib", "file2-oa.bib"]),
        ("/root/sub", [], ["another-oa.bib"]),
    ]
    result = find_bib_files("/root", "processed")
    assert set(result) == {"/root/file2-oa.bib", "/root/sub/another-oa.bib"}


##########################
# extract_year_from_filename, sort_bib_files_by_year
##########################


@pytest.mark.parametrize(
    "fname,expected",
    [
        ("paper_2022.bib", 2022),
        ("no-year-here.bib", None),
        ("1987-oa.bib", 1987),
        ("stuff_1234_ok.bib", 1234),
    ],
)
def test_extract_year_from_filename(fname, expected):
    assert extract_year_from_filename(fname) == expected


def test_sort_bib_files_by_year(tmp_path):
    f1 = str(tmp_path / "paper_2020.bib")
    f2 = str(tmp_path / "paper_1987.bib")
    f3 = str(tmp_path / "paper_noyear.bib")
    f4 = str(tmp_path / "random2022.bib")
    out = sort_bib_files_by_year([f1, f2, f3, f4])
    assert out == [f2, f1, f4, f3]


##########################
# process_bib_entries_by_dois
##########################


@patch("alexify.core.fetch_openalex_works_by_dois")
def test_process_bib_entries_by_dois_no_entries(mock_fetch):
    assert process_bib_entries_by_dois([]) is False
    mock_fetch.assert_not_called()


@patch("alexify.core.fetch_openalex_works_by_dois")
def test_process_bib_entries_by_dois_partial(mock_fetch, mock_logger):
    mock_fetch.return_value = ["ID1", None]
    entries = [
        {"ENTRYTYPE": "article", "ID": "a", "title": "Title1", "doi": "10.1234/foo"},
        {"ENTRYTYPE": "article", "ID": "b", "title": "Title2", "doi": "10.1234/bar"},
    ]
    modified = process_bib_entries_by_dois(entries)
    assert modified is True
    assert entries[0]["openalex"] == "ID1"
    assert "openalex" not in entries[1]
    assert "[DOI MATCH] Title1 => ID1" in mock_logger.text


##########################
# compute_metadata_score
##########################


@pytest.mark.parametrize(
    "bib_year,oa_year,expected",
    [
        ("2022", 2022, 60),
        ("2022", 2023, 55),
        ("2022", 2025, 45),
        ("2022", 2030, 35),
        ("", 2022, 50),
        ("abcd", 2022, 50),
    ],
)
def test_compute_metadata_score(bib_year, oa_year, expected):
    entry = {"year": bib_year}
    work = {"publication_year": oa_year}
    score = compute_metadata_score(entry, work)
    assert score == pytest.approx(expected, 0.1)


##########################
# compute_overall_score
##########################


@patch("alexify.matching.fuzzy_match_titles", return_value=80)
@patch("alexify.matching.fuzzy_match_authors", return_value=70)
@patch("alexify.matching.parse_bibtex_authors", return_value=["John Smith"])
@patch("alexify.core.compute_metadata_score", return_value=50)
def test_compute_overall_score(m_meta, m_parse, m_authors, m_titles):
    e = {"title": "SomeTitle", "author": "Smith, John", "year": "2021"}
    w = {
        "title": "some other",
        "authorships": [{"author": {"display_name": "J. Smith"}}],
    }
    out = compute_overall_score(e, w)
    # Weighted => 0.5*80 + 0.3*70 + 0.2*50 = 71
    assert out == 71.0


##########################
# process_bib_entry_by_title
##########################


@patch("alexify.search.fetch_all_candidates_for_entry")
def test_process_bib_entry_by_title_has_openalex(m_fetch):
    entry = {"ENTRYTYPE": "article", "ID": "X", "title": "T", "openalex": "XYZ"}
    changed, matched = process_bib_entry_by_title(entry)
    assert changed is False
    assert matched is True
    m_fetch.assert_not_called()


@patch("alexify.search.fetch_all_candidates_for_entry", return_value=[])
def test_process_bib_entry_by_title_no_candidates(m_fetch):
    entry = {"ENTRYTYPE": "article", "ID": "X", "title": "No hits?"}
    changed, matched = process_bib_entry_by_title(entry)
    assert (changed, matched) == (False, False)
    m_fetch.assert_called_once()


@patch("alexify.core.compute_overall_score", return_value=95)
@patch(
    "alexify.search.fetch_all_candidates_for_entry",
    return_value=[{"id": "https://openalex.org/W123"}],
)
def test_process_bib_entry_by_title_best_high(m_fetch, m_score, mock_logger):
    entry = {"ENTRYTYPE": "article", "ID": "X", "title": "T"}
    changed, matched = process_bib_entry_by_title(entry, False, False)
    assert changed
    assert matched
    assert entry["openalex"] == "W123"
    assert "[HIGH] T => W123 (score=95.0)" in mock_logger.text


@patch("alexify.core.compute_overall_score", return_value=75)
@patch(
    "alexify.search.fetch_all_candidates_for_entry",
    return_value=[{"id": "https://openalex.org/W999"}],
)
def test_process_bib_entry_by_title_best_mid_noninteractive(
    m_fetch, m_score, mock_logger
):
    entry = {"ENTRYTYPE": "article", "ID": "Y", "title": "T2"}
    changed, matched = process_bib_entry_by_title(entry, False, False)
    assert changed
    assert matched
    assert entry["openalex"] == "W999"
    assert "[MED] T2 => W999 (score=75.0)" in mock_logger.text


@patch("alexify.core.compute_overall_score", return_value=75)
@patch(
    "alexify.search.fetch_all_candidates_for_entry",
    return_value=[{"id": "https://openalex.org/Wabc"}],
)
@patch("builtins.input", return_value="y")
def test_process_bib_entry_by_title_best_mid_interactive_yes(
    m_input, m_fetch, m_score, mock_logger
):
    entry = {"ENTRYTYPE": "article", "ID": "Z", "title": "T3"}
    changed, matched = process_bib_entry_by_title(entry, True, False)
    assert changed
    assert matched
    assert entry["openalex"] == "Wabc"
    assert "User accepted => Wabc" in mock_logger.text


@patch("alexify.core.compute_overall_score", return_value=75)
@patch(
    "alexify.search.fetch_all_candidates_for_entry",
    return_value=[{"id": "https://openalex.org/W777"}],
)
@patch("builtins.input", return_value="n")
def test_process_bib_entry_by_title_best_mid_interactive_no(m_input, m_fetch, m_score):
    entry = {"ENTRYTYPE": "article", "ID": "Yy", "title": "T4"}
    changed, matched = process_bib_entry_by_title(entry, True, False)
    assert not changed
    assert not matched
    assert "openalex" not in entry


@patch("alexify.core.compute_overall_score", return_value=50)
@patch(
    "alexify.search.fetch_all_candidates_for_entry",
    return_value=[{"id": "https://openalex.org/Wlow"}],
)
def test_process_bib_entry_by_title_below_maybe(m_fetch, m_score):
    entry = {"ENTRYTYPE": "article", "ID": "Zz", "title": "T5"}
    changed, matched = process_bib_entry_by_title(entry)
    assert not changed
    assert not matched
    assert "openalex" not in entry


##########################
# handle_process
##########################


@patch("os.path.exists", return_value=True)
@patch("alexify.core.load_bib_file")
@patch("alexify.core.process_bib_entries_by_dois")
@patch("alexify.core.process_bib_entry_by_title")
@patch("alexify.core.save_bib_file")
def test_handle_process_no_force_already_processed(
    m_save, m_title, m_dois, m_load, m_exists, mock_logger
):
    handle_process("foo.bib", user_interaction=False, force=False, strict=False)
    m_load.assert_not_called()
    assert "Skipping foo.bib, foo-oa.bib already present" in mock_logger.text


@patch("os.path.exists", return_value=False)
@patch("alexify.core.load_bib_file", return_value=None)
def test_handle_process_load_fail(m_load, m_exists, mock_logger):
    handle_process("bad.bib", False, False, False)
    # returns early => no logs about "Failed to load"


@patch("os.path.exists", return_value=False)
@patch("alexify.core.load_bib_file")
@patch("alexify.core.process_bib_entry_by_title")
@patch("alexify.core.save_bib_file")
def test_handle_process_full_flow(m_save, m_title, m_load, m_exists, mock_logger):
    """
    We want final => matched 1 / 2. Unmatched: 1

    We'll do:
      - first entry => process_bib_entries_by_dois => sets openalex => success_count=1
      - second => no match => fail_count=1
    """
    # So we have to patch process_bib_entries_by_dois so it sets openalex on entry[0].

    db = BibDatabase()
    db.entries = [
        {"ENTRYTYPE": "article", "ID": "a", "title": "HasDOI", "doi": "10.abc/xyz"},
        {"ENTRYTYPE": "article", "ID": "b", "title": "NoDOI"},
    ]
    m_load.return_value = db

    # We'll define a side effect that modifies the first entry to have openalex
    def mock_process_bib_entries(es):
        es[0]["openalex"] = "Wdoi"
        return True  # means "modified"

    with patch(
        "alexify.core.process_bib_entries_by_dois", side_effect=mock_process_bib_entries
    ):
        # second => process_bib_entry_by_title => returns (False, False)
        m_title.side_effect = [(False, False)]

        handle_process(
            "realfile.bib", user_interaction=False, force=False, strict=False
        )

    # final log => "Done: realfile.bib => matched 1 / 2. Unmatched: 1"
    txt = mock_logger.text
    assert "Wrote updated file => realfile-oa.bib" in txt
    assert "matched 1 / 2. Unmatched: 1" in txt


##########################
# handle_fetch
##########################


@patch("alexify.core.load_bib_file", return_value=None)
def test_handle_fetch_load_fail(m_load, mock_logger):
    handle_fetch("bad.bib", "/some/out", False)
    # no "Failed to load" from handle_fetch; just returns early


@patch("alexify.core.load_bib_file")
@patch("alexify.core._fetch_and_save_work")
def test_handle_fetch_success(m_fetch, m_load, mock_logger):
    db = BibDatabase()
    db.entries = [
        {"ENTRYTYPE": "article", "ID": "A1", "title": "E1", "openalex": "W123"},
        {"ENTRYTYPE": "article", "ID": "A2", "title": "E2"},
        {"ENTRYTYPE": "article", "ID": "A3", "title": "E3", "openalex": "W999"},
    ]
    m_load.return_value = db
    handle_fetch("somefile.bib", "/outdir", force=False)
    assert m_fetch.call_count == 2
    assert "Fetched 2/3" in mock_logger.text


##########################
# _fetch_and_save_work
##########################


@patch("alexify.search.httpx.Client")
@patch("os.makedirs")
@patch("os.path.exists", return_value=True)
@patch("alexify.core.extract_year_from_filename", return_value=1987)
@patch("builtins.open", new_callable=mock_open)
def test__fetch_and_save_work_success(m_file, m_year, m_exists, m_makedirs, m_client):
    from alexify.core import _fetch_and_save_work

    # Mock the httpx response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "https://openalex.org/W123"}
    
    mock_client_instance = m_client.return_value.__enter__.return_value
    mock_client_instance.get.return_value = mock_response

    out = _fetch_and_save_work("W123", "/path/to/bib", "/outdir", True)
    assert out is True
    m_file.assert_called_once_with("/outdir/1987/W123.json", "w")

    handle = m_file()
    data = ""
    for arg in handle.write.call_args_list:
        data += arg[0][0]
    assert '"id": "https://openalex.org/W123"' in data


@patch("alexify.search.httpx.Client")
@patch("os.makedirs")
@patch("os.path.exists", return_value=False)
@patch("alexify.core.extract_year_from_filename", return_value=None)
@patch("builtins.open", new_callable=mock_open)
def test__fetch_and_save_work_unknown_year(
    m_file, m_year, m_exists, m_makedirs, m_client
):
    from alexify.core import _fetch_and_save_work

    # Mock the httpx response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "https://openalex.org/W999"}
    
    mock_client_instance = m_client.return_value.__enter__.return_value
    mock_client_instance.get.return_value = mock_response
    out = _fetch_and_save_work("W999", "/some/bib", "/outdir2", False)
    assert out is True
    m_makedirs.assert_called_once_with("/outdir2/unknown-year", exist_ok=True)
    m_file.assert_called_once_with("/outdir2/unknown-year/W999.json", "w")


@patch("alexify.search.httpx.Client")
@patch("os.path.exists", return_value=False)
@patch("os.makedirs")
def test__fetch_and_save_work_not_found(
    m_makedirs, m_exists, m_client, mock_logger, tmp_path
):
    from alexify.core import _fetch_and_save_work

    # Mock the httpx response to return None (404)
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = None
    
    mock_client_instance = m_client.return_value.__enter__.return_value
    mock_client_instance.get.return_value = mock_response
    
    # We'll choose a safe outdir => no permission error
    outdir = str(tmp_path / "safeout")

    out = _fetch_and_save_work("Wnope", "/somefile.bib", outdir, True)
    assert out is False
    assert "No Work found for Wnope" in mock_logger.text


##########################
# handle_missing
##########################


@patch("alexify.core.load_bib_file", return_value=None)
def test_handle_missing_no_db(m_load, mock_logger):
    handle_missing("badfile.bib")
    # returns early => no logs


@patch("alexify.core.load_bib_file")
def test_handle_missing_some(m_load, mock_logger):
    db = BibDatabase()
    db.entries = [
        {"ENTRYTYPE": "article", "ID": "xx", "title": "T1", "openalex": "W1"},
        {"ENTRYTYPE": "article", "ID": "yy", "title": "T2"},
        {"ENTRYTYPE": "article", "ID": "zz", "title": "T3", "openalex": "W3"},
    ]
    m_load.return_value = db
    handle_missing("/path/test.bib")
    assert "No openalex => Title: T2" in mock_logger.text
    assert "Total missing from /path/test.bib: 1" in mock_logger.text
