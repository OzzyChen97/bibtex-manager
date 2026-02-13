"""Normalization pipeline for BibTeX entries."""
import re
from unidecode import unidecode
from models.entry import BibEntry


MONTH_MAP = {
    'january': 'jan', 'february': 'feb', 'march': 'mar', 'april': 'apr',
    'may': 'may', 'june': 'jun', 'july': 'jul', 'august': 'aug',
    'september': 'sep', 'october': 'oct', 'november': 'nov', 'december': 'dec',
    '1': 'jan', '2': 'feb', '3': 'mar', '4': 'apr', '5': 'may', '6': 'jun',
    '7': 'jul', '8': 'aug', '9': 'sep', '10': 'oct', '11': 'nov', '12': 'dec',
    '01': 'jan', '02': 'feb', '03': 'mar', '04': 'apr', '05': 'may', '06': 'jun',
    '07': 'jul', '08': 'aug', '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dec',
}

# Common acronyms that should be brace-protected in titles
TITLE_ACRONYMS = [
    'BERT', 'GPT', 'ResNet', 'VGG', 'GAN', 'GANs', 'LSTM', 'GRU', 'CNN', 'CNNs',
    'RNN', 'RNNs', 'NLP', 'CV', 'RL', 'SLAM', 'YOLO', 'SSD', 'RGB', 'RGBD',
    'IoU', 'mAP', 'FPN', 'ROI', 'RoI', 'ViT', 'CLIP', 'DALL-E', 'DALLE',
    'LLM', 'LLMs', 'SAM', 'NeRF', 'NeRFs', 'DETR', 'DINO', 'MAE', 'BEiT',
    'Transformer', 'Transformers', 'ImageNet', 'COCO', 'VOC', 'CIFAR',
    'Adam', 'SGD', 'BatchNorm', 'LayerNorm', 'ReLU', 'GELU', 'SiLU',
    'U-Net', 'UNet', 'EfficientNet', 'MobileNet', 'DenseNet', 'InceptionNet',
    '3D', '2D', '4D', 'RGB-D', 'LiDAR', 'MRI', 'CT', 'PET',
    'GNN', 'GNNs', 'VAE', 'VAEs', 'MLP', 'MLPs', 'KNN',
    'API', 'GPU', 'TPU', 'CPU', 'FLOPS', 'FLOPs',
    'SOTA', 'SoTA', 'CVPR', 'ICCV', 'ECCV', 'NeurIPS', 'ICML', 'ICLR',
    'AAAI', 'IJCAI', 'ACL', 'EMNLP', 'NAACL', 'MICCAI',
]


def normalize_entry(entry: BibEntry, existing_keys: set[str] = None) -> BibEntry:
    """Apply full normalization pipeline to a BibEntry."""
    if existing_keys is None:
        existing_keys = set()

    if entry.author:
        entry.author = normalize_authors(entry.author)
    if entry.title:
        entry.title = normalize_title(entry.title)
    if entry.pages:
        entry.pages = normalize_pages(entry.pages)
    if entry.month:
        entry.month = normalize_month(entry.month)
    if entry.doi:
        entry.doi = normalize_doi(entry.doi)

    # Generate citation key
    entry.citation_key = generate_citation_key(entry, existing_keys)
    existing_keys.add(entry.citation_key)

    return entry


def normalize_authors(author_str: str) -> str:
    """Normalize author string to 'Last, First and Last2, First2' format."""
    if not author_str:
        return author_str

    # Already in good format check
    author_str = author_str.strip()

    # Split by ' and '
    authors = re.split(r'\s+and\s+', author_str)
    normalized = []

    for author in authors:
        author = author.strip()
        if not author:
            continue
        # If already in "Last, First" format
        if ',' in author:
            parts = [p.strip() for p in author.split(',', 1)]
            normalized.append(f"{parts[0]}, {parts[1]}")
        else:
            # "First Middle Last" format -> "Last, First Middle"
            name_parts = author.split()
            if len(name_parts) == 1:
                normalized.append(name_parts[0])
            else:
                last = name_parts[-1]
                first = ' '.join(name_parts[:-1])
                normalized.append(f"{last}, {first}")

    return ' and '.join(normalized)


def normalize_title(title: str) -> str:
    """Protect acronyms and proper nouns in title with braces."""
    if not title:
        return title

    # Remove existing outer braces
    title = title.strip()
    if title.startswith('{') and title.endswith('}'):
        title = title[1:-1]

    # Protect known acronyms
    for acronym in TITLE_ACRONYMS:
        # Match whole word, not already in braces
        pattern = r'(?<!\{)\b(' + re.escape(acronym) + r')\b(?!\})'
        title = re.sub(pattern, r'{\1}', title)

    return title


def normalize_pages(pages: str) -> str:
    """Normalize page ranges to use double-dash."""
    if not pages:
        return pages
    # Replace single dash, en-dash, em-dash with double-dash
    pages = re.sub(r'\s*[-\u2013\u2014]+\s*', '--', pages)
    # Ensure double-dash (not triple or more)
    pages = re.sub(r'-{3,}', '--', pages)
    return pages


def normalize_month(month: str) -> str:
    """Normalize month to 3-letter abbreviation."""
    if not month:
        return month
    month_lower = month.strip().lower().rstrip('.')
    return MONTH_MAP.get(month_lower, month)


def normalize_doi(doi: str) -> str:
    """Normalize DOI: strip URL prefix, lowercase."""
    if not doi:
        return doi
    doi = doi.strip()
    # Remove URL prefixes
    for prefix in ('https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'http://dx.doi.org/'):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.strip()


def generate_citation_key(entry: BibEntry, existing_keys: set[str] = None) -> str:
    """Generate citation key in AuthorYearFirstWord format."""
    if existing_keys is None:
        existing_keys = set()

    # Extract last name of first author
    author_part = 'Unknown'
    if entry.author:
        first_author = entry.author.split(' and ')[0].strip()
        if ',' in first_author:
            author_part = first_author.split(',')[0].strip()
        else:
            parts = first_author.split()
            author_part = parts[-1] if parts else 'Unknown'

    # Clean author part
    author_part = unidecode(author_part)
    author_part = re.sub(r'[^a-zA-Z]', '', author_part)
    if not author_part:
        author_part = 'Unknown'

    # Year
    year_part = entry.year or 'XXXX'

    # First significant word of title
    title_word = ''
    if entry.title:
        # Remove braces and get words
        clean_title = re.sub(r'[{}]', '', entry.title)
        words = clean_title.split()
        stop_words = {'a', 'an', 'the', 'on', 'in', 'of', 'for', 'and', 'or', 'to', 'with', 'from', 'by', 'at', 'is', 'are', 'was', 'were'}
        for w in words:
            clean_w = re.sub(r'[^a-zA-Z]', '', w)
            if clean_w.lower() not in stop_words and len(clean_w) > 1:
                title_word = clean_w
                break

    base_key = f"{author_part}{year_part}{title_word}"

    # Handle collisions
    if base_key not in existing_keys:
        return base_key

    for suffix in 'BCDEFGHIJKLMNOPQRSTUVWXYZ':
        candidate = f"{base_key}{suffix}"
        if candidate not in existing_keys:
            return candidate

    # Fallback
    i = 2
    while f"{base_key}{i}" in existing_keys:
        i += 1
    return f"{base_key}{i}"
