"""Privacy-safe connection diagnostics for Casambi Bluetooth."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import time
from typing import Any, Final

DEFAULT_LOG_INTERVAL_SECONDS: Final = 300.0


class ConnectionDiagnostics:
    """Track aggregate connection health without network identifiers."""

    def __init__(
        self, log_interval_seconds: float = DEFAULT_LOG_INTERVAL_SECONDS
    ) -> None:
        """Initialize empty diagnostics."""
        self.state = "disconnected"
        self.disconnects = 0
        self.reconnect_attempts = 0
        self.reconnect_successes = 0
        self.reconnect_failures = 0
        self.reconnect_skips = 0
        self.last_reconnect_result: str | None = None
        self.unsupported_control_modes: dict[str, int] = {}
        self._log_interval_seconds = log_interval_seconds
        self._last_log_at: dict[str, float] = {}

    def record_connecting(self) -> None:
        """Record an active initial connection attempt."""
        self.state = "connecting"

    def record_connected(self) -> None:
        """Record a connected network."""
        self.state = "connected"

    def record_disconnected(self) -> None:
        """Record a connection that is no longer available."""
        self.state = "disconnected"

    def record_disconnect(self) -> None:
        """Count an unexpected disconnect callback."""
        self.disconnects += 1
        self.record_disconnected()

    def record_reconnect_attempt(self) -> None:
        """Count a reconnect attempt."""
        self.reconnect_attempts += 1
        self.state = "reconnecting"

    def record_reconnect_success(self) -> None:
        """Count a successful reconnect."""
        self.reconnect_successes += 1
        self.last_reconnect_result = "success"
        self.record_connected()

    def record_reconnect_failure(self) -> None:
        """Count a failed reconnect."""
        self.reconnect_failures += 1
        self.last_reconnect_result = "failure"
        self.record_disconnected()

    def record_reconnect_skip(self, reason: str) -> None:
        """Count a reconnect that was deliberately skipped."""
        self.reconnect_skips += 1
        self.last_reconnect_result = f"skipped_{reason}"

    def set_unsupported_control_modes(self, modes: Iterable[str]) -> None:
        """Replace the aggregate unsupported-control inventory."""
        self.unsupported_control_modes = dict(sorted(Counter(modes).items()))

    def should_log(self, event: str, *, now: float | None = None) -> bool:
        """Return whether an event may be logged under the local rate limit."""
        event_time = time.monotonic() if now is None else now
        last_log_at = self._last_log_at.get(event)
        if (
            last_log_at is not None
            and event_time - last_log_at < self._log_interval_seconds
        ):
            return False
        self._last_log_at[event] = event_time
        return True

    def snapshot(self) -> dict[str, Any]:
        """Return diagnostics data safe for Home Assistant issue reports."""
        return {
            "connection": {
                "state": self.state,
                "disconnects": self.disconnects,
                "reconnect_attempts": self.reconnect_attempts,
                "reconnect_successes": self.reconnect_successes,
                "reconnect_failures": self.reconnect_failures,
                "reconnect_skips": self.reconnect_skips,
                "last_reconnect_result": self.last_reconnect_result,
            },
            "unsupported_control_modes": self.unsupported_control_modes.copy(),
        }


def build_diagnostics_payload(
    connection: ConnectionDiagnostics,
    *,
    integration_version: str,
    library_version: str,
    cache_version: int,
    unit_count: int,
    group_count: int,
    scene_count: int,
) -> dict[str, Any]:
    """Build an aggregate payload without config-entry data or identifiers."""
    return {
        "versions": {
            "integration": integration_version,
            "library": library_version,
            "cache": cache_version,
        },
        **connection.snapshot(),
        "inventory": {
            "units": unit_count,
            "groups": group_count,
            "scenes": scene_count,
        },
    }
