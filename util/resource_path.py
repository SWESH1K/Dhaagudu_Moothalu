import sys
import os

from typing import Final

try:
    from core.contracts import IResourceLocator
except Exception:  # avoid circulars during bootstrap
    class IResourceLocator:  # type: ignore
        def path(self, relative: str) -> str: ...

def resource_path(relative_path: str) -> str:
    """Return an absolute path to a resource, working for dev and for PyInstaller onefile.

    When running as a PyInstaller onefile executable, resources are extracted to
    a temporary folder available as sys._MEIPASS. Otherwise return the path
    relative to the current working directory.
    """
    base_path = getattr(sys, '_MEIPASS', None) or os.path.abspath('.')
    return os.path.join(base_path, relative_path)


class ResourceLocator(IResourceLocator):
    """Concrete resource locator used via dependency inversion where helpful."""

    _base: Final[str]

    def __init__(self) -> None:
        self._base = getattr(sys, '_MEIPASS', None) or os.path.abspath('.')

    def path(self, relative: str) -> str:
        return os.path.join(self._base, relative)
