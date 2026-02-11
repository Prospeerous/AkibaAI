"""
CBK Data Scraper - Central Bank of Kenya
==========================================

Scrapes monetary policy reports, financial stability reports,
and other publications from the CBK website.

Usage:
    python scripts/1_scrape_cbk.py
"""

import os
import json
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
import time
from typing import List, Dict

# Configuration
CBK_BASE_URL = "https://www.centralbank.go.ke"
CBK_PUBLICATIONS_URL = f"{CBK_BASE_URL}/publications/"

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "cbk"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "cbk"

# Create directories
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Scraping settings
MAX_PDFS = 15  # Start with 15 documents for Phase 1
REQUEST_DELAY = 2  # Be respectful - 2 seconds between requests


class CBKScraper:
    """Scraper for Central Bank of Kenya publications"""

    def __init__(self, base_url: str = CBK_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def find_pdf_links(self, page_url: str) -> List[Dict[str, str]]:
        """
        Find all PDF links on a given page

        Returns:
            List of dicts with 'url', 'title' keys
        """
        print(f"Scanning page: {page_url}")

        try:
            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            pdf_links = []

            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']

                # Check if it's a PDF
                if href.lower().endswith('.pdf'):
                    full_url = urljoin(page_url, href)
                    title = link.get_text(strip=True) or urlparse(href).path.split('/')[-1]

                    pdf_links.append({
                        'url': full_url,
                        'title': title,
                        'source_page': page_url
                    })

            print(f"Found {len(pdf_links)} PDFs on this page")
            return pdf_links

        except Exception as e:
            print(f"Error scanning {page_url}: {e}")
            return []

    def download_pdf(self, url: str, save_path: Path) -> bool:
        """Download a PDF file"""
        try:
            print(f"  Downloading: {url}")
            response = self.session.get(url, timeout=60)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)

            print(f"  ✓ Saved to: {save_path.name}")
            return True

        except Exception as e:
            print(f"  ✗ Error downloading {url}: {e}")
            return False

    def parse_pdf(self, pdf_path: Path) -> Dict[str, any]:
        """
        Extract text and metadata from PDF

        Returns:
            Dict with 'text', 'pages', 'metadata'
        """
        try:
            doc = fitz.open(pdf_path)

            # Extract metadata
            metadata = doc.metadata

            # Extract text from all pages
            text_content = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                text_content.append(text)

            full_text = "\n\n".join(text_content)

            doc.close()

            return {
                'text': full_text,
                'pages': len(text_content),
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'creation_date': metadata.get('creationDate', ''),
                'char_count': len(full_text),
                'word_count': len(full_text.split())
            }

        except Exception as e:
            print(f"  ✗ Error parsing PDF {pdf_path.name}: {e}")
            return None

    def scrape_publications(self, max_pdfs: int = MAX_PDFS) -> List[Dict]:
        """
        Main scraping function

        Scrapes CBK publications, downloads PDFs, and extracts text
        """
        print(f"\n{'='*60}")
        print("CBK SCRAPER - Central Bank of Kenya")
        print(f"{'='*60}\n")

        # Key CBK publication pages
        publication_pages = [
            f"{self.base_url}/publications/",
            f"{self.base_url}/monetary-policy/",
            f"{self.base_url}/statistics/",
        ]

        # Find all PDF links
        all_pdfs = []
        for page_url in publication_pages:
            pdf_links = self.find_pdf_links(page_url)
            all_pdfs.extend(pdf_links)
            time.sleep(REQUEST_DELAY)

        # Remove duplicates
        seen_urls = set()
        unique_pdfs = []
        for pdf in all_pdfs:
            if pdf['url'] not in seen_urls:
                seen_urls.add(pdf['url'])
                unique_pdfs.append(pdf)

        print(f"\nFound {len(unique_pdfs)} unique PDFs")
        print(f"Will download and process up to {max_pdfs} documents\n")

        # Download and process PDFs
        processed_docs = []
        for i, pdf_info in enumerate(unique_pdfs[:max_pdfs], 1):
            print(f"\n[{i}/{min(max_pdfs, len(unique_pdfs))}] Processing: {pdf_info['title'][:60]}...")

            # Generate filename
            filename = f"cbk_{i:03d}_{urlparse(pdf_info['url']).path.split('/')[-1]}"
            pdf_path = RAW_DATA_DIR / filename

            # Download PDF
            if self.download_pdf(pdf_info['url'], pdf_path):
                # Parse PDF
                parsed_data = self.parse_pdf(pdf_path)

                if parsed_data:
                    # Save processed text
                    text_filename = pdf_path.stem + ".txt"
                    text_path = PROCESSED_DATA_DIR / text_filename

                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(parsed_data['text'])

                    # Save metadata
                    doc_metadata = {
                        'id': f"cbk_{i:03d}",
                        'title': pdf_info['title'],
                        'url': pdf_info['url'],
                        'source': 'Central Bank of Kenya',
                        'source_page': pdf_info['source_page'],
                        'pdf_file': str(pdf_path),
                        'text_file': str(text_path),
                        'scraped_date': datetime.now().isoformat(),
                        'pages': parsed_data['pages'],
                        'char_count': parsed_data['char_count'],
                        'word_count': parsed_data['word_count'],
                        'pdf_metadata': {
                            'title': parsed_data['title'],
                            'author': parsed_data['author'],
                            'creation_date': parsed_data['creation_date']
                        }
                    }

                    processed_docs.append(doc_metadata)

                    print(f"  ✓ Extracted {parsed_data['pages']} pages, {parsed_data['word_count']:,} words")

            # Be respectful - delay between requests
            if i < min(max_pdfs, len(unique_pdfs)):
                time.sleep(REQUEST_DELAY)

        return processed_docs


def save_metadata(documents: List[Dict], output_path: Path):
    """Save scraping metadata to JSON"""
    metadata = {
        'scrape_date': datetime.now().isoformat(),
        'source': 'Central Bank of Kenya',
        'total_documents': len(documents),
        'documents': documents
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nMetadata saved to: {output_path}")


def main():
    """Main execution"""
    print("\nStarting CBK scraper...")
    print(f"Raw data directory: {RAW_DATA_DIR}")
    print(f"Processed data directory: {PROCESSED_DATA_DIR}")

    # Initialize scraper
    scraper = CBKScraper()

    # Scrape publications
    documents = scraper.scrape_publications(max_pdfs=MAX_PDFS)

    # Save metadata
    metadata_path = PROCESSED_DATA_DIR / "cbk_metadata.json"
    save_metadata(documents, metadata_path)

    # Summary
    print(f"\n{'='*60}")
    print("SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"✓ Successfully processed: {len(documents)} documents")
    print(f"✓ Raw PDFs saved to: {RAW_DATA_DIR}")
    print(f"✓ Extracted text saved to: {PROCESSED_DATA_DIR}")
    print(f"✓ Metadata saved to: {metadata_path}")

    # Statistics
    total_words = sum(doc['word_count'] for doc in documents)
    total_pages = sum(doc['pages'] for doc in documents)

    print(f"\nStatistics:")
    print(f"  - Total pages: {total_pages:,}")
    print(f"  - Total words: {total_words:,}")
    print(f"  - Average words per document: {total_words//len(documents):,}")

    print(f"\n✓ Ready for Step 2: Run 'python scripts/2_build_index.py'\n")


if __name__ == "__main__":
    main()
