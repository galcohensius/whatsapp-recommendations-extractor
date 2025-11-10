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

---

# Backend API Deployment (Render)

This section covers deploying the FastAPI backend to Render for processing uploads and storing results.

## Prerequisites

- Render account (free tier available)
- PostgreSQL database (included in Render free tier)
- OpenAI API key (for AI enhancement)

## Quick Start

1. **Push your code to GitHub** (if not already done)
2. **Connect repository to Render**
3. **Deploy using render.yaml** (automatic) or manual setup

## Deployment Options

### Option 1: Using render.yaml (Recommended)

1. Push `render.yaml` to your repository
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New** → **Blueprint**
4. Connect your GitHub repository
5. Render will automatically detect `render.yaml` and create services
6. Set environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `CORS_ORIGINS`: Your GitHub Pages URL (e.g., `https://galcohensius.github.io`)
7. Deploy!

### Option 2: Manual Setup

#### Step 1: Create PostgreSQL Database

1. Go to Render Dashboard → **New** → **PostgreSQL**
2. Name: `whatsapp-recommendations-db`
3. Plan: Free
4. Region: Choose closest to you
5. Click **Create Database**
6. Copy the **Internal Database URL** (you'll need this)

#### Step 2: Create Web Service

1. Go to Render Dashboard → **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `whatsapp-recommendations-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Add Environment Variables:
   - `DATABASE_URL`: (from PostgreSQL service, Internal Database URL)
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `CORS_ORIGINS`: `https://galcohensius.github.io,http://localhost:8000`
   - `SECRET_KEY`: (generate random string, e.g., `openssl rand -hex 32`)
5. Click **Create Web Service**

#### Step 3: Update Frontend API URL

1. Get your Render service URL (e.g., `https://whatsapp-recommendations-api.onrender.com`)
2. Update `docs/api.js`:
   ```javascript
   const API_BASE_URL = 'https://your-service-name.onrender.com';
   ```
3. Commit and push to GitHub Pages

## Environment Variables

Create `backend/.env` file for local development (copy from `backend/.env.example`):

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/whatsapp_recommendations
OPENAI_API_KEY=your-key-here
CORS_ORIGINS=http://localhost:8000
SECRET_KEY=your-secret-key-here
```

**Important:** Never commit `.env` file to git (it's in `.gitignore`)

## Database Migrations

On first deployment, the database tables are created automatically via `init_db()` in `backend/app.py`.

For manual migrations (if needed):

```bash
# Initialize Alembic (if not done)
cd backend
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

## Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up local PostgreSQL** (or use SQLite for testing):
   - Install PostgreSQL
   - Create database: `createdb whatsapp_recommendations`
   - Update `DATABASE_URL` in `.env`

3. **Run backend:**
   ```bash
   cd backend
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Update frontend API URL** in `docs/api.js`:
   ```javascript
   const API_BASE_URL = 'http://localhost:8000';
   ```

5. **Test upload:**
   - Open `docs/upload.html` in browser
   - Upload a zip file
   - Check results at `docs/results.html?session_id=...`

## API Endpoints

- `GET /api/health` - Health check
- `POST /api/upload` - Upload zip file (max 5MB)
- `GET /api/status/{session_id}` - Check processing status
- `GET /api/results/{session_id}` - Get processed results
- `GET /docs` - FastAPI auto-generated API documentation

## Configuration

### File Limits
- **Max file size**: 5MB (configurable in `backend/config.py`)
- **Processing timeout**: 30 minutes (configurable)
- **Results retention**: 1 day (configurable)

### Cleanup

Expired sessions and results are automatically cleaned up:
- Runs every hour via background task
- Deletes data older than retention period (1 day)

## Troubleshooting

### Database Connection Issues

- Verify `DATABASE_URL` is correct
- Check PostgreSQL service is running (Render dashboard)
- Ensure database exists and user has permissions

### CORS Errors

- Verify `CORS_ORIGINS` includes your frontend URL
- Check browser console for specific CORS errors
- Ensure backend URL is correct in `docs/api.js`

### Processing Timeout

- Large files may exceed 30-minute timeout
- Check session status: `GET /api/status/{session_id}`
- Consider increasing `PROCESSING_TIMEOUT` in `backend/config.py`

### OpenAI Enhancement Not Working

- Verify `OPENAI_API_KEY` is set correctly
- Check API key has sufficient credits
- Review backend logs for OpenAI API errors

## Monitoring

- **Render Dashboard**: View logs, metrics, and service status
- **FastAPI Docs**: Visit `https://your-service.onrender.com/docs` for interactive API docs
- **Health Check**: `https://your-service.onrender.com/api/health`

## Security Notes

- API keys are stored as environment variables (never in code)
- Results expire after 1 day automatically
- CORS is configured to only allow your GitHub Pages domain
- File uploads are validated (type and size)
- No rate limiting (as per requirements, but can be added if needed)

