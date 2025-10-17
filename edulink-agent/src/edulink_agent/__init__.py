"""Edulink automation package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("edulink-agent")
except PackageNotFoundError:  # pragma: no cover - fallback during local dev
    __version__ = "0.0.0"

__all__ = ["__version__"]
