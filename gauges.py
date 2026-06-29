"""Thread-safe Prometheus Gauge management with cleanup."""

import threading
from typing import Dict, Optional
from prometheus_client import Gauge


class ThreadSafeGauges:
    """Manages gauges with thread safety and automatic cleanup."""

    def __init__(self):
        self._gauges: Dict[str, Gauge] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self, name: str, description: Optional[str], label_names: list[str]
    ) -> Gauge:
        """Get existing gauge or create new one with thread safety."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(
                    name, description, labelnames=label_names
                )
            return self._gauges[name]

    def set(self, name: str, labels: list[str], value: float) -> None:
        """Set gauge value with thread safety."""
        with self._lock:
            if name in self._gauges:
                self._gauges[name].labels(labels).set(value)

    def cleanup(self) -> None:
        """Remove all gauges (useful for restart scenarios)."""
        with self._lock:
            self._gauges.clear()


# Global instance for use throughout the exporter
_gauges = ThreadSafeGauges()
