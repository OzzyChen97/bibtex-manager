"""Base rate-limited HTTP client for external APIs."""
import time
import random
import requests
from functools import wraps


class RateLimitedClient:
    """Base class for rate-limited API clients."""

    def __init__(self, min_delay: float = 1.0, max_delay: float = 2.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BibTeXManager/1.0 (Academic Reference Manager)'
        })

    def _wait(self):
        """Wait appropriate time between requests."""
        elapsed = time.time() - self._last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str, params: dict = None, retries: int = 3, **kwargs) -> requests.Response:
        """Make a rate-limited GET request with retries."""
        last_error = None
        for attempt in range(retries):
            self._wait()
            try:
                resp = self.session.get(url, params=params, timeout=60, **kwargs)
                if resp.status_code == 429:
                    wait_time = (2 ** attempt) * 5 + random.uniform(0, 5)
                    time.sleep(wait_time)
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.ConnectionError as e:
                last_error = e
                time.sleep(2 ** attempt + random.uniform(0, 1))
            except requests.exceptions.Timeout as e:
                last_error = e
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                last_error = e
                time.sleep(2 ** attempt)
        raise requests.exceptions.RequestException(f"Max retries exceeded: {last_error}")
