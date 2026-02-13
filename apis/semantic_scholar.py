"""Semantic Scholar API client for metadata and venue detection."""
import logging
from apis import RateLimitedClient

logger = logging.getLogger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient(RateLimitedClient):
    """Query Semantic Scholar for paper metadata and venue detection."""

    def __init__(self):
        super().__init__(min_delay=1.0, max_delay=3.0)

    def get_paper_by_arxiv_id(self, arxiv_id: str) -> dict | None:
        """Look up a paper by arXiv ID.

        Returns dict with title, authors, year, venue, externalIds, publicationVenue.
        """
        url = f"{S2_API_BASE}/paper/ARXIV:{arxiv_id}"
        params = {
            'fields': 'title,authors,year,venue,externalIds,publicationVenue,abstract,citationCount'
        }
        try:
            resp = self.get(url, params=params)
            data = resp.json()
            return self._parse_paper(data)
        except Exception as e:
            logger.error(f"S2 lookup failed for arXiv:{arxiv_id}: {e}")
            return None

    def get_paper_by_doi(self, doi: str) -> dict | None:
        """Look up a paper by DOI."""
        url = f"{S2_API_BASE}/paper/DOI:{doi}"
        params = {
            'fields': 'title,authors,year,venue,externalIds,publicationVenue,abstract,citationCount'
        }
        try:
            resp = self.get(url, params=params)
            data = resp.json()
            return self._parse_paper(data)
        except Exception as e:
            logger.error(f"S2 lookup failed for DOI:{doi}: {e}")
            return None

    def search_paper(self, query: str, limit: int = 5) -> list[dict]:
        """Search for papers by title query."""
        url = f"{S2_API_BASE}/paper/search"
        params = {
            'query': query,
            'limit': limit,
            'fields': 'title,authors,year,venue,externalIds,publicationVenue,abstract,citationCount'
        }
        try:
            resp = self.get(url, params=params)
            data = resp.json()
            papers = data.get('data', [])
            return [self._parse_paper(p) for p in papers if p]
        except Exception as e:
            logger.error(f"S2 search failed for '{query}': {e}")
            return []

    def is_published(self, paper_info: dict) -> bool:
        """Check if a paper has been published at a venue (not just arXiv)."""
        if not paper_info:
            return False
        venue = paper_info.get('venue', '')
        doi = paper_info.get('doi', '')
        pub_venue = paper_info.get('publication_venue')

        # Has a non-arXiv venue
        if venue and venue.lower() not in ('arxiv', 'arxiv.org', ''):
            return True
        # Has a DOI that's not an arXiv DOI
        if doi and 'arxiv' not in doi.lower():
            return True
        # Has a publication venue object
        if pub_venue and pub_venue.get('name'):
            return True

        return False

    def _parse_paper(self, data: dict) -> dict:
        """Parse S2 API response into a clean dict."""
        external_ids = data.get('externalIds', {}) or {}
        authors = data.get('authors', []) or []
        author_names = [a.get('name', '') for a in authors if a.get('name')]
        pub_venue = data.get('publicationVenue')

        return {
            'title': data.get('title', ''),
            'authors': ' and '.join(author_names),
            'year': str(data.get('year', '')),
            'venue': data.get('venue', ''),
            'doi': external_ids.get('DOI', ''),
            'arxiv_id': external_ids.get('ArXiv', ''),
            'abstract': data.get('abstract', ''),
            'citation_count': data.get('citationCount', 0),
            'publication_venue': {
                'name': pub_venue.get('name', '') if pub_venue else '',
                'type': pub_venue.get('type', '') if pub_venue else '',
            } if pub_venue else None,
            's2_id': data.get('paperId', ''),
        }
