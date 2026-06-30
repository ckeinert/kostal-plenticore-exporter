import os
import tempfile
from pathlib import Path
from typing import Union


class SessionCache:
    """Persistent session cache with atomic writes and cleanup."""

    def __init__(self, host: str, user: str):
        self._cache_dir = Path(tempfile.gettempdir())
        self._cache_file = self._cache_dir / f"pykoplenti-session-{host}-{user}"
        # Ensure cache directory exists with proper permissions
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def read_session_id(self) -> Union[str, None]:
        """Read cached session ID atomically."""
        if self._cache_file.is_file():
            try:
                with open(self._cache_file, "r", encoding="ascii") as f:
                    return f.read(256).strip()
            except (OSError, UnicodeDecodeError):
                # File corrupted or unreadable - clean up and return None
                self.remove()
                return None
        else:
            return None

    def write_session_id(self, id: str) -> None:
        """Write session ID atomically using temp file + rename."""
        fd, tmp_path = tempfile.mkstemp(
            dir=self._cache_dir, prefix=f"pykoplenti-session-{self._cache_file.stem}-."
        )
        tmp_path = Path(tmp_path)
        try:
            os.write(fd, id.encode("ascii"))
            os.fsync(fd)  # Ensure data is written to disk
            os.close(fd)

            # Atomic rename - this also sets permissions correctly
            tmp_path.rename(self._cache_file)
        except (OSError, IOError):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def remove(self) -> None:
        """Remove session cache file."""
        self._cache_file.unlink(missing_ok=True)


def cleanup_stale_sessions() -> int:
    """Clean up stale session files (older than 1 hour). Returns count removed."""
    import time
    from datetime import timedelta

    cutoff = time.time() - timedelta(hours=1).total_seconds()
    removed = 0

    for f in self._cache_dir.glob("pykoplenti-session-*"):
        if f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    return removed
