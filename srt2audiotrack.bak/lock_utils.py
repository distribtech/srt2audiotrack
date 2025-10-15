from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(target: str | Path):
    """Create a ``.lock`` file while working with a target resource.

    Parameters
    ----------
    target:
        Path to the file or directory that is being processed.  A sibling
        ``.lock`` file will be created with ``.lock`` appended to the name.

    Yields
    ------
    Path
        Path to the created lock file.
    """
    lock_path = Path(f"{target}.lock")
    if lock_path.exists():
        raise RuntimeError(f"Resource is locked: {lock_path}")
    lock_path.touch()
    try:
        yield lock_path
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
