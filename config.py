import os

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bibtex_manager.db')
SCHOLAR_PROXY = None          # e.g. "http://127.0.0.1:7890" or None
SCHOLAR_MIN_DELAY = 10        # seconds between Scholar requests
SCHOLAR_MAX_DELAY = 15
USE_ABBREVIATIONS = True      # default export with abbreviated names
PORT = 5001
DEBUG = True
