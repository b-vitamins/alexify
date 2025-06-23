import logging
import sys
import time
from typing import Optional


class ProgressIndicator:
    """Simple progress indicator for command-line operations."""

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        show_rate: bool = True,
        show_eta: bool = True,
        width: int = 50,
    ):
        self.total = total
        self.description = description
        self.show_rate = show_rate
        self.show_eta = show_eta
        self.width = width
        self.current = 0
        self.start_time = time.time()
        self.last_update = 0
        self.logger = logging.getLogger(__name__)

    def update(self, increment: int = 1) -> None:
        """Update progress by the given increment."""
        self.current = min(self.current + increment, self.total)
        current_time = time.time()

        # Only update display every 0.1 seconds to avoid spam
        if current_time - self.last_update > 0.1 or self.current >= self.total:
            self._display_progress()
            self.last_update = current_time

    def _display_progress(self) -> None:
        """Display the current progress."""
        if self.total == 0:
            return

        percentage = (self.current / self.total) * 100
        filled_width = int(self.width * self.current / self.total)
        bar = "█" * filled_width + "░" * (self.width - filled_width)

        # Calculate rate and ETA
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and self.current > 0:
            rate = self.current / elapsed_time
            if rate > 0 and self.current < self.total:
                eta_seconds = (self.total - self.current) / rate
                eta_str = (
                    f" ETA: {self._format_time(eta_seconds)}" if self.show_eta else ""
                )
            else:
                eta_str = ""
            rate_str = f" ({rate:.1f}/s)" if self.show_rate else ""
        else:
            rate_str = ""
            eta_str = ""

        # Build progress message
        message = f"{self.description}: {percentage:5.1f}% |{bar}| {self.current}/{self.total}{rate_str}{eta_str}"

        # Use carriage return to overwrite previous line
        if self.current < self.total:
            print(f"\r{message}", end="", flush=True)
        else:
            # Final update - use newline
            print(f"\r{message}")

    def _format_time(self, seconds: float) -> str:
        """Format time in human-readable format."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds // 60:.0f}m {seconds % 60:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"

    def finish(self) -> None:
        """Mark progress as complete."""
        self.current = self.total
        self._display_progress()


class LoggingProgressIndicator:
    """Progress indicator that uses logging instead of terminal output."""

    def __init__(
        self, total: int, description: str = "Processing", update_interval: int = 10
    ):
        self.total = total
        self.description = description
        self.update_interval = update_interval
        self.current = 0
        self.start_time = time.time()
        self.logger = logging.getLogger(__name__)

    def update(self, increment: int = 1) -> None:
        """Update progress by the given increment."""
        self.current = min(self.current + increment, self.total)

        # Log progress at intervals
        if (self.current % self.update_interval == 0) or (self.current >= self.total):
            self._log_progress()

    def _log_progress(self) -> None:
        """Log the current progress."""
        if self.total == 0:
            return

        percentage = (self.current / self.total) * 100
        elapsed_time = time.time() - self.start_time

        if elapsed_time > 0 and self.current > 0:
            rate = self.current / elapsed_time
            rate_str = f" ({rate:.1f}/s)"
        else:
            rate_str = ""

        self.logger.info(
            f"{self.description}: {self.current}/{self.total} ({percentage:.1f}%){rate_str}"
        )

    def finish(self) -> None:
        """Mark progress as complete."""
        self.current = self.total
        elapsed_time = time.time() - self.start_time
        rate = self.current / elapsed_time if elapsed_time > 0 else 0

        self.logger.info(
            f"{self.description} complete: {self.total} items in {elapsed_time:.2f}s "
            f"({rate:.1f}/s)"
        )


def create_progress_indicator(
    total: int, description: str = "Processing", use_logging: bool = False, **kwargs
) -> Optional[ProgressIndicator]:
    """
    Factory function to create appropriate progress indicator.

    Args:
        total: Total number of items to process
        description: Description of the operation
        use_logging: Whether to use logging instead of terminal output
        **kwargs: Additional arguments for progress indicator

    Returns:
        Progress indicator instance or None if total is 0
    """
    if total == 0:
        return None

    if use_logging or not sys.stdout.isatty():
        return LoggingProgressIndicator(total, description, **kwargs)
    else:
        return ProgressIndicator(total, description, **kwargs)
