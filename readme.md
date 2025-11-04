# WhatsApp Recommendations Extractor

A tool to extract recommendations from WhatsApp chat messages and VCF contact files, then display them in an interactive, searchable web interface.

## Features

- 📱 **Extract from WhatsApp chats**: Parses WhatsApp chat exports (.txt files)
- 📇 **Process VCF contacts**: Extracts contact information from .vcf files
- 🔍 **Interactive web interface**: Searchable, filterable table with Hebrew support
- 📞 **Click-to-call**: Phone numbers are clickable links

## Usage

### 1. Extract Recommendations

Run the extraction script to process WhatsApp chats and VCF files:

```bash
python src/extract_recommendations.py
```

This will:
- Parse all `.vcf` files from `data/vcf/`
- Parse WhatsApp chat from `data/txt/`
- Generate `web/recommendations.json`

### 2. Clean Up Recommendations

If you need to clean up invalid entries (e.g., URL parameters captured as names):

```bash
python src/cleanup_recommendations.py
```

## Running the Web Interface

To view the interactive web interface, you need to run a local server (the page loads data from `recommendations.json`).

```bash
# From project root
python -m http.server 8000
```
Then navigate to: `http://localhost:8000/web/`

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Place your data files:
   - WhatsApp chat exports in `data/txt/`
   - VCF contact files in `data/vcf/`

3. Run the extraction script to generate the recommendations.
