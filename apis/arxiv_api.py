"""arXiv API client for metadata retrieval."""
import logging
import xml.etree.ElementTree as ET
from apis import RateLimitedClient

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "http://export.arxiv.org/api/query"
ATOM_NS = '{http://www.w3.org/2005/Atom}'


class ArxivClient(RateLimitedClient):
    """Query arXiv API for paper metadata."""

    def __init__(self):
        super().__init__(min_delay=1.0, max_delay=3.0)

    def get_by_id(self, arxiv_id: str) -> dict | None:
        """Look up a paper by arXiv ID."""
        # Strip version suffix for search
        clean_id = arxiv_id.strip()
        params = {
            'id_list': clean_id,
            'max_results': 1,
        }
        try:
            resp = self.get(ARXIV_API_BASE, params=params)
            return self._parse_response(resp.text)
        except Exception as e:
            logger.error(f"arXiv lookup failed for {arxiv_id}: {e}")
            return None

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search arXiv by query string."""
        params = {
            'search_query': f'all:{query}',
            'max_results': max_results,
            'sortBy': 'relevance',
        }
        try:
            resp = self.get(ARXIV_API_BASE, params=params)
            return self._parse_response_list(resp.text)
        except Exception as e:
            logger.error(f"arXiv search failed for '{query}': {e}")
            return []

    def _parse_response(self, xml_text: str) -> dict | None:
        """Parse single result from arXiv Atom feed."""
        results = self._parse_response_list(xml_text)
        return results[0] if results else None

    def _parse_response_list(self, xml_text: str) -> list[dict]:
        """Parse arXiv Atom feed into list of paper dicts."""
        results = []
        try:
            root = ET.fromstring(xml_text)
            for entry in root.findall(f'{ATOM_NS}entry'):
                paper = self._parse_entry(entry)
                if paper and paper.get('title'):
                    results.append(paper)
        except ET.ParseError as e:
            logger.error(f"Failed to parse arXiv XML: {e}")
        return results

    def _parse_entry(self, entry) -> dict:
        """Parse a single Atom entry element."""
        title_el = entry.find(f'{ATOM_NS}title')
        title = title_el.text.strip().replace('\n', ' ') if title_el is not None and title_el.text else ''

        summary_el = entry.find(f'{ATOM_NS}summary')
        abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ''

        # Extract authors
        authors = []
        for author_el in entry.findall(f'{ATOM_NS}author'):
            name_el = author_el.find(f'{ATOM_NS}name')
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        # Extract arXiv ID from the entry id URL
        id_el = entry.find(f'{ATOM_NS}id')
        arxiv_url = id_el.text.strip() if id_el is not None and id_el.text else ''
        arxiv_id = ''
        if 'arxiv.org/abs/' in arxiv_url:
            arxiv_id = arxiv_url.split('arxiv.org/abs/')[-1]

        # Extract published date for year
        published_el = entry.find(f'{ATOM_NS}published')
        year = ''
        if published_el is not None and published_el.text:
            year = published_el.text[:4]

        # Extract DOI if present (in arxiv namespace)
        doi = ''
        for link in entry.findall(f'{ATOM_NS}link'):
            href = link.get('href', '')
            if 'doi.org' in href:
                doi = href.replace('https://doi.org/', '').replace('http://doi.org/', '')

        # Extract categories
        categories = []
        for cat in entry.findall('{http://arxiv.org/schemas/atom}primary_category'):
            term = cat.get('term', '')
            if term:
                categories.append(term)

        return {
            'arxiv_id': arxiv_id,
            'title': title,
            'authors': ' and '.join(authors),
            'year': year,
            'abstract': abstract,
            'doi': doi,
            'url': arxiv_url,
            'categories': categories,
        }
