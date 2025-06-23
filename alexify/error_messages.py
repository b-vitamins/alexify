import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ErrorContext:
    """Provides enhanced error messages with helpful context."""

    @staticmethod
    def format_file_error(
        operation: str,
        file_path: str,
        error: Exception,
        suggestions: Optional[List[str]] = None,
    ) -> str:
        """Format file operation errors with helpful context."""
        base_msg = f"Failed to {operation} file: {file_path}"

        # Add specific error details
        error_details = []
        if isinstance(error, FileNotFoundError):
            error_details.append("File or directory does not exist")
            if suggestions is None:
                suggestions = [
                    "Check if the file path is correct",
                    "Ensure the file exists and is accessible",
                    "Verify parent directories exist",
                ]
        elif isinstance(error, PermissionError):
            error_details.append("Permission denied")
            if suggestions is None:
                suggestions = [
                    "Check file/directory permissions",
                    "Ensure you have read/write access",
                    "Try running with appropriate privileges",
                ]
        elif isinstance(error, (UnicodeDecodeError, UnicodeError)):
            error_details.append(f"Text encoding error: {str(error)}")
            if suggestions is None:
                suggestions = [
                    "File may be in a different encoding (try UTF-8, Latin-1)",
                    "File might be binary, not text",
                    "Check if file is corrupted",
                ]
        elif isinstance(error, OSError):
            error_details.append(f"System error: {str(error)}")
            if suggestions is None:
                suggestions = [
                    "Check available disk space",
                    "Verify file system is not read-only",
                    "Ensure path length is within system limits",
                ]
        else:
            error_details.append(f"Unexpected error: {str(error)}")

        # Build comprehensive message
        message_parts = [base_msg]
        if error_details:
            message_parts.extend([f"  Reason: {detail}" for detail in error_details])

        # Add file system context
        if os.path.exists(file_path):
            try:
                stat = os.stat(file_path)
                message_parts.append(f"  File size: {stat.st_size} bytes")
                message_parts.append(f"  Permissions: {oct(stat.st_mode)[-3:]}")
            except OSError:
                pass
        else:
            parent_dir = os.path.dirname(file_path)
            if parent_dir and os.path.exists(parent_dir):
                message_parts.append(f"  Parent directory exists: {parent_dir}")
            else:
                message_parts.append(f"  Parent directory missing: {parent_dir}")

        if suggestions:
            message_parts.append("  Suggestions:")
            message_parts.extend([f"    - {suggestion}" for suggestion in suggestions])

        return "\n".join(message_parts)

    @staticmethod
    def format_network_error(
        operation: str,
        url: str,
        error: Exception,
        retry_count: int = 0,
        suggestions: Optional[List[str]] = None,
    ) -> str:
        """Format network operation errors with helpful context."""
        base_msg = f"Failed to {operation}: {url}"

        error_details = []
        import httpx

        if isinstance(error, httpx.TimeoutException):
            error_details.append(f"Request timed out after {error}")
            if suggestions is None:
                suggestions = [
                    "Check your internet connection",
                    "Try increasing timeout settings",
                    "OpenAlex servers may be experiencing high load",
                ]
        elif isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            error_details.append(f"HTTP {status_code}: {error.response.reason_phrase}")

            if status_code == 429:
                retry_after = error.response.headers.get("Retry-After", "unknown")
                error_details.append(f"Rate limited, retry after: {retry_after}s")
                if suggestions is None:
                    suggestions = [
                        "Reduce concurrent request settings (--max-requests)",
                        "Add email to requests for polite pool access (--email)",
                        "Wait before retrying",
                    ]
            elif status_code >= 500:
                error_details.append("Server error")
                if suggestions is None:
                    suggestions = [
                        "OpenAlex servers may be experiencing issues",
                        "Try again later",
                        "Check OpenAlex status page",
                    ]
            elif status_code == 404:
                error_details.append("Resource not found")
                if suggestions is None:
                    suggestions = [
                        "Check if the DOI/ID exists in OpenAlex",
                        "Verify the query parameters",
                        "Resource may have been removed",
                    ]
        elif isinstance(error, httpx.ConnectError):
            error_details.append("Connection failed")
            if suggestions is None:
                suggestions = [
                    "Check your internet connection",
                    "Verify DNS resolution is working",
                    "Check if you're behind a firewall/proxy",
                ]
        else:
            error_details.append(f"Network error: {str(error)}")

        message_parts = [base_msg]
        if error_details:
            message_parts.extend([f"  Reason: {detail}" for detail in error_details])

        if retry_count > 0:
            message_parts.append(f"  Retry attempt: {retry_count}")

        if suggestions:
            message_parts.append("  Suggestions:")
            message_parts.extend([f"    - {suggestion}" for suggestion in suggestions])

        return "\n".join(message_parts)

    @staticmethod
    def format_validation_error(
        field_name: str,
        value: Any,
        expected: str,
        suggestions: Optional[List[str]] = None,
    ) -> str:
        """Format validation errors with helpful context."""
        base_msg = f"Invalid {field_name}: {repr(value)}"

        message_parts = [
            base_msg,
            f"  Expected: {expected}",
            f"  Received: {type(value).__name__} with value {repr(value)}",
        ]

        if suggestions:
            message_parts.append("  Suggestions:")
            message_parts.extend([f"    - {suggestion}" for suggestion in suggestions])

        return "\n".join(message_parts)

    @staticmethod
    def format_configuration_error(
        config_key: str,
        error_message: str,
        current_config: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ) -> str:
        """Format configuration errors with helpful context."""
        base_msg = f"Configuration error for '{config_key}': {error_message}"

        message_parts = [base_msg]

        if current_config:
            message_parts.append("  Current configuration:")
            for key, value in current_config.items():
                if key == config_key:
                    message_parts.append(f"    {key}: {repr(value)} ← INVALID")
                else:
                    message_parts.append(f"    {key}: {repr(value)}")

        if suggestions:
            message_parts.append("  Suggestions:")
            message_parts.extend([f"    - {suggestion}" for suggestion in suggestions])

        return "\n".join(message_parts)


def format_startup_error(error: Exception, context: str = "") -> str:
    """Format startup errors with system information."""
    message_parts = [
        "Failed to start alexify application",
        f"Error: {str(error)}",
        f"Error type: {type(error).__name__}",
    ]

    if context:
        message_parts.append(f"Context: {context}")

    # Add system information
    message_parts.extend(
        [
            "",
            "System Information:",
            f"  Python version: {sys.version.split()[0]}",
            f"  Platform: {sys.platform}",
            f"  Working directory: {os.getcwd()}",
        ]
    )

    # Check for common issues
    suggestions = []
    if isinstance(error, ImportError):
        suggestions.extend(
            [
                "Install missing dependencies with: pip install -r requirements.txt",
                "Check if you're in the correct virtual environment",
                "Verify all required packages are installed",
            ]
        )
    elif isinstance(error, PermissionError):
        suggestions.extend(
            [
                "Check file/directory permissions",
                "Ensure you have write access to the working directory",
                "Try running with appropriate privileges",
            ]
        )

    if suggestions:
        message_parts.append("")
        message_parts.append("Suggestions:")
        message_parts.extend([f"  - {suggestion}" for suggestion in suggestions])

    return "\n".join(message_parts)


def log_comprehensive_error(
    logger_instance: logging.Logger,
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    suggestions: Optional[List[str]] = None,
) -> None:
    """Log an error with comprehensive context information."""

    # Build error message with context
    message_parts = [f"Error during {operation}: {str(error)}"]

    if context:
        message_parts.append("Context:")
        for key, value in context.items():
            message_parts.append(f"  {key}: {repr(value)}")

    # Add exception details
    if hasattr(error, "__traceback__") and error.__traceback__:
        import traceback

        tb_lines = traceback.format_tb(error.__traceback__)
        if tb_lines:
            message_parts.append("Traceback (most recent call last):")
            message_parts.extend([f"  {line.rstrip()}" for line in tb_lines])

    if suggestions:
        message_parts.append("Suggestions:")
        message_parts.extend([f"  - {suggestion}" for suggestion in suggestions])

    # Log the comprehensive error
    logger_instance.error("\n".join(message_parts))


# Convenience functions for common error types
def file_operation_failed(operation: str, file_path: str, error: Exception) -> str:
    """Quick error formatting for file operations."""
    return ErrorContext.format_file_error(operation, file_path, error)


def network_operation_failed(
    operation: str, url: str, error: Exception, retry_count: int = 0
) -> str:
    """Quick error formatting for network operations."""
    return ErrorContext.format_network_error(operation, url, error, retry_count)


def validation_failed(field_name: str, value: Any, expected: str) -> str:
    """Quick error formatting for validation failures."""
    return ErrorContext.format_validation_error(field_name, value, expected)
