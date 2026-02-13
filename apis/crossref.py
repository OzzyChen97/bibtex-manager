"""CrossRef API client for DOI lookup and verification."""
import logging
from apis import RateLimitedClient

logger = logging.getLogger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org"


class CrossRefClient(RateLimitedClient):
    """Query CrossRef for DOI metadata."""

    def __init__(self):
        super().__init__(min_delay=0.5, max_delay=1.5)
        self.session.headers.update({
            'User-Agent': 'BibTeXManager/1.0 (mailto:bibtex-manager@example.com)'
        })

    def get_by_doi(self, doi: str) -> dict | None:
        """Look up a work by DOI."""
        url = f"{CROSSREF_API_BASE}/works/{doi}"
        try:
            resp = self.get(url)
            data = resp.json()
            message = data.get('message', {})
            return self._parse_work(message)
        except Exception as e:
            logger.error(f"CrossRef lookup failed for DOI:{doi}: {e}")
            return None

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search CrossRef by query string."""
        url = f"{CROSSREF_API_BASE}/works"
        params = {
            'query': query,
            'rows': limit,
            'select': 'DOI,title,author,published-print,container-title,volume,issue,page,type',
        }
        try:
            resp = self.get(url, params=params)
            data = resp.json()
            items = data.get('message', {}).get('items', [])
            return [self._parse_work(item) for item in items]
        except Exception as e:
            logger.error(f"CrossRef search failed for '{query}': {e}")
            return []

    def _parse_work(self, work: dict) -> dict:
        """Parse a CrossRef work item."""
        # Extract title
        titles = work.get('title', [])
        title = titles[0] if titles else ''

        # Extract authors
        authors_raw = work.get('author', [])
        author_parts = []
        for a in authors_raw:
            family = a.get('family', '')
            given = a.get('given', '')
            if family and given:
                author_parts.append(f"{family}, {given}")
            elif family:
                author_parts.append(family)
        authors = ' and '.join(author_parts)

        # Extract year
        date_parts = work.get('published-print', {}).get('date-parts', [[]])
        if not date_parts or not date_parts[0]:
            date_parts = work.get('published-online', {}).get('date-parts', [[]])
        year = str(date_parts[0][0]) if date_parts and date_parts[0] else ''

        # Extract journal/conference
        containers = work.get('container-title', [])
        container = containers[0] if containers else ''

        return {
            'doi': work.get('DOI', ''),
            'title': title,
            'authors': authors,
            'year': year,
            'journal': container,
            'volume': work.get('volume', ''),
            'number': work.get('issue', ''),
            'pages': work.get('page', ''),
            'type': work.get('type', ''),
            'publisher': work.get('publisher', ''),
        }
