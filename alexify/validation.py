import logging
import os
import re
import sys
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


def validate_email_format(email: str) -> bool:
    """Validate email format using regex pattern."""
    if not email or not isinstance(email, str):
        return False

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_pattern, email.strip()) is not None


def validate_numeric_range(
    value: Any, param_name: str, min_val: int, max_val: int, required_type: type = int
) -> Tuple[bool, str]:
    """
    Validate that a numeric parameter is within acceptable bounds.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, required_type):
        return (
            False,
            f"{param_name} must be of type {required_type.__name__}, got {type(value).__name__}",
        )

    if value < min_val or value > max_val:
        return (
            False,
            f"{param_name} must be between {min_val} and {max_val}, got {value}",
        )

    return True, ""


def validate_path_access(
    path: str,
    param_name: str = "Path",
    must_exist: bool = True,
    must_be_readable: bool = True,
    must_be_writable: bool = False,
    must_be_directory: bool = False,
    must_be_file: bool = False,
) -> Tuple[bool, str]:
    """
    Comprehensive path validation.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path or not isinstance(path, str):
        return False, f"{param_name} must be a non-empty string"

    path = path.strip()
    if not path:
        return False, f"{param_name} cannot be empty"

    if must_exist and not os.path.exists(path):
        return False, f"{param_name} does not exist: {path}"

    if os.path.exists(path):
        if must_be_directory and not os.path.isdir(path):
            return False, f"{param_name} must be a directory: {path}"

        if must_be_file and not os.path.isfile(path):
            return False, f"{param_name} must be a file: {path}"

        if must_be_readable and not os.access(path, os.R_OK):
            return False, f"{param_name} is not readable: {path}"

        if must_be_writable and not os.access(path, os.W_OK):
            return False, f"{param_name} is not writable: {path}"

    return True, ""


def validate_configuration(config: Dict[str, Any]) -> List[str]:
    """
    Validate application configuration comprehensively.

    Args:
        config: Configuration dictionary to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate email if provided
    if config.get("email"):
        if not validate_email_format(config["email"]):
            errors.append(f"Invalid email format: '{config['email']}'")

    # Validate numeric parameters
    numeric_validations = [
        ("max_retries", 1, 100),
        ("timeout", 1, 300),
        ("max_concurrent_requests", 1, 100),
        ("max_requests", 1, 100),
        ("max_files", 1, 50),
        ("max_entries", 1, 200),
        ("batch_size", 1, 1000),
    ]

    for param_name, min_val, max_val in numeric_validations:
        if param_name in config:
            is_valid, error_msg = validate_numeric_range(
                config[param_name], param_name, min_val, max_val
            )
            if not is_valid:
                errors.append(error_msg)

    # Validate float parameters
    float_validations = [
        ("backoff", 0.1, 10.0),
    ]

    for param_name, min_val, max_val in float_validations:
        if param_name in config:
            is_valid, error_msg = validate_numeric_range(
                config[param_name], param_name, min_val, max_val, float
            )
            if not is_valid:
                errors.append(error_msg)

    # Validate retry codes list
    if "retry_codes" in config:
        retry_codes = config["retry_codes"]
        if not isinstance(retry_codes, list):
            errors.append("retry_codes must be a list")
        elif not all(
            isinstance(code, int) and 400 <= code <= 599 for code in retry_codes
        ):
            errors.append("retry_codes must contain valid HTTP status codes (400-599)")

    return errors


def validate_startup_environment() -> List[str]:
    """
    Validate the runtime environment at startup.

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check Python version
    if sys.version_info < (3, 10):
        errors.append(
            f"Python 3.10+ required, found {sys.version_info.major}.{sys.version_info.minor}"
        )

    # Check for required modules
    required_modules = [
        "bibtexparser",
        "fuzzywuzzy",
        "httpx",
        "Levenshtein",
    ]

    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            errors.append(f"Required module not found: {module_name}")

    # Check file system permissions for temporary operations
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(b"test")
    except (OSError, PermissionError) as exc:
        errors.append(f"Cannot create temporary files: {exc}")

    return errors


def validate_cli_arguments(args: Any) -> List[str]:
    """
    Validate CLI arguments after parsing.

    Args:
        args: Parsed command-line arguments

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate email format if provided
    if hasattr(args, "email") and args.email:
        if not validate_email_format(args.email):
            errors.append(f"Invalid email format: '{args.email}'")

    # Validate paths based on command
    if hasattr(args, "path") and args.path:
        is_valid, error_msg = validate_path_access(
            args.path, "Input path", must_exist=True, must_be_readable=True
        )
        if not is_valid:
            errors.append(error_msg)

    # Validate output directory for fetch command
    if hasattr(args, "output_dir") and args.output_dir:
        if hasattr(args, "command") and args.command == "fetch":
            # For fetch command, we may need to create the output directory
            parent_dir = os.path.dirname(os.path.abspath(args.output_dir))
            if parent_dir:
                is_valid, error_msg = validate_path_access(
                    parent_dir,
                    "Output directory parent",
                    must_exist=True,
                    must_be_directory=True,
                    must_be_writable=True,
                )
                if not is_valid:
                    errors.append(error_msg)

    # Validate concurrent processing parameters
    concurrent_params = [
        ("max_requests", 1, 100),
        ("max_files", 1, 50),
        ("max_entries", 1, 200),
        ("batch_size", 1, 1000),
    ]

    for param_name, min_val, max_val in concurrent_params:
        if hasattr(args, param_name):
            value = getattr(args, param_name)
            is_valid, error_msg = validate_numeric_range(
                value, param_name.replace("_", "-"), min_val, max_val
            )
            if not is_valid:
                errors.append(error_msg)

    return errors


def check_system_resources() -> List[str]:
    """
    Check system resources and warn about potential issues.

    Returns:
        List of warning messages
    """
    warnings = []

    # Check available memory (basic check)
    try:
        import psutil

        memory = psutil.virtual_memory()
        if memory.available < 256 * 1024 * 1024:  # Less than 256MB
            warnings.append(
                "Low available memory detected. Consider reducing concurrency."
            )
    except ImportError:
        # psutil not available, skip memory check
        pass

    # Check disk space in temp directory
    try:
        import shutil

        _, _, free_space = shutil.disk_usage(os.path.expanduser("~"))
        if free_space < 100 * 1024 * 1024:  # Less than 100MB
            warnings.append(
                "Low disk space in home directory. Cache operations may fail."
            )
    except OSError:
        pass

    return warnings


def validate_and_report_startup() -> bool:
    """
    Perform comprehensive startup validation and report issues.

    Returns:
        True if validation passes, False if critical errors found
    """
    logger.info("Performing startup validation...")

    # Check environment
    env_errors = validate_startup_environment()
    if env_errors:
        logger.error("Environment validation failed:")
        for error in env_errors:
            logger.error(f"  - {error}")
        return False

    # Check system resources
    warnings = check_system_resources()
    for warning in warnings:
        logger.warning(warning)

    logger.info("Startup validation completed successfully")
    return True
