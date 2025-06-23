import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
    suppress_external: bool = True,
) -> None:
    """
    Configure centralized logging for the alexify application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom log format string
        date_format: Custom date format string
        suppress_external: Whether to suppress verbose external library logs
    """
    if format_string is None:
        format_string = "%(asctime)s - %(levelname)s - %(message)s"

    if date_format is None:
        date_format = "%Y-%m-%d %H:%M:%S"

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=format_string,
        datefmt=date_format,
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )

    if suppress_external:
        # Silence verbose external library logs
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        # Only show errors and warnings from urllib3
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with consistent naming convention.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_debug_mode(enabled: bool = True) -> None:
    """
    Enable or disable debug mode for all alexify loggers.

    Args:
        enabled: Whether to enable debug logging
    """
    level = logging.DEBUG if enabled else logging.INFO

    # Set level for all alexify loggers
    for logger_name in [
        "alexify.core",
        "alexify.core_concurrent",
        "alexify.search",
        "alexify.search_async",
        "alexify.matching",
        "alexify.cli",
        "alexify.http_client",
        "alexify.config",
        "alexify.query_builder",
        "alexify.error_handling",
    ]:
        logging.getLogger(logger_name).setLevel(level)


def suppress_library_logs() -> None:
    """Suppress verbose logs from external libraries."""
    external_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "requests",
        "asyncio",
    ]

    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def setup_performance_logging(enabled: bool = False) -> None:
    """
    Enable performance logging for monitoring execution times.

    Args:
        enabled: Whether to enable performance logging
    """
    if enabled:
        # Add performance logger configuration
        perf_logger = logging.getLogger("alexify.performance")
        perf_logger.setLevel(logging.DEBUG)

        # Create handler for performance logs if it doesn't exist
        if not perf_logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - PERF - %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S.%f",
            )
            handler.setFormatter(formatter)
            perf_logger.addHandler(handler)
            perf_logger.propagate = False  # Don't propagate to root logger


# Default logging setup for when module is imported
def configure_default_logging() -> None:
    """Configure default logging when the module is imported."""
    setup_logging(level="INFO", suppress_external=True)


# Auto-configure logging when module is imported
if not logging.getLogger().handlers:
    configure_default_logging()
