# 📚 Doc Scraper

A tool that crawls **login-protected documentation sites** and exports everything to:

- 📄 **PDF** — nicely formatted, for human reading
- 📝 **Markdown** — clean plain text, ideal for feeding into AI tools like Claude

Works by using your **existing Chrome login session** — no passwords, no cookie exports, Chrome can stay open.

---

## ✨ Features

- Crawls all linked pages recursively within the same documentation section
- Preserves headings, paragraphs, bullet points and code blocks
- Skips navigation, sidebars and other noise
- Generates a clean Markdown file optimised for AI consumption
- Generates a styled PDF with cover page for human reading
- Fully reusable — just swap the URL for any other site

---

## 🔧 Requirements

- Python 3.8 or higher
- Google Chrome (already installed and logged in to the documentation site)

---

## 📦 Installation

**1. Clone this repository**

```bash
git clone https://github.com/your-username/doc-scraper.git
cd doc-scraper
```

**2. Install dependencies**

```bash
pip install selenium webdriver-manager beautifulsoup4 reportlab lxml
```

---

## 🚀 Usage

### Before you run

Make sure you are logged in to the documentation site in Chrome. The script makes a temporary copy of your Chrome profile (including your session cookies) so it can access pages that require login. Chrome can stay open while the script runs.

### Run the script

```bash
python doc_scraper.py --url <start_url> --output <output_name> --title "My Documentation"
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--url` | ✅ Yes | The starting URL of the documentation page |
| `--output` | No | Output filename without extension (default: `documentatie`) |
| `--title` | No | Title shown on the PDF cover page (default: `Documentatie`) |
| `--max-pages` | No | Maximum number of pages to crawl (default: `200`) |
| `--wait` | No | Seconds to wait per page for JS rendering (default: `4`) |

### Example

```bash
python doc_scraper.py \
  --url "https://docs.example.com/api/getting-started" \
  --output my_docs \
  --title "Example API Documentation"
```

This produces two files:
- `my_docs.pdf` — formatted PDF for reading
- `my_docs.md` — clean Markdown for use with AI tools

---

## 🤖 Using the Markdown output with AI

Upload the generated `.md` file to an AI assistant like Claude and ask questions about the documentation. Because the Markdown contains all pages in one file with clear headings and code blocks, the AI can understand and answer questions about the full documentation in one go.

---

## 📁 Project structure

```
doc-scraper/
├── doc_scraper.py   # Main script
├── README.md        # This file
└── .gitignore
```

---

## 🔒 .gitignore

```
output/
*.pdf
*.md
!README.md
__pycache__/
*.pyc
```

---

## ❓ Troubleshooting

**"0 pages found" or "cannot display page"**
- Make sure you are logged in to the documentation site in Chrome
- Check that the URL is correct and accessible in your browser

**"Chrome profile not found"**
- Make sure Google Chrome is installed (not Chromium or Edge)
- On Windows, profiles are stored in `%LOCALAPPDATA%\Google\Chrome\User Data`

**PDF looks wrong / missing content**
- Try increasing the wait time: `--wait 8`
- Some sites load content slowly

---

## 📄 License

MIT — free to use, modify and share.
