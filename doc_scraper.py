#!/usr/bin/env python3
"""
Documentation Scraper Tool
==========================
Crawls a documentation site using cookies and exports to:
- PDF (mooi opgemaakt, voor mensen)
- Markdown (clean tekst, voor AI)

Gebruik:
  python doc_scraper.py --url <start_url> --cookies <cookies.json> --output <naam>
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Preformatted,
)
from reportlab.lib.enums import TA_LEFT


# ── helpers ──────────────────────────────────────────────────────────────────

def load_cookies(cookie_file: str) -> dict:
    """Load cookies from a Cookie-Editor JSON export."""
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookie_list = json.load(f)
    return {c["name"]: c["value"] for c in cookie_list}


def make_session(cookies: dict) -> requests.Session:
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Documentation Scraper)",
        "Accept": "text/html,application/xhtml+xml",
    })
    return session


def clean_text(text: str) -> str:
    """Clean up whitespace from extracted text."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def escape_xml(text: str) -> str:
    """Escape characters that break ReportLab XML parsing."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    # Remove non-printable characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


# ── crawler ──────────────────────────────────────────────────────────────────

def get_all_links(soup: BeautifulSoup, base_url: str, root_url: str) -> list:
    """Extract all internal documentation links from the page."""
    parsed_root = urlparse(root_url)
    root_path = parsed_root.path.rsplit('/', 1)[0]  # parent directory

    links = []
    seen = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Only follow links on same domain and same path prefix
        if (parsed.netloc == parsed_root.netloc
                and parsed.path.startswith(root_path)
                and full_url not in seen
                and not parsed.fragment):
            seen.add(full_url)
            links.append(full_url)
    return links


def parse_page(html: str, url: str) -> dict:
    """Parse a documentation page into structured content."""
    soup = BeautifulSoup(html, 'lxml')

    # Remove navigation, sidebar, footer noise
    for tag in soup.find_all(['nav', 'footer', 'script', 'style',
                               'header', 'aside']):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
            r'nav|sidebar|footer|breadcrumb|toc|menu|toolbar|banner', re.I)):
        tag.decompose()

    # Get title
    title = ''
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    # Get main content area
    main = (soup.find('main')
            or soup.find(id=re.compile(r'main|content|article', re.I))
            or soup.find(class_=re.compile(r'main|content|article|wiki', re.I))
            or soup.find('article')
            or soup.body)

    blocks = []  # list of (type, text)
    if main:
        for el in main.descendants:
            if not hasattr(el, 'name'):
                continue
            if el.name in ('h1', 'h2', 'h3', 'h4'):
                text = el.get_text(strip=True)
                if text:
                    blocks.append((el.name, text))
            elif el.name == 'p':
                text = clean_text(el.get_text())
                if text:
                    blocks.append(('p', text))
            elif el.name in ('pre', 'code') and el.parent.name not in ('pre',):
                code = el.get_text()
                if code.strip():
                    blocks.append(('code', code.strip()))
            elif el.name == 'li':
                text = clean_text(el.get_text())
                if text and len(text) < 500:
                    blocks.append(('li', text))

    return {'url': url, 'title': title, 'blocks': blocks}


def crawl(start_url: str, session: requests.Session,
          max_pages: int = 200, delay: float = 0.5) -> list:
    """Crawl all documentation pages starting from start_url."""
    visited = set()
    queue = [start_url]
    pages = []

    print(f"\n🔍 Start crawlen vanaf: {start_url}")
    print(f"   Max pagina's: {max_pages}\n")

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            print(f"  [{len(visited):3d}] {url}")
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"       ⚠️  HTTP {resp.status_code} — overgeslagen")
                continue

            page_data = parse_page(resp.text, url)
            pages.append(page_data)

            # Find more links
            soup = BeautifulSoup(resp.text, 'lxml')
            new_links = get_all_links(soup, url, start_url)
            for link in new_links:
                if link not in visited and link not in queue:
                    queue.append(link)

            time.sleep(delay)

        except Exception as e:
            print(f"       ❌ Fout: {e}")
            continue

    print(f"\n✅ Klaar! {len(pages)} pagina's gecrawld.\n")
    return pages


# ── Markdown export ──────────────────────────────────────────────────────────

def export_markdown(pages: list, output_path: str):
    """Export all pages to a single clean Markdown file."""
    lines = []
    lines.append("# Documentatie Export\n")
    lines.append(f"> Gegenereerd door doc_scraper.py | {len(pages)} pagina's\n\n")
    lines.append("---\n\n")

    for page in pages:
        if not page['title'] and not page['blocks']:
            continue

        lines.append(f"# {page['title']}\n")
        lines.append(f"*Bron: {page['url']}*\n\n")

        for block_type, text in page['blocks']:
            if block_type == 'h1':
                lines.append(f"# {text}\n\n")
            elif block_type == 'h2':
                lines.append(f"## {text}\n\n")
            elif block_type == 'h3':
                lines.append(f"### {text}\n\n")
            elif block_type == 'h4':
                lines.append(f"#### {text}\n\n")
            elif block_type == 'p':
                lines.append(f"{text}\n\n")
            elif block_type == 'code':
                lines.append(f"```\n{text}\n```\n\n")
            elif block_type == 'li':
                lines.append(f"- {text}\n")

        lines.append("\n---\n\n")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"📝 Markdown opgeslagen: {output_path}")


# ── PDF export ───────────────────────────────────────────────────────────────

def export_pdf(pages: list, output_path: str, title: str = "Documentatie"):
    """Export all pages to a nicely formatted PDF."""

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=title,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontSize=28,
        textColor=colors.HexColor('#1a1a2e'),
        spaceAfter=20,
    )
    style_page_title = ParagraphStyle(
        'PageTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#16213e'),
        spaceBefore=10,
        spaceAfter=8,
        borderPad=4,
    )
    style_h2 = ParagraphStyle(
        'H2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0f3460'),
        spaceBefore=10,
        spaceAfter=5,
    )
    style_h3 = ParagraphStyle(
        'H3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#533483'),
        spaceBefore=8,
        spaceAfter=4,
    )
    style_body = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        leading=15,
        spaceAfter=6,
    )
    style_bullet = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=15,
        bulletIndent=5,
        spaceAfter=3,
    )
    style_code = ParagraphStyle(
        'Code',
        fontName='Courier',
        fontSize=8,
        leading=12,
        backColor=colors.HexColor('#f4f4f4'),
        leftIndent=10,
        rightIndent=10,
        spaceBefore=6,
        spaceAfter=6,
        borderColor=colors.HexColor('#cccccc'),
        borderWidth=0.5,
        borderPad=5,
        borderRadius=3,
    )
    style_url = ParagraphStyle(
        'URL',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#888888'),
        spaceAfter=8,
    )

    story = []

    # Cover page
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph(escape_xml(title), style_title))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor('#0f3460')))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Totaal {len(pages)} pagina's gescraped",
        styles['Normal']
    ))
    story.append(PageBreak())

    # Content
    for page in pages:
        if not page['title'] and not page['blocks']:
            continue

        story.append(Paragraph(escape_xml(page['title']), style_page_title))
        story.append(Paragraph(escape_xml(page['url']), style_url))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor('#cccccc')))
        story.append(Spacer(1, 0.2 * cm))

        for block_type, text in page['blocks']:
            text_safe = escape_xml(text)
            try:
                if block_type == 'h2':
                    story.append(Paragraph(text_safe, style_h2))
                elif block_type in ('h3', 'h4'):
                    story.append(Paragraph(text_safe, style_h3))
                elif block_type == 'p':
                    story.append(Paragraph(text_safe, style_body))
                elif block_type == 'li':
                    story.append(Paragraph(f"• {text_safe}", style_bullet))
                elif block_type == 'code':
                    # Use Preformatted for code blocks
                    clean_code = text.replace('\t', '    ')
                    story.append(Preformatted(clean_code, style_code))
            except Exception:
                # Fallback: skip problematic block
                continue

        story.append(PageBreak())

    doc.build(story)
    print(f"📄 PDF opgeslagen: {output_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Documentation Scraper — crawl + export naar PDF & Markdown'
    )
    parser.add_argument('--url', required=True,
                        help='Start URL van de documentatie')
    parser.add_argument('--cookies', required=True,
                        help='Pad naar Cookie-Editor JSON export')
    parser.add_argument('--output', default='documentatie',
                        help='Bestandsnaam zonder extensie (default: documentatie)')
    parser.add_argument('--max-pages', type=int, default=200,
                        help='Max aantal pagina\'s (default: 200)')
    parser.add_argument('--title', default='API Documentatie',
                        help='Titel voor de PDF')
    args = parser.parse_args()

    # Load cookies & create session
    print("🍪 Cookies laden...")
    cookies = load_cookies(args.cookies)
    session = make_session(cookies)

    # Crawl
    pages = crawl(args.url, session, max_pages=args.max_pages)

    if not pages:
        print("❌ Geen pagina's gevonden. Controleer de URL en cookies.")
        sys.exit(1)

    # Export
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = f"{args.output}.md"
    pdf_path = f"{args.output}.pdf"

    export_markdown(pages, md_path)
    export_pdf(pages, pdf_path, title=args.title)

    print(f"\n🎉 Klaar!")
    print(f"   📝 Markdown (voor AI):  {md_path}")
    print(f"   📄 PDF (voor mensen):   {pdf_path}")


if __name__ == '__main__':
    main()