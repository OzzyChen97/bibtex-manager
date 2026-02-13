"""Orchestrator: resolves paper identifiers to normalized BibTeX entries.

Core pipeline:
  Input (DOI / arXiv ID / title)
    -> detect type
    -> fetch metadata (Semantic Scholar, arXiv, CrossRef)
    -> check if arXiv paper is published
    -> fetch BibTeX from Google Scholar (published version if available)
    -> normalize
    -> return BibEntry
"""
import re
import logging
from models.entry import BibEntry
from services.parser import parse_bibtex
from services.normalizer import normalize_entry
from apis.scholar import ScholarClient
from apis.semantic_scholar import SemanticScholarClient
from apis.crossref import CrossRefClient
from apis.arxiv_api import ArxivClient

logger = logging.getLogger(__name__)

# Patterns
DOI_PATTERN = re.compile(r'^10\.\d{4,}/.+')
ARXIV_PATTERN = re.compile(r'^(\d{4}\.\d{4,5})(v\d+)?$')
ARXIV_OLD_PATTERN = re.compile(r'^[a-z\-]+/\d{7}$')


class Resolver:
    """Orchestrates paper lookup and BibTeX resolution."""

    def __init__(self, scholar_proxy=None, scholar_min_delay=10, scholar_max_delay=15):
        self.scholar = ScholarClient(
            proxy=scholar_proxy,
            min_delay=scholar_min_delay,
            max_delay=scholar_max_delay,
        )
        self.s2 = SemanticScholarClient()
        self.crossref = CrossRefClient()
        self.arxiv = ArxivClient()

    def detect_input_type(self, query: str) -> str:
        """Detect if input is a DOI, arXiv ID, or title."""
        query = query.strip()
        # Remove URL wrappers
        if 'doi.org/' in query:
            query = query.split('doi.org/')[-1]
        if 'arxiv.org/abs/' in query:
            query = query.split('arxiv.org/abs/')[-1]

        if DOI_PATTERN.match(query):
            return 'doi'
        if ARXIV_PATTERN.match(query) or ARXIV_OLD_PATTERN.match(query):
            return 'arxiv'
        return 'title'

    def clean_query(self, query: str) -> str:
        """Extract the core identifier from a query."""
        query = query.strip()
        if 'doi.org/' in query:
            return query.split('doi.org/')[-1]
        if 'arxiv.org/abs/' in query:
            return query.split('arxiv.org/abs/')[-1]
        return query

    def resolve(self, query: str, existing_keys: set[str] = None) -> dict:
        """Resolve a query to a BibEntry.

        Returns dict with: entry (BibEntry or None), source_info (dict), error (str or None)
        """
        if existing_keys is None:
            existing_keys = set()

        query = self.clean_query(query)
        input_type = self.detect_input_type(query)
        logger.info(f"Resolving '{query}' as {input_type}")

        try:
            if input_type == 'arxiv':
                return self._resolve_arxiv(query, existing_keys)
            elif input_type == 'doi':
                return self._resolve_doi(query, existing_keys)
            else:
                return self._resolve_title(query, existing_keys)
        except Exception as e:
            logger.error(f"Resolution failed for '{query}': {e}")
            return {'entry': None, 'source_info': {}, 'error': str(e)}

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search for papers and return results with metadata.

        Returns list of dicts with paper info and optional BibTeX.
        """
        query = self.clean_query(query)
        input_type = self.detect_input_type(query)

        results = []

        if input_type == 'arxiv':
            # Look up the specific arXiv paper
            paper = self._get_arxiv_metadata(query)
            if paper:
                results.append(paper)
        elif input_type == 'doi':
            paper = self._get_doi_metadata(query)
            if paper:
                results.append(paper)
        else:
            # Search via Scholar
            scholar_results = self.scholar.search_and_get_bibtex(query, max_results=max_results)
            for sr in scholar_results:
                results.append({
                    'title': sr.get('title', ''),
                    'authors': sr.get('authors', ''),
                    'year': sr.get('year', ''),
                    'venue': sr.get('venue', ''),
                    'bibtex': sr.get('bibtex'),
                    'source': 'scholar',
                    'is_published': bool(sr.get('venue')),
                })

        return results

    def _resolve_arxiv(self, arxiv_id: str, existing_keys: set[str]) -> dict:
        """Resolve an arXiv paper, checking for published version."""
        # Strip version
        base_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id

        # Step 1: Get metadata from Semantic Scholar
        s2_info = self.s2.get_paper_by_arxiv_id(base_id)
        title = None
        venue = None
        is_published = False

        if s2_info:
            title = s2_info.get('title')
            is_published = self.s2.is_published(s2_info)
            if is_published:
                venue = s2_info.get('venue', '')
                pub_venue = s2_info.get('publication_venue')
                if pub_venue and pub_venue.get('name'):
                    venue = pub_venue['name']
                logger.info(f"arXiv:{base_id} is published at: {venue}")

        # Fallback: get title from arXiv API
        if not title:
            arxiv_info = self.arxiv.get_by_id(arxiv_id)
            if arxiv_info:
                title = arxiv_info.get('title')

        if not title:
            return {'entry': None, 'source_info': {},
                    'error': f'Could not find paper with arXiv ID: {arxiv_id}'}

        # Step 2: Fetch BibTeX from Google Scholar
        bibtex_str = self.scholar.get_bibtex_for_title(title, venue=venue if is_published else None)

        source_info = {
            'input_type': 'arxiv',
            'arxiv_id': base_id,
            'is_published': is_published,
            'venue': venue or '',
            'bibtex_source': 'scholar' if bibtex_str else 'constructed',
        }

        if bibtex_str:
            entries = parse_bibtex(bibtex_str)
            if entries:
                entry = entries[0]
                # Ensure arXiv ID is preserved
                if not entry.arxiv_id:
                    entry.arxiv_id = base_id
                # Merge S2 metadata if available
                if s2_info:
                    if not entry.doi and s2_info.get('doi'):
                        entry.doi = s2_info['doi']
                    if not entry.abstract and s2_info.get('abstract'):
                        entry.abstract = s2_info['abstract']
                entry.source = 'scholar'
                entry = normalize_entry(entry, existing_keys)
                return {'entry': entry, 'source_info': source_info, 'error': None}

        # Fallback: construct entry from metadata
        entry = self._construct_entry_from_metadata(s2_info, arxiv_id=base_id)
        if entry:
            entry = normalize_entry(entry, existing_keys)
        return {'entry': entry, 'source_info': source_info, 'error': None}

    def _resolve_doi(self, doi: str, existing_keys: set[str]) -> dict:
        """Resolve a DOI to a BibTeX entry."""
        # Get metadata from CrossRef
        cr_info = self.crossref.get_by_doi(doi)
        title = cr_info.get('title') if cr_info else None

        # Also try Semantic Scholar
        s2_info = self.s2.get_paper_by_doi(doi)
        if not title and s2_info:
            title = s2_info.get('title')

        source_info = {
            'input_type': 'doi',
            'doi': doi,
            'bibtex_source': 'unknown',
        }

        if title:
            # Fetch BibTeX from Scholar
            bibtex_str = self.scholar.get_bibtex_for_title(title)
            if bibtex_str:
                entries = parse_bibtex(bibtex_str)
                if entries:
                    entry = entries[0]
                    if not entry.doi:
                        entry.doi = doi
                    if s2_info and not entry.abstract and s2_info.get('abstract'):
                        entry.abstract = s2_info['abstract']
                    entry.source = 'scholar'
                    entry = normalize_entry(entry, existing_keys)
                    source_info['bibtex_source'] = 'scholar'
                    return {'entry': entry, 'source_info': source_info, 'error': None}

        # Fallback: construct from CrossRef metadata
        if cr_info:
            entry = self._construct_entry_from_crossref(cr_info)
            if entry:
                entry = normalize_entry(entry, existing_keys)
                source_info['bibtex_source'] = 'crossref'
                return {'entry': entry, 'source_info': source_info, 'error': None}

        return {'entry': None, 'source_info': source_info,
                'error': f'Could not find paper with DOI: {doi}'}

    def _resolve_title(self, title: str, existing_keys: set[str]) -> dict:
        """Resolve a title search to a BibTeX entry."""
        source_info = {
            'input_type': 'title',
            'query': title,
            'bibtex_source': 'unknown',
        }

        bibtex_str = self.scholar.get_bibtex_for_title(title)
        if bibtex_str:
            entries = parse_bibtex(bibtex_str)
            if entries:
                entry = entries[0]
                entry.source = 'scholar'
                entry = normalize_entry(entry, existing_keys)
                source_info['bibtex_source'] = 'scholar'
                return {'entry': entry, 'source_info': source_info, 'error': None}

        return {'entry': None, 'source_info': source_info,
                'error': f'No results found for: {title}'}

    def _get_arxiv_metadata(self, arxiv_id: str) -> dict | None:
        """Get combined metadata for an arXiv paper."""
        base_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id

        # Try Semantic Scholar first
        s2_info = self.s2.get_paper_by_arxiv_id(base_id)
        if s2_info:
            is_published = self.s2.is_published(s2_info)
            venue = s2_info.get('venue', '')
            pub_venue = s2_info.get('publication_venue')
            if pub_venue and pub_venue.get('name'):
                venue = pub_venue['name']
            return {
                'title': s2_info.get('title', ''),
                'authors': s2_info.get('authors', ''),
                'year': s2_info.get('year', ''),
                'venue': venue,
                'arxiv_id': base_id,
                'doi': s2_info.get('doi', ''),
                'is_published': is_published,
                'source': 'semantic_scholar',
            }

        # Fallback to arXiv API
        arxiv_info = self.arxiv.get_by_id(arxiv_id)
        if arxiv_info:
            return {
                'title': arxiv_info.get('title', ''),
                'authors': arxiv_info.get('authors', ''),
                'year': arxiv_info.get('year', ''),
                'venue': '',
                'arxiv_id': base_id,
                'doi': arxiv_info.get('doi', ''),
                'is_published': False,
                'source': 'arxiv',
            }

        return None

    def _get_doi_metadata(self, doi: str) -> dict | None:
        """Get metadata for a DOI."""
        cr_info = self.crossref.get_by_doi(doi)
        if cr_info:
            return {
                'title': cr_info.get('title', ''),
                'authors': cr_info.get('authors', ''),
                'year': cr_info.get('year', ''),
                'venue': cr_info.get('journal', ''),
                'doi': doi,
                'is_published': True,
                'source': 'crossref',
            }
        return None

    def _construct_entry_from_metadata(self, s2_info: dict, arxiv_id: str = None) -> BibEntry | None:
        """Construct a BibEntry from Semantic Scholar metadata."""
        if not s2_info:
            return None

        is_published = self.s2.is_published(s2_info)
        venue = s2_info.get('venue', '')
        pub_venue = s2_info.get('publication_venue')

        if is_published and pub_venue and pub_venue.get('type') == 'journal':
            entry_type = 'article'
        elif is_published:
            entry_type = 'inproceedings'
        else:
            entry_type = 'misc'

        entry = BibEntry(
            citation_key='temp',
            entry_type=entry_type,
            title=s2_info.get('title', ''),
            author=s2_info.get('authors', ''),
            year=s2_info.get('year', ''),
            doi=s2_info.get('doi', ''),
            arxiv_id=arxiv_id,
            abstract=s2_info.get('abstract', ''),
            source='semantic_scholar',
        )

        if entry_type == 'article':
            entry.journal = venue or (pub_venue.get('name', '') if pub_venue else '')
        elif entry_type == 'inproceedings':
            entry.booktitle = venue or (pub_venue.get('name', '') if pub_venue else '')

        return entry

    def _construct_entry_from_crossref(self, cr_info: dict) -> BibEntry | None:
        """Construct a BibEntry from CrossRef metadata."""
        if not cr_info:
            return None

        cr_type = cr_info.get('type', '')
        if cr_type in ('journal-article', 'article'):
            entry_type = 'article'
        elif cr_type in ('proceedings-article',):
            entry_type = 'inproceedings'
        else:
            entry_type = 'article'

        entry = BibEntry(
            citation_key='temp',
            entry_type=entry_type,
            title=cr_info.get('title', ''),
            author=cr_info.get('authors', ''),
            year=cr_info.get('year', ''),
            doi=cr_info.get('doi', ''),
            volume=cr_info.get('volume', ''),
            number=cr_info.get('number', ''),
            pages=cr_info.get('pages', ''),
            publisher=cr_info.get('publisher', ''),
            source='crossref',
        )

        journal = cr_info.get('journal', '')
        if entry_type == 'article':
            entry.journal = journal
        elif entry_type == 'inproceedings':
            entry.booktitle = journal

        return entry
