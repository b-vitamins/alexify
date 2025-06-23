import functools
import logging
import threading
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass


class FileOperationTimeout:
    """Context manager for file operations with timeout."""

    def __init__(self, timeout_seconds: float, operation_name: str = "File operation"):
        self.timeout_seconds = timeout_seconds
        self.operation_name = operation_name
        self.timer = None
        self.timed_out = False

    def __enter__(self):
        def timeout_handler():
            self.timed_out = True
            logger.warning(
                f"{self.operation_name} timed out after {self.timeout_seconds}s"
            )

        self.timer = threading.Timer(self.timeout_seconds, timeout_handler)
        self.timer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.timer:
            self.timer.cancel()

        if self.timed_out:
            raise TimeoutError(
                f"{self.operation_name} timed out after {self.timeout_seconds}s"
            )


def with_timeout(timeout_seconds: float, operation_name: Optional[str] = None):
    """
    Decorator to add timeout to function calls.

    Args:
        timeout_seconds: Maximum time to allow for function execution
        operation_name: Description of the operation for error messages
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__name__}"

            result = [None]
            exception = [None]
            finished = threading.Event()

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
                finally:
                    finished.set()

            thread = threading.Thread(target=target, daemon=True)
            thread.start()

            if finished.wait(timeout_seconds):
                if exception[0]:
                    raise exception[0]
                return result[0]
            else:
                logger.warning(f"{name} timed out after {timeout_seconds}s")
                raise TimeoutError(f"{name} timed out after {timeout_seconds}s")

        return wrapper

    return decorator


def safe_file_read(
    file_path: str, timeout_seconds: float = 30.0, encoding: str = "utf-8"
) -> Optional[str]:
    """
    Safely read a file with timeout protection.

    Args:
        file_path: Path to the file to read
        timeout_seconds: Maximum time to wait for file read
        encoding: File encoding

    Returns:
        File contents or None if operation fails/times out
    """

    @with_timeout(timeout_seconds, f"Reading file {file_path}")
    def _read_file():
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()

    try:
        return _read_file()
    except (OSError, UnicodeDecodeError, TimeoutError) as exc:
        logger.error(f"Failed to read file {file_path}: {exc}")
        return None


def safe_file_write(
    file_path: str, content: str, timeout_seconds: float = 30.0, encoding: str = "utf-8"
) -> bool:
    """
    Safely write to a file with timeout protection.

    Args:
        file_path: Path to the file to write
        content: Content to write
        timeout_seconds: Maximum time to wait for file write
        encoding: File encoding

    Returns:
        True if successful, False otherwise
    """

    @with_timeout(timeout_seconds, f"Writing file {file_path}")
    def _write_file():
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return True

    try:
        return _write_file()
    except (OSError, UnicodeEncodeError, TimeoutError) as exc:
        logger.error(f"Failed to write file {file_path}: {exc}")
        return False


def safe_directory_creation(dir_path: str, timeout_seconds: float = 10.0) -> bool:
    """
    Safely create directory with timeout protection.

    Args:
        dir_path: Path to the directory to create
        timeout_seconds: Maximum time to wait for directory creation

    Returns:
        True if successful, False otherwise
    """
    import os

    @with_timeout(timeout_seconds, f"Creating directory {dir_path}")
    def _create_dir():
        os.makedirs(dir_path, exist_ok=True)
        return True

    try:
        return _create_dir()
    except (OSError, TimeoutError) as exc:
        logger.error(f"Failed to create directory {dir_path}: {exc}")
        return False


class ProgressiveTimeout:
    """
    Progressive timeout handler that increases timeout for subsequent operations.
    Useful for operations that may get slower as they process more data.
    """

    def __init__(
        self,
        base_timeout: float = 10.0,
        max_timeout: float = 60.0,
        increment: float = 5.0,
    ):
        self.base_timeout = base_timeout
        self.max_timeout = max_timeout
        self.increment = increment
        self.current_timeout = base_timeout
        self.operation_count = 0

    def get_current_timeout(self) -> float:
        """Get the current timeout value."""
        return self.current_timeout

    def next_operation(self) -> float:
        """Prepare for next operation and return timeout to use."""
        self.operation_count += 1

        # Increase timeout for subsequent operations
        if self.operation_count > 1:
            self.current_timeout = min(
                self.current_timeout + self.increment, self.max_timeout
            )

        return self.current_timeout

    def reset(self):
        """Reset timeout to base value."""
        self.current_timeout = self.base_timeout
        self.operation_count = 0


# Global progressive timeout instance for file operations
_global_file_timeout = ProgressiveTimeout(
    base_timeout=10.0, max_timeout=60.0, increment=5.0
)


def get_adaptive_file_timeout() -> float:
    """Get adaptive timeout for file operations that increases with usage."""
    return _global_file_timeout.next_operation()


def reset_adaptive_timeout():
    """Reset adaptive timeout to base value."""
    _global_file_timeout.reset()
