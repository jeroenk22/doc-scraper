# 📚 Doc Scraper

A tool that crawls **login-protected documentation sites** and exports everything to:

- 📄 **PDF** — nicely formatted, for human reading
- 📝 **Markdown** — clean plain text, ideal for feeding into AI tools like Claude

Works by using your browser cookies to authenticate, so you don't need to share passwords.

---

## ✨ Features

- Crawls all linked pages recursively within the same documentation section
- Preserves headings, paragraphs, bullet points and code blocks
- Skips navigation, sidebars and other noise
- Generates a clean Markdown file optimised for AI consumption
- Generates a styled PDF with cover page for human reading
- Fully reusable — just swap the URL and cookies for any other site

---

## 🔧 Requirements

- Python 3.8 or higher
- pip (comes with Python)

---

## 📦 Installation

**1. Clone this repository**

```bash
git clone https://github.com/your-username/doc-scraper.git
cd doc-scraper
```

**2. Install dependencies**

```bash
pip install requests beautifulsoup4 reportlab lxml
```

---

## 🍪 Step 1 — Export your cookies

You need to export your browser cookies so the scraper can access pages that require login.

1. Install the **Cookie-Editor** browser extension:
   - [Chrome](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
   - [Firefox](https://addons.mozilla.org/firefox/addon/cookie-editor/)

2. Open your browser and **log in** to the documentation site

3. Click the Cookie-Editor icon in your browser toolbar

4. Click **Export** (the export icon at the bottom)

5. Save the result as a `.json` file, e.g. `cookies.json`

---

## 🚀 Usage

```bash
python doc_scraper.py --url <start_url> --cookies <cookies.json> --output <output_name> --title "My Documentation"
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--url` | ✅ Yes | The starting URL of the documentation page |
| `--cookies` | ✅ Yes | Path to your Cookie-Editor JSON export |
| `--output` | No | Output filename without extension (default: `documentatie`) |
| `--title` | No | Title shown on the PDF cover page (default: `API Documentatie`) |
| `--max-pages` | No | Maximum number of pages to crawl (default: `200`) |

### Example

```bash
python doc_scraper.py \
  --url "https://docs.example.com/api/getting-started" \
  --cookies cookies.json \
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
└── cookies.json     # Your exported cookies (don't commit this!)
```

> ⚠️ **Never commit your `cookies.json` to GitHub.** Add it to `.gitignore`.

---

## 🔒 .gitignore

Create a `.gitignore` file to prevent accidentally pushing your cookies:

```
cookies.json
*.json
output/
*.pdf
*.md
!README.md
```

---

## ❓ Troubleshooting

**"0 pages found"**
- Make sure you are logged in before exporting cookies
- Check that the URL is correct and accessible in your browser
- Try exporting cookies again — they may have expired

**"HTTP 403 or 401"**
- Your session has expired. Log in again and re-export cookies.

**PDF looks wrong / missing content**
- Some sites use JavaScript to render content. This tool works best with server-rendered HTML documentation (Confluence, Notion export, wiki-style sites).

---

## 📄 License

MIT — free to use, modify and share.
