import logging
import sys
from unittest.mock import patch

import pytest
from alexify.cli import main as cli_main


@pytest.fixture
def mock_logger(caplog):
    """
    Capture logs from the top-level logger in cli.py.
    By default, cli sets basicConfig => level=INFO, so we can see logs.
    """
    caplog.set_level(logging.INFO)
    return caplog


#########################
# Test pyalex configuration
#########################


@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.find_bib_files", return_value=[])
@patch("alexify.cli.sort_bib_files_by_year", return_value=[])
@patch("alexify.cli.init_openalex_config")
def test_cli_email_passed(
    mock_init, mock_sort, mock_find, mock_validate_path, monkeypatch
):
    """
    Confirm we call init_pyalex_config with the passed email.
    """
    monkeypatch.setattr(
        sys,
        "argv",
        ["alexify", "--email", "tester@example.com", "process", "/some/path"],
    )
    cli_main()
    # We expect init_pyalex_config to be called with the email
    mock_init.assert_called_once_with(email="tester@example.com")


@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.find_bib_files", return_value=[])
@patch("alexify.cli.sort_bib_files_by_year", return_value=[])
@patch("alexify.cli.init_openalex_config")
def test_cli_no_email(mock_init, mock_sort, mock_find, mock_validate_path, monkeypatch):
    """
    Confirm we call init_openalex_config with email=None when no --email arg is provided.
    """
    monkeypatch.setattr(sys, "argv", ["alexify", "process", "/some/path"])
    cli_main()
    mock_init.assert_called_once_with(email=None)


#########################
# Test subcommands: process, fetch, missing
#########################


@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.init_openalex_config")
@patch("alexify.cli.handle_process")
@patch("alexify.cli.find_bib_files")
@patch("alexify.cli.sort_bib_files_by_year")
def test_cli_process_happy(
    mock_sort,
    mock_find,
    mock_handle_process,
    mock_init,
    mock_validate_path,
    monkeypatch,
    mock_logger,
):
    """
    Command:
      alexify process /some/path --interactive --force --strict
    We expect:
      - init_pyalex_config called
      - find_bib_files(mode='original') => list of files
      - sort_bib_files_by_year => sorted
      - handle_process called for each file
    """
    # We'll mock sys.argv
    monkeypatch.setattr(
        sys,
        "argv",
        ["alexify", "process", "/some/path", "--interactive", "--force", "--strict"],
    )

    mock_find.return_value = ["/file1.bib", "/file2.bib"]
    mock_sort.return_value = ["/file2.bib", "/file1.bib"]

    # Run the cli
    cli_main()

    # Checks
    mock_init.assert_called_once()
    mock_find.assert_called_once_with("/some/path", mode="original")
    mock_sort.assert_called_once_with(["/file1.bib", "/file2.bib"])

    # handle_process calls for each file
    # handle_process(bf, user_interaction, force, strict)
    assert mock_handle_process.call_count == 2
    mock_handle_process.assert_any_call("/file2.bib", True, True, True)
    mock_handle_process.assert_any_call("/file1.bib", True, True, True)


@patch("os.makedirs")
@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.init_openalex_config")
@patch("alexify.cli.handle_fetch")
@patch("alexify.cli.find_bib_files")
@patch("alexify.cli.sort_bib_files_by_year")
def test_cli_fetch_happy(
    mock_sort,
    mock_find,
    mock_handle_fetch,
    mock_init,
    mock_validate_path,
    mock_makedirs,
    monkeypatch,
):
    """
    Command:
      alexify fetch /some/processed --output-dir /outdir --force
    """
    monkeypatch.setattr(
        sys,
        "argv",
        ["alexify", "fetch", "/some/processed", "--output-dir", "/outdir", "--force"],
    )

    mock_find.return_value = ["/file1-oa.bib", "/file2-oa.bib"]
    mock_sort.return_value = ["/file2-oa.bib", "/file1-oa.bib"]

    cli_main()

    mock_init.assert_called_once()
    mock_find.assert_called_once_with("/some/processed", mode="processed")
    mock_sort.assert_called_once_with(["/file1-oa.bib", "/file2-oa.bib"])

    # handle_fetch calls => handle_fetch(file, outdir, force)
    assert mock_handle_fetch.call_count == 2
    mock_handle_fetch.assert_any_call("/file2-oa.bib", "/outdir", True)
    mock_handle_fetch.assert_any_call("/file1-oa.bib", "/outdir", True)


@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.init_openalex_config")
@patch("alexify.cli.handle_missing")
@patch("alexify.cli.find_bib_files")
@patch("alexify.cli.sort_bib_files_by_year")
def test_cli_missing_happy(
    mock_sort,
    mock_find,
    mock_handle_missing,
    mock_init,
    mock_validate_path,
    monkeypatch,
):
    """
    Command:
      alexify missing /some/processed
    """
    monkeypatch.setattr(sys, "argv", ["alexify", "missing", "/some/processed"])
    mock_find.return_value = ["/f1-oa.bib"]
    mock_sort.return_value = ["/f1-oa.bib"]

    cli_main()

    mock_init.assert_called_once()
    mock_find.assert_called_once_with("/some/processed", mode="processed")
    mock_sort.assert_called_once_with(["/f1-oa.bib"])

    mock_handle_missing.assert_called_once_with("/f1-oa.bib")


#########################
# Test required arguments
#########################


def test_cli_fetch_missing_output_dir(monkeypatch, caplog):
    """
    If we run: alexify fetch /somepath, but no --output-dir => argparse error
    We'll capture SystemExit + usage message in logs
    """
    monkeypatch.setattr(sys, "argv", ["alexify", "fetch", "/some/processed"])
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code != 0
    # We can also check caplog or capsys for usage string
    # But typically we only check we got SystemExit


def test_cli_no_command(monkeypatch):
    """
    Running 'alexify' with no subcommand => SystemExit + usage
    """
    monkeypatch.setattr(sys, "argv", ["alexify"])
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code != 0


def test_cli_unknown_command(monkeypatch):
    """
    Running 'alexify unknownstuff' => SystemExit with error about unknown subcommand
    """
    monkeypatch.setattr(sys, "argv", ["alexify", "unknownstuff"])
    # argparse will error => SystemExit
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code != 0
    # we might check the error message or usage, but this ensures it fails


#########################
# Test logs
#########################


@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.init_openalex_config")
@patch("alexify.cli.find_bib_files", return_value=[])
def test_cli_process_no_files_found(
    mock_validate_path, mock_find, mock_init, monkeypatch, caplog
):
    """
    If find_bib_files returns empty => handle_process never called => just logs
    """

    monkeypatch.setattr(sys, "argv", ["alexify", "process", "/empty"])
    with patch("alexify.cli.handle_process") as mock_hp:
        cli_main()
        mock_hp.assert_not_called()
    # should see no error, just no calls
    # we can confirm logs mention "Processing"? Or might be empty?
    # It's not strictly necessary, but you can check caplog if you like.
    # We'll just confirm no error was raised.


@patch("alexify.cli.validate_path_access")
@patch("alexify.cli.init_openalex_config")
@patch("alexify.cli.find_bib_files", return_value=["/somebib.bib"])
@patch("alexify.cli.sort_bib_files_by_year", return_value=["/somebib.bib"])
def test_cli_process_logs(
    mock_validate_path, mock_sort, mock_find, mock_init, monkeypatch, caplog
):
    """
    Check that with a single .bib, we call handle_process once and log at INFO level.
    """

    monkeypatch.setattr(sys, "argv", ["alexify", "process", "/somepath"])
    with patch("alexify.cli.handle_process") as mock_hp:
        cli_main()
        mock_hp.assert_called_once()
    # We can confirm logs if we want
    # e.g. "Processing /somebib.bib, # entries: N"
    # But that's in the handle_process logic, not cli. The cli itself only logs basic info.
    # Let's just check no errors
    assert "ERROR" not in caplog.text
