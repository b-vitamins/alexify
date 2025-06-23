import asyncio
import logging
import signal
import sys
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handles graceful shutdown of concurrent operations."""

    def __init__(self):
        self.shutdown_requested = threading.Event()
        self.active_operations = set()
        self.operation_lock = threading.Lock()
        self._signal_handlers_installed = False
        self._original_handlers = {}

    def install_signal_handlers(self):
        """Install signal handlers for graceful shutdown."""
        if self._signal_handlers_installed:
            return

        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            self.request_shutdown()

        # Store original handlers
        try:
            self._original_handlers[signal.SIGINT] = signal.signal(
                signal.SIGINT, signal_handler
            )
            self._original_handlers[signal.SIGTERM] = signal.signal(
                signal.SIGTERM, signal_handler
            )
            self._signal_handlers_installed = True
            logger.debug("Signal handlers installed for graceful shutdown")
        except (OSError, ValueError) as exc:
            logger.warning(f"Could not install signal handlers: {exc}")

    def restore_signal_handlers(self):
        """Restore original signal handlers."""
        if not self._signal_handlers_installed:
            return

        try:
            for sig, handler in self._original_handlers.items():
                signal.signal(sig, handler)
            self._signal_handlers_installed = False
            logger.debug("Original signal handlers restored")
        except (OSError, ValueError) as exc:
            logger.warning(f"Could not restore signal handlers: {exc}")

    def request_shutdown(self):
        """Request graceful shutdown of all operations."""
        self.shutdown_requested.set()

        with self.operation_lock:
            active_count = len(self.active_operations)

        if active_count > 0:
            logger.info(f"Waiting for {active_count} active operations to complete...")
        else:
            logger.info("No active operations, shutdown can proceed immediately")

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_requested.is_set()

    def register_operation(self, operation_id: str):
        """Register an active operation."""
        with self.operation_lock:
            self.active_operations.add(operation_id)
        logger.debug(f"Registered operation: {operation_id}")

    def unregister_operation(self, operation_id: str):
        """Unregister a completed operation."""
        with self.operation_lock:
            self.active_operations.discard(operation_id)
        logger.debug(f"Unregistered operation: {operation_id}")

    def wait_for_operations(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all active operations to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all operations completed, False if timeout occurred
        """
        start_time = time.time()

        while True:
            with self.operation_lock:
                if not self.active_operations:
                    logger.info("All operations completed successfully")
                    return True

                active_count = len(self.active_operations)

            if timeout and (time.time() - start_time) >= timeout:
                logger.warning(
                    f"Timeout reached, {active_count} operations still active"
                )
                return False

            time.sleep(0.1)  # Short sleep to avoid busy waiting

    def force_shutdown(self):
        """Force immediate shutdown without waiting for operations."""
        with self.operation_lock:
            active_count = len(self.active_operations)
            self.active_operations.clear()

        if active_count > 0:
            logger.warning(
                f"Force shutdown: abandoned {active_count} active operations"
            )

        self.shutdown_requested.set()


# Global shutdown manager instance
_shutdown_manager = GracefulShutdown()


def get_shutdown_manager() -> GracefulShutdown:
    """Get the global shutdown manager instance."""
    return _shutdown_manager


def install_shutdown_handlers():
    """Install signal handlers for graceful shutdown."""
    _shutdown_manager.install_signal_handlers()


def request_shutdown():
    """Request graceful shutdown."""
    _shutdown_manager.request_shutdown()


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_manager.is_shutdown_requested()


class OperationContext:
    """Context manager for tracking operations during shutdown."""

    def __init__(
        self, operation_id: str, shutdown_manager: Optional[GracefulShutdown] = None
    ):
        self.operation_id = operation_id
        self.shutdown_manager = shutdown_manager or _shutdown_manager

    def __enter__(self):
        self.shutdown_manager.register_operation(self.operation_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown_manager.unregister_operation(self.operation_id)

    def check_shutdown(self):
        """Check if shutdown was requested and raise exception if so."""
        if self.shutdown_manager.is_shutdown_requested():
            raise KeyboardInterrupt("Shutdown requested")


def with_shutdown_protection(operation_name: str):
    """Decorator to add shutdown protection to functions."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with OperationContext(f"{operation_name}_{id(threading.current_thread())}"):
                return func(*args, **kwargs)

        return wrapper

    return decorator


async def async_with_shutdown_protection(operation_name: str):
    """Async decorator to add shutdown protection to async functions."""

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            operation_id = f"{operation_name}_{id(asyncio.current_task())}"
            with OperationContext(operation_id):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def wait_for_shutdown(timeout: float = 30.0) -> bool:
    """
    Wait for graceful shutdown to complete.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if shutdown completed gracefully, False if forced
    """
    logger.info("Initiating graceful shutdown...")

    if _shutdown_manager.wait_for_operations(timeout):
        logger.info("Graceful shutdown completed")
        return True
    else:
        logger.warning("Graceful shutdown timeout, forcing shutdown")
        _shutdown_manager.force_shutdown()
        return False


def cleanup_and_exit(exit_code: int = 0):
    """Perform cleanup and exit the application."""
    logger.info("Performing final cleanup...")

    # Restore signal handlers
    _shutdown_manager.restore_signal_handlers()

    # Final log message
    logger.info(f"Application shutdown complete (exit code: {exit_code})")

    # Exit
    sys.exit(exit_code)
