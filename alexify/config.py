import threading
from typing import Any, Dict, List, Optional


class ConfigManager:
    """Thread-safe configuration manager for OpenAlex API settings."""

    def __init__(self):
        self._config: Dict[str, Any] = {
            "email": None,
            "max_retries": 10,
            "backoff": 0.5,
            "retry_codes": [429, 500, 503],
            "timeout": 30.0,
            "max_concurrent_requests": 20,
        }
        self._lock = threading.Lock()

    def get_config(self) -> Dict[str, Any]:
        """Get a copy of the current configuration."""
        with self._lock:
            return self._config.copy()

    def update_config(
        self,
        email: Optional[str] = None,
        max_retries: Optional[int] = None,
        backoff: Optional[float] = None,
        retry_codes: Optional[List[int]] = None,
        timeout: Optional[float] = None,
        max_concurrent_requests: Optional[int] = None,
    ) -> None:
        """Update configuration parameters."""
        with self._lock:
            if email is not None:
                self._config["email"] = email
            if max_retries is not None:
                self._config["max_retries"] = max_retries
            if backoff is not None:
                self._config["backoff"] = backoff
            if retry_codes is not None:
                self._config["retry_codes"] = retry_codes
            if timeout is not None:
                self._config["timeout"] = timeout
            if max_concurrent_requests is not None:
                self._config["max_concurrent_requests"] = max_concurrent_requests

    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value."""
        with self._lock:
            return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a specific configuration value."""
        with self._lock:
            self._config[key] = value


# Global configuration instance
_config_manager = ConfigManager()


def get_config() -> Dict[str, Any]:
    """Get the current global configuration."""
    return _config_manager.get_config()


def init_config(
    email: Optional[str] = None,
    max_retries: int = 10,
    backoff: float = 0.5,
    retry_codes: List[int] = [429, 500, 503],
    timeout: float = 30.0,
    max_concurrent_requests: int = 20,
) -> None:
    """Initialize global configuration for OpenAlex API usage."""
    _config_manager.update_config(
        email=email,
        max_retries=max_retries,
        backoff=backoff,
        retry_codes=retry_codes,
        timeout=timeout,
        max_concurrent_requests=max_concurrent_requests,
    )


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific configuration value."""
    return _config_manager.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a specific configuration value."""
    _config_manager.set(key, value)
