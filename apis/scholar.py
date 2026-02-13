"""Google Scholar BibTeX fetcher using scholarly library."""
import time
import random
import logging
from scholarly import scholarly, ProxyGenerator

logger = logging.getLogger(__name__)


class ScholarClient:
    """Fetch BibTeX entries from Google Scholar."""

    def __init__(self, proxy: str = None, min_delay: float = 10, max_delay: float = 15):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request_time = 0

        if proxy:
            pg = ProxyGenerator()
            pg.SingleProxy(http=proxy, https=proxy)
            scholarly.use_proxy(pg)
            logger.info(f"Scholar using proxy: {proxy}")

    def _wait(self):
        elapsed = time.time() - self._last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def search_and_get_bibtex(self, query: str, max_results: int = 5) -> list[dict]:
        """Search Google Scholar and return results with BibTeX.

        Returns list of dicts with keys: title, authors, year, venue, bibtex, url
        """
        results = []
        try:
            self._wait()
            search_results = scholarly.search_pubs(query)

            for i, pub in enumerate(search_results):
                if i >= max_results:
                    break
                try:
                    result = self._extract_pub_info(pub)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to extract pub info: {e}")
                    continue

        except Exception as e:
            logger.error(f"Scholar search failed for '{query}': {e}")

        return results

    def get_bibtex_for_title(self, title: str, venue: str = None) -> str | None:
        """Search for a specific paper and return its BibTeX.

        If venue is provided, search with venue to find published version.
        """
        query = f'"{title}"'
        if venue:
            query = f'"{title}" {venue}'

        try:
            self._wait()
            search_results = scholarly.search_pubs(query)
            pub = next(search_results, None)

            if pub is None:
                # Retry without venue
                if venue:
                    return self.get_bibtex_for_title(title, venue=None)
                return None

            # Fill in details and get BibTeX
            self._wait()
            pub_filled = scholarly.fill(pub)
            bibtex = scholarly.bibtex(pub_filled)
            return bibtex

        except StopIteration:
            return None
        except Exception as e:
            logger.error(f"Scholar BibTeX fetch failed for '{title}': {e}")
            # Retry without venue if that was included
            if venue:
                try:
                    return self.get_bibtex_for_title(title, venue=None)
                except Exception:
                    pass
            return None

    def _extract_pub_info(self, pub) -> dict | None:
        """Extract publication info from a scholarly result."""
        bib = pub.get('bib', {})
        if not bib:
            return None

        title = bib.get('title', '')
        if not title:
            return None

        # Try to get BibTeX
        bibtex = None
        try:
            self._wait()
            pub_filled = scholarly.fill(pub)
            bibtex = scholarly.bibtex(pub_filled)
        except Exception as e:
            logger.warning(f"Failed to get BibTeX for '{title}': {e}")

        authors = bib.get('author', '')
        if isinstance(authors, list):
            authors = ' and '.join(authors)

        return {
            'title': title,
            'authors': authors,
            'year': str(bib.get('pub_year', '')),
            'venue': bib.get('venue', '') or bib.get('journal', '') or bib.get('conference', ''),
            'bibtex': bibtex,
            'url': pub.get('pub_url', '') or pub.get('eprint_url', ''),
            'num_citations': pub.get('num_citations', 0),
        }
