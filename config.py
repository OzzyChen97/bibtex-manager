import os
import sys


def _base_path():
    """Return base path — works both in dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _data_path():
    """Writable data directory (next to the executable when frozen)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = _base_path()
DATA_PATH = _data_path()

DATABASE = os.path.join(DATA_PATH, 'bibtex_manager.db')
SCHOLAR_PROXY = None          # e.g. "http://127.0.0.1:7890" or None
SCHOLAR_MIN_DELAY = 10        # seconds between Scholar requests
SCHOLAR_MAX_DELAY = 15
USE_ABBREVIATIONS = True      # default export with abbreviated names
PORT = 5001
DEBUG = False
