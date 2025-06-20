import pytest
from fuzzywuzzy import fuzz


def test_levenshtein_speedup_available():
    """
    Verify that python-Levenshtein is available for performance speedup.
    When python-Levenshtein is installed, fuzzywuzzy will use the C extension
    which provides significant performance improvements.
    """
    # Check if the speedup warning would be shown
    # This is done by checking if StringMatcher is available
    try:
        import fuzzywuzzy.StringMatcher  # noqa: F401

        # If we can import StringMatcher, python-Levenshtein is available
        assert True, "python-Levenshtein is available for speedup"
    except ImportError:
        # If import fails, the speedup is not available
        pytest.fail(
            "python-Levenshtein is not installed. "
            "Fuzzy matching will be significantly slower. "
            "Install with: pip install python-Levenshtein"
        )


def test_fuzzy_matching_performance():
    """
    Basic performance check to ensure fuzzy matching completes in reasonable time.
    With python-Levenshtein, this should be very fast.
    """
    import time

    # Create test strings
    str1 = "The quick brown fox jumps over the lazy dog" * 10
    str2 = "The quick brown fox jumped over the lazy dogs" * 10

    # Time the fuzzy matching
    start = time.time()

    # Run multiple iterations to get measurable time
    for _ in range(100):
        _ = fuzz.ratio(str1, str2)
        _ = fuzz.token_sort_ratio(str1, str2)
        _ = fuzz.partial_ratio(str1, str2)

    elapsed = time.time() - start

    # With python-Levenshtein, this should complete in well under 1 second
    # Without it, it might take several seconds
    assert (
        elapsed < 1.0
    ), f"Fuzzy matching took {elapsed:.2f}s - performance issue detected"
