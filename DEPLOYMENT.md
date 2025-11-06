# GitHub Pages Deployment Guide

**Live site:** [https://galcohensius.github.io/whatsapp-recommendations-extractor/](https://galcohensius.github.io/whatsapp-recommendations-extractor/)

This guide explains how to deploy the recommendations web interface to GitHub Pages so it's publicly accessible.

## Quick Start

After running `python main.py` to generate recommendations, deploy with:

```bash
python main.py --deploy
```

Or manually:

```bash
python scripts/deploy_to_gh_pages.py
```

## Initial Setup (One-Time)

### Step 1: Enable GitHub Pages

1. Go to your GitHub repository
2. Click **Settings** → **Pages** (in the left sidebar)
3. Under **Source**, select:
   - **Branch**: `main` (or your default branch)
   - **Folder**: `/docs`
4. Click **Save**

### Step 2: First Deployment

1. Run the deployment script:
   ```bash
   python scripts/deploy_to_gh_pages.py
   ```

2. Commit and push the changes:
   ```bash
   git add docs/
   git commit -m "Initial GitHub Pages deployment"
   git push
   ```

3. Wait a few minutes for GitHub Pages to build
4. Your site will be available at:
   ```
   https://<your-username>.github.io/<repository-name>/
   ```

   For this project, the deployed site is:
   [https://galcohensius.github.io/whatsapp-recommendations-extractor/](https://galcohensius.github.io/whatsapp-recommendations-extractor/)

## Automatic Deployment

### Option 1: Using main.py

Include `--deploy` flag when running the main workflow:

```bash
# Extract, fix, analyze, and deploy
python main.py --deploy

# With auto-commit (automatically commits and pushes)
python main.py --deploy --auto-commit
```

### Option 2: Manual Deployment Script

Run the deployment script directly:

```bash
# Basic deployment (copies files, you commit manually)
python scripts/deploy_to_gh_pages.py

# With auto-commit (commits and pushes automatically)
python scripts/deploy_to_gh_pages.py --auto-commit
```

## Update Workflow

After updating recommendations, redeploy:

1. **Generate new recommendations:**
   ```bash
   python main.py
   ```

2. **Deploy updates:**
   ```bash
   python main.py --deploy --auto-commit
   ```

Or manually:
   ```bash
   python scripts/deploy_to_gh_pages.py --auto-commit
   git push  # If auto-commit didn't push
   ```

## What Gets Deployed

The deployment script copies:
- `web/recommendations.json` → `docs/recommendations.json`

**Note:** 
- `docs/index.html` is edited directly (not copied from web/)
- Only `recommendations.json` is updated during deployment
- Backup files and OpenAI responses remain private

## Custom Domain (Optional)

To use a custom domain:

1. Add a `CNAME` file in `docs/` with your domain:
   ```
   recommendations.example.com
   ```

2. Configure DNS settings at your domain registrar
3. Update GitHub Pages settings to show your custom domain

## Troubleshooting

### Site not updating?

- Wait 1-2 minutes after pushing (GitHub Pages rebuilds automatically)
- Check GitHub repository → **Actions** tab for build status
- Verify `docs/` folder contains `index.html` and `recommendations.json`

### 404 Error?

- Ensure GitHub Pages is configured to use `/docs` folder
- Check that `docs/index.html` exists and is committed
- Verify the repository is public (or you have GitHub Pro/Team for private repos)

### Files not copying?

- Ensure `web/index.html` and `web/recommendations.json` exist
- Check file permissions
- Run the script with verbose output to see errors

## Privacy Considerations

⚠️ **Important:** The deployed site is **publicly accessible**. 

- All recommendations data will be visible to anyone with the link
- Phone numbers will be visible (though clickable for privacy)
- Consider if this is appropriate for your use case

To keep data private:
- Use the local server instead: `cd web && python -m http.server 8000`
- Or set up a private repository with GitHub Pro/Team

## Advanced: GitHub Actions Auto-Deploy

For automatic deployment on every push to main, see `.github/workflows/deploy.yml` (if created).

