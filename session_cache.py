import os
import tempfile
from pathlib import Path
from typing import Union


class SessionCache:
    """Persistent the session in a temporary file."""

    def __init__(self, host: str, user: str):
        self._cache_file = Path(
            tempfile.gettempdir(), f"pykoplenti-session-{host}-{user}"
        )

    def read_session_id(self) -> Union[str, None]:
        if self._cache_file.is_file():
            with self._cache_file.open("rt") as f:
                return f.readline(256)
        else:
            return None

    def write_session_id(self, id: str):
        f = os.open(self._cache_file, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, mode=0o600)
        try:
            os.write(f, id.encode("ascii"))
        finally:
            os.close(f)

    def remove(self):
        self._cache_file.unlink(missing_ok=True)
