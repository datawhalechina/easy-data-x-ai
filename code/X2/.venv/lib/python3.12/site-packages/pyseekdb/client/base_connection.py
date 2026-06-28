"""
Base connection interface definition
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseConnection(ABC):
    """
    Abstract base class for connection management.
    Defines unified connection interface for all clients.
    """

    # ==================== Connection Management ====================

    @abstractmethod
    def _ensure_connection(self) -> Any:
        """Ensure connection is established (internal method)"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status"""
        pass

    @abstractmethod
    def _cleanup(self):
        """Internal cleanup method to close connection and release resources"""
        pass

    @abstractmethod
    def _execute(self, sql: str) -> Any:
        """Execute SQL statement (basic functionality)"""
        pass

    @abstractmethod
    def get_raw_connection(self) -> Any:
        """Get raw connection object"""
        pass

    @property
    @abstractmethod
    def mode(self) -> str:
        """Return client mode (e.g., 'SeekdbEmbeddedClient', 'RemoteServerClient')"""
        pass

    # ==================== Context Manager ====================

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support: automatic resource cleanup"""
        self._cleanup()

    def __del__(self):
        """Destructor: ensure connection is closed to prevent resource leaks"""
        try:
            if hasattr(self, "_connection") and self.is_connected():
                self._cleanup()
        except Exception as exc:
            # Ignore all exceptions in destructor
            # Avoid issues during interpreter shutdown
            logger.debug("Failed to cleanup connection in destructor: %s", exc)
