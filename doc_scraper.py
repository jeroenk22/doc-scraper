#!/usr/bin/env python3
"""
Documentation Scraper Tool v4
==============================
Crawls a documentation site (including JavaScript-rendered pages) using
your existing Chrome login session and exports to:
- PDF (nicely formatted, for human reading)
- Markdown (clean text, for AI tools like Claude)

Usage:
  python doc_scraper.py --url <start_url> --output <n> --title "My Docs"
"""

import argparse
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Preformatted,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def clean_text(text):
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def escape_xml(text):
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

def find_chrome_profile():
    home = Path.home()
    system = platform.system()
    candidates = []
    if system == 'Windows':
        candidates = [
            home / 'AppData' / 'Local' / 'Google' / 'Chrome' / 'User Data',
            home / 'AppData' / 'Local' / 'Google' / 'Chrome Beta' / 'User Data',
        ]
    elif system == 'Darwin':
        candidates = [home / 'Library' / 'Application Support' / 'Google' / 'Chrome']
    else:
        candidates = [home / '.config' / 'google-chrome', home / '.config' / 'chromium']
    for p in candidates:
        if p.exists():
            return str(p)
    return ''


def copy_profile(profile_path):
    """Copy Chrome profile to temp dir, using SQLite backup for locked files."""
    temp_profile = tempfile.mkdtemp(prefix='doc_scraper_')
    src_default = Path(profile_path) / 'Default'
    dst_default = Path(temp_profile) / 'Default'

    # Copy everything except known large/irrelevant cache folders
    shutil.copytree(str(src_default), str(dst_default),
        ignore=shutil.ignore_patterns(
            'Cache', 'Code Cache', 'GPUCache', 'ShaderCache',
            'DawnCache', 'Crashpad', 'CrashpadMetrics*'
        ),
        copy_function=safe_copy
    )
    return temp_profile


def safe_copy(src, dst):
    """Copy a file; if locked, use SQLite backup (works for Cookies db)."""
    try:
        shutil.copy2(src, dst)
    except (PermissionError, OSError):
        # Try SQLite backup for database files locked by Chrome
        try:
            src_conn = sqlite3.connect(f'file:{src}?mode=ro&immutable=1', uri=True)
            dst_conn = sqlite3.connect(dst)
            src_conn.backup(dst_conn)
            src_conn.close()
            dst_conn.close()
        except Exception:
            # Skip files we truly cannot access
            pass


# ── browser ───────────────────────────────────────────────────────────────────

def make_driver(start_url):
    """Launch headless Chrome using a copy of your existing logged-in profile."""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-extensions')

    temp_profile = None
    profile_path = find_chrome_profile()

    if profile_path:
        print(f"👤 Chrome profiel gevonden: {profile_path}")
        print("📋 Tijdelijke kopie maken (even geduld)...")
        try:
            temp_profile = copy_profile(profile_path)
            options.add_argument(f'--user-data-dir={temp_profile}')
            options.add_argument('--profile-directory=Default')
            print("✅ Profiel geladen — ingelogd als jezelf!")
        except Exception as e:
            print(f"⚠️  Kon profiel niet kopiëren: {e}")
            if temp_profile and Path(temp_profile).exists():
                shutil.rmtree(temp_profile, ignore_errors=True)
            temp_profile = None
    else:
        print("⚠️  Geen Chrome profiel gevonden.")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver._temp_profile = temp_profile
    return driver


def cleanup_driver(driver):
    driver.quit()
    temp = getattr(driver, '_temp_profile', None)
    if temp and Path(temp).exists():
        shutil.rmtree(temp, ignore_errors=True)
        print("🧹 Tijdelijk profiel opgeruimd")


def get_page_html(driver, url, wait_seconds=4):
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
    except Exception:
        pass
    time.sleep(wait_seconds)
    return driver.page_source


# ── crawler ───────────────────────────────────────────────────────────────────

def get_all_links(html, base_url, root_url):
    soup = BeautifulSoup(html, 'lxml')
    parsed_root = urlparse(root_url)
    root_path = parsed_root.path.rsplit('/', 1)[0]
    links, seen = [], set()
    for a in soup.find_all('a', href=True):
        full_url = urljoin(base_url, a['href'])
        parsed = urlparse(full_url)
        if (parsed.netloc == parsed_root.netloc
                and parsed.path.startswith(root_path)
                and full_url not in seen
                and not parsed.fragment
                and '?' not in full_url):
            seen.add(full_url)
            links.append(full_url)
    return links


def parse_page(html, url):
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup.find_all(['nav', 'footer', 'script', 'style', 'header', 'aside']):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
            r'nav|sidebar|footer|breadcrumb|toc|menu|toolbar|banner|action-bar', re.I)):
        tag.decompose()

    title = ''
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    # Skip error pages
    if title and any(x in title.lower() for x in ['niet weergeven', 'not found', '404', 'access denied', 'inloggen']):
        return {'url': url, 'title': '', 'blocks': []}

    main = (soup.find('main')
            or soup.find(id=re.compile(r'main|content|article', re.I))
            or soup.find(class_=re.compile(r'main|content|article|wiki|page-body', re.I))
            or soup.find('article')
            or soup.body)

    blocks, seen_texts = [], set()
    if main:
        for el in main.descendants:
            if not hasattr(el, 'name'):
                continue
            if el.name in ('h1', 'h2', 'h3', 'h4'):
                text = el.get_text(strip=True)
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    blocks.append((el.name, text))
            elif el.name == 'p':
                text = clean_text(el.get_text())
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    blocks.append(('p', text))
            elif el.name == 'pre':
                code = el.get_text()
                if code.strip():
                    blocks.append(('code', code.strip()))
            elif el.name == 'code' and el.parent.name not in ('pre',):
                code = el.get_text()
                if code.strip() and len(code.strip()) > 10:
                    blocks.append(('code', code.strip()))
            elif el.name == 'li':
                text = clean_text(el.get_text())
                if text and len(text) < 500 and text not in seen_texts:
                    seen_texts.add(text)
                    blocks.append(('li', text))

    return {'url': url, 'title': title, 'blocks': blocks}


def crawl(start_url, driver, max_pages=200, wait_seconds=4):
    visited, queue, pages = set(), [start_url], []
    print(f"\n🔍 Start crawlen vanaf: {start_url}")
    print(f"   Max pagina's: {max_pages}\n")

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            print(f"  [{len(visited):3d}] {url}")
            html = get_page_html(driver, url, wait_seconds)
            page_data = parse_page(html, url)
            if page_data['title']:
                print(f"       ✅ \"{page_data['title']}\" ({len(page_data['blocks'])} blokken)")
                pages.append(page_data)
            else:
                print(f"       ⚠️  Geen content / toegang geweigerd — overgeslagen")
            for link in get_all_links(html, url, start_url):
                if link not in visited and link not in queue:
                    queue.append(link)
        except Exception as e:
            print(f"       ❌ Fout: {e}")

    print(f"\n✅ Klaar! {len(pages)} pagina's gecrawld.\n")
    return pages


# ── exports ───────────────────────────────────────────────────────────────────

def export_markdown(pages, output_path, title):
    lines = [f"# {title}\n\n", f"> {len(pages)} pagina's\n\n", "---\n\n"]
    for page in pages:
        if not page['title']:
            continue
        lines.append(f"# {page['title']}\n\n*Bron: {page['url']}*\n\n")
        for block_type, text in page['blocks']:
            if block_type == 'h1': lines.append(f"# {text}\n\n")
            elif block_type == 'h2': lines.append(f"## {text}\n\n")
            elif block_type == 'h3': lines.append(f"### {text}\n\n")
            elif block_type == 'h4': lines.append(f"#### {text}\n\n")
            elif block_type == 'p': lines.append(f"{text}\n\n")
            elif block_type == 'code': lines.append(f"```\n{text}\n```\n\n")
            elif block_type == 'li': lines.append(f"- {text}\n")
        lines.append("\n---\n\n")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"📝 Markdown: {output_path}")


def export_pdf(pages, output_path, title):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm, topMargin=2.5*cm, bottomMargin=2.5*cm, title=title)
    styles = getSampleStyleSheet()
    s = {
        'title':  ParagraphStyle('T',  parent=styles['Title'],    fontSize=28, textColor=colors.HexColor('#1a1a2e'), spaceAfter=20),
        'ptitle': ParagraphStyle('PT', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#16213e'), spaceBefore=10, spaceAfter=8),
        'h2':     ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0f3460'), spaceBefore=10, spaceAfter=5),
        'h3':     ParagraphStyle('H3', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor('#533483'), spaceBefore=8, spaceAfter=4),
        'body':   ParagraphStyle('B',  parent=styles['Normal'],   fontSize=10, leading=15, spaceAfter=6),
        'bullet': ParagraphStyle('BL', parent=styles['Normal'],   fontSize=10, leading=14, leftIndent=15, spaceAfter=3),
        'code':   ParagraphStyle('C',  fontName='Courier', fontSize=8, leading=12,
                                 backColor=colors.HexColor('#f4f4f4'), leftIndent=10, rightIndent=10,
                                 spaceBefore=6, spaceAfter=6, borderColor=colors.HexColor('#cccccc'),
                                 borderWidth=0.5, borderPad=5),
        'url':    ParagraphStyle('U',  parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#888888'), spaceAfter=8),
    }

    story = [Spacer(1, 3*cm), Paragraph(escape_xml(title), s['title']),
             HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0f3460')),
             Spacer(1, 0.5*cm),
             Paragraph(f"Totaal {len(pages)} pagina's gescraped", styles['Normal']),
             PageBreak()]

    for page in pages:
        if not page['title']:
            continue
        story += [Paragraph(escape_xml(page['title']), s['ptitle']),
                  Paragraph(escape_xml(page['url']), s['url']),
                  HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')),
                  Spacer(1, 0.2*cm)]
        for block_type, text in page['blocks']:
            text_safe = escape_xml(text)
            try:
                if block_type == 'h2': story.append(Paragraph(text_safe, s['h2']))
                elif block_type in ('h3','h4'): story.append(Paragraph(text_safe, s['h3']))
                elif block_type == 'p': story.append(Paragraph(text_safe, s['body']))
                elif block_type == 'li': story.append(Paragraph(f"• {text_safe}", s['bullet']))
                elif block_type == 'code': story.append(Preformatted(text.replace('\t','    '), s['code']))
            except Exception:
                continue
        story.append(PageBreak())

    doc.build(story)
    print(f"📄 PDF: {output_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Documentation Scraper — export to PDF & Markdown')
    parser.add_argument('--url',       required=True,  help='Start URL of the documentation')
    parser.add_argument('--output',    default='documentatie', help='Output filename without extension')
    parser.add_argument('--title',     default='Documentatie', help='Title for the PDF cover page')
    parser.add_argument('--max-pages', type=int, default=200,  help='Max pages to crawl (default: 200)')
    parser.add_argument('--wait',      type=int, default=4,    help='Seconds to wait per page for JS (default: 4)')
    args = parser.parse_args()

    print("🌐 Browser opstarten...")
    driver = make_driver(args.url)

    try:
        pages = crawl(args.url, driver, max_pages=args.max_pages, wait_seconds=args.wait)
    finally:
        cleanup_driver(driver)

    if not pages:
        print("❌ Geen pagina's gevonden. Zorg dat je ingelogd bent in Chrome.")
        sys.exit(1)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    export_markdown(pages, f"{args.output}.md", title=args.title)
    export_pdf(pages,      f"{args.output}.pdf", title=args.title)

    print(f"\n🎉 Klaar!")
    print(f"   📝 Markdown (voor AI):  {args.output}.md")
    print(f"   📄 PDF (voor mensen):   {args.output}.pdf")

if __name__ == '__main__':
    main()