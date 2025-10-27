import sys
import os

def resource_path(relative_path: str) -> str:
    """Return an absolute path to a resource, working for dev and for PyInstaller onefile.

    When running as a PyInstaller onefile executable, resources are extracted to
    a temporary folder available as sys._MEIPASS. Otherwise return the path
    relative to the current working directory.
    """
    base_path = getattr(sys, '_MEIPASS', None) or os.path.abspath('.')
    return os.path.join(base_path, relative_path)
