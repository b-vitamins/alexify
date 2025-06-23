import functools
import logging
from typing import Any, Callable, List, Optional, TypeVar, Union

import httpx

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


def handle_http_errors(
    return_value: Any = None,
    log_errors: bool = True,
    reraise_on: Optional[List[type]] = None,
) -> Callable[[F], F]:
    """
    Decorator to handle HTTP errors consistently across the codebase.

    Args:
        return_value: Value to return on error (default: None)
        log_errors: Whether to log errors (default: True)
        reraise_on: List of exception types to re-raise instead of handling
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"HTTP error in {func.__name__}: {exc}")
                return return_value
            except Exception as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"Unexpected error in {func.__name__}: {exc}")
                return return_value

        return wrapper

    return decorator


def handle_async_http_errors(
    return_value: Any = None,
    log_errors: bool = True,
    reraise_on: Optional[List[type]] = None,
) -> Callable[[F], F]:
    """
    Async version of handle_http_errors decorator.

    Args:
        return_value: Value to return on error (default: None)
        log_errors: Whether to log errors (default: True)
        reraise_on: List of exception types to re-raise instead of handling
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"HTTP error in {func.__name__}: {exc}")
                return return_value
            except Exception as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"Unexpected error in {func.__name__}: {exc}")
                return return_value

        return wrapper

    return decorator


def handle_file_errors(
    return_value: Any = None,
    log_errors: bool = True,
    reraise_on: Optional[List[type]] = None,
) -> Callable[[F], F]:
    """
    Decorator to handle file operation errors consistently.

    Args:
        return_value: Value to return on error (default: None)
        log_errors: Whether to log errors (default: True)
        reraise_on: List of exception types to re-raise instead of handling
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (FileNotFoundError, PermissionError, OSError) as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"File operation error in {func.__name__}: {exc}")
                return return_value
            except (UnicodeDecodeError, UnicodeError) as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"Unicode error in {func.__name__}: {exc}")
                return return_value
            except Exception as exc:
                if reraise_on and type(exc) in reraise_on:
                    raise
                if log_errors:
                    logger.error(f"Unexpected error in {func.__name__}: {exc}")
                return return_value

        return wrapper

    return decorator


def validate_input(
    check_none: bool = True,
    check_empty: bool = True,
    check_type: Optional[Union[type, tuple]] = None,
    return_value: Any = None,
) -> Callable[[F], F]:
    """
    Decorator to validate function inputs consistently.

    Args:
        check_none: Whether to check for None values (default: True)
        check_empty: Whether to check for empty strings/collections (default: True)
        check_type: Type or tuple of types to check against
        return_value: Value to return on validation failure (default: None)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check the first argument (common pattern)
            if args:
                first_arg = args[0]

                if check_none and first_arg is None:
                    logger.warning(f"{func.__name__} called with None argument")
                    return return_value

                if (
                    check_empty
                    and hasattr(first_arg, "__len__")
                    and len(first_arg) == 0
                ):
                    logger.warning(f"{func.__name__} called with empty argument")
                    return return_value

                if check_type and not isinstance(first_arg, check_type):
                    logger.warning(
                        f"{func.__name__} called with wrong type: {type(first_arg)}"
                    )
                    return return_value

            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_performance(log_level: int = logging.DEBUG) -> Callable[[F], F]:
    """
    Decorator to log function execution time.

    Args:
        log_level: Logging level to use (default: DEBUG)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.log(
                    log_level, f"{func.__name__} executed in {execution_time:.3f}s"
                )
                return result
            except Exception as exc:
                execution_time = time.time() - start_time
                logger.log(
                    log_level,
                    f"{func.__name__} failed after {execution_time:.3f}s: {exc}",
                )
                raise

        return wrapper

    return decorator


def log_async_performance(log_level: int = logging.DEBUG) -> Callable[[F], F]:
    """
    Async version of log_performance decorator.

    Args:
        log_level: Logging level to use (default: DEBUG)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import time

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.log(
                    log_level, f"{func.__name__} executed in {execution_time:.3f}s"
                )
                return result
            except Exception as exc:
                execution_time = time.time() - start_time
                logger.log(
                    log_level,
                    f"{func.__name__} failed after {execution_time:.3f}s: {exc}",
                )
                raise

        return wrapper

    return decorator
