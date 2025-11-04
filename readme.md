# WhatsApp Recommendations Extractor

A tool to extract recommendations from WhatsApp chat messages and VCF contact files, then display them in an interactive, searchable web interface.

## Features

- 📱 **Extract from WhatsApp chats**: Parses WhatsApp chat exports (.txt files)
- 📇 **Process VCF contacts**: Extracts contact information from .vcf files
- 🔍 **Interactive web interface**: Searchable, filterable table with Hebrew support
- 📞 **Click-to-call**: Phone numbers are clickable links

## Usage

### 1. Extract Recommendations

Run the main script to process WhatsApp chats and VCF files:

```bash
python main.py
```

This will:
- Parse all `.vcf` files from `data/vcf/`
- Parse WhatsApp chat from `data/txt/`
- Generate `web/recommendations.json`

### 2. Advanced Options

Use the main script for the complete workflow:

```bash
# Run full workflow (extract, fix, analyze)
python main.py

# With OpenAI enhancement
python main.py --use-openai

# Deploy to GitHub Pages after extraction
python main.py --deploy
```

See `python main.py --help` for all options.

## Running the Web Interface

### Local Viewing

To view the interactive web interface locally, run a local server:

```bash
# From project root
cd docs
python -m http.server 8000
```
Then navigate to: `http://localhost:8000`

**Note:** Edit `docs/index.html` directly to customize the interface.

### Public Deployment (GitHub Pages)

To share the interface publicly via GitHub Pages:

```bash
# Run full workflow and deploy
python main.py --deploy

# Or deploy manually after extraction
python scripts/deploy_to_gh_pages.py
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions.

After deployment, your site will be available at:
```
https://<your-username>.github.io/<repository-name>/
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Place your data files:
   - WhatsApp chat exports in `data/txt/`
   - VCF contact files in `data/vcf/`

3. Run the main script to generate the recommendations:
   ```bash
   python main.py
   ```
