"""Bundled data files: the manual corpus, the golden question set and the demo plant state.

In a source checkout they are the repository's corpus/ and eval/ directories. A wheel carries
copies under industrial_monitor/_data/ (force-include in pyproject.toml).
"""

from pathlib import Path

_PACKAGE_DATA = Path(__file__).resolve().parent / "_data"
_CHECKOUT_ROOT = Path(__file__).resolve().parents[2]


def data_path(relative: str) -> Path:
    """Path of a bundled file or directory, independent of the working directory."""
    packaged = _PACKAGE_DATA / relative
    return packaged if packaged.exists() else _CHECKOUT_ROOT / relative
