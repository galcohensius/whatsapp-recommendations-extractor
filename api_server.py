"""
FastAPI backend for WhatsApp recommendations extractor.

Endpoints:
- POST /api/upload: upload a ZIP, create session, kick off processing
- GET  /api/status/{session_id}: fetch session status
- GET  /api/results/{session_id}: fetch processed recommendations

Persists session metadata and results JSON in Supabase Postgres.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.extraction import run_extraction
from src.prepare_ready_to_upload import prepare_ready_to_upload
from src.ai_enrich import enrich_file

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_TABLE = "sessions"
USE_OPENAI_ENRICH = os.getenv("USE_OPENAI", "false").lower() == "true"

DATA_ROOT = Path("data")
SESSIONS_ROOT = DATA_ROOT / "sessions"
RESULT_EXPIRY_DAYS = int(os.getenv("RESULT_EXPIRY_DAYS", "7"))

# ---------------------------------------------------------------------------
# FastAPI setup
# ---------------------------------------------------------------------------

app = FastAPI(title="WhatsApp Recommendations Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=500,
            detail="Supabase credentials are missing (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).",
        )


def _supabase_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _default_expiry() -> datetime:
    return _now_utc() + timedelta(days=RESULT_EXPIRY_DAYS)


def _normalize_records(records: List[Dict[str, Any]], preview_mode: bool) -> List[Dict[str, Any]]:
    """Map extractor output to frontend shape."""
    normalized: List[Dict[str, Any]] = []
    for rec in records:
        normalized.append(
            {
                "service": rec.get("Service", "") or "",
                "name": rec.get("Name", "") or "",
                "phone": rec.get("Phone", "") or "",
                "date": rec.get("Date", "") or "",
                "recommender": rec.get("Recommender", "") or "",
                "context": rec.get("FinalContext")
                or rec.get("TextContext")
                or rec.get("vcfContext")
                or "",
            }
        )
    if preview_mode and len(normalized) > 150:
        # keep most recent-ish items (end of list assumes chronological append)
        normalized = normalized[-150:]
    return normalized


def _load_result_records(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Prefer cleaned ready_to_upload.json, otherwise ai_enriched.json, otherwise combined extraction output.
    """
    ready_path = data_dir / "ready_to_upload.json"
    ai_path = data_dir / "ai_enriched.json"
    extracted_path = data_dir / "extracted_vcf_and_text.json"

    if ready_path.exists():
        return json.loads(ready_path.read_text(encoding="utf-8"))
    if ai_path.exists():
        return json.loads(ai_path.read_text(encoding="utf-8"))
    if extracted_path.exists():
        return json.loads(extracted_path.read_text(encoding="utf-8"))
    return []


def _move_files_to_data_dir(extracted_dir: Path, data_dir: Path) -> None:
    """Move .txt files to data_dir/txt and .vcf to data_dir/vcf."""
    txt_dir = data_dir / "txt"
    vcf_dir = data_dir / "vcf"
    txt_dir.mkdir(parents=True, exist_ok=True)
    vcf_dir.mkdir(parents=True, exist_ok=True)

    for path in extracted_dir.rglob("*"):
        if path.is_dir():
            continue
        target = None
        if path.suffix.lower() == ".txt":
            target = txt_dir / path.name
        elif path.suffix.lower() == ".vcf":
            target = vcf_dir / path.name
        if target:
            target.write_bytes(path.read_bytes())


def _session_dir(session_id: str) -> Path:
    return SESSIONS_ROOT / session_id


async def supabase_upsert_session(row: Dict[str, Any]) -> None:
    _require_supabase()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            headers=_supabase_headers(),
            content=json.dumps(row),
        )
        if resp.status_code >= 300:
            raise HTTPException(
                status_code=500,
                detail=f"Supabase upsert failed: {resp.status_code} {resp.text}",
            )


async def supabase_update_session(session_id: str, updates: Dict[str, Any]) -> None:
    _require_supabase()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?session_id=eq.{session_id}",
            headers=_supabase_headers(),
            content=json.dumps(updates),
        )
        if resp.status_code >= 300:
            raise HTTPException(
                status_code=500,
                detail=f"Supabase update failed: {resp.status_code} {resp.text}",
            )


async def supabase_fetch_session(session_id: str) -> Optional[Dict[str, Any]]:
    _require_supabase()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?session_id=eq.{session_id}&limit=1",
            headers=_supabase_headers(),
        )
        if resp.status_code >= 300:
            raise HTTPException(
                status_code=500,
                detail=f"Supabase fetch failed: {resp.status_code} {resp.text}",
            )
        data = resp.json()
        if not data:
            return None
        return data[0]


async def supabase_cleanup_expired() -> None:
    """Delete expired sessions from Supabase."""
    _require_supabase()
    now_iso = _now_utc().isoformat()
    async with httpx.AsyncClient(timeout=20) as client:
        await client.delete(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?expires_at=lt.{now_iso}",
            headers=_supabase_headers(),
        )


async def _process_session(session_id: str, file_name: str, preview_mode: bool) -> None:
    data_dir = _session_dir(session_id)
    raw_dir = data_dir / "raw"
    zip_path = raw_dir / "upload.zip"
    try:
        # Extract zip
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(raw_dir)

        _move_files_to_data_dir(raw_dir, data_dir)

        combined, outputs = run_extraction(data_dir=data_dir, save=True)

        extracted_path = outputs.get("combined") or (data_dir / "extracted_vcf_and_text.json")
        ai_enriched_path = data_dir / "ai_enriched.json"
        ready_path = data_dir / "ready_to_upload.json"
        openai_enhanced = False

        # Optional OpenAI enrichment (mirrors main.py --enrich)
        if USE_OPENAI_ENRICH and extracted_path and extracted_path.exists():
            try:
                await supabase_update_session(
                    session_id,
                    {"progress_message": "Enriching with OpenAI..."},
                )
                enrich_file(extracted_path, ai_enriched_path)
                openai_enhanced = True
            except Exception as exc:
                await supabase_update_session(
                    session_id,
                    {
                        "progress_message": f"Enrichment skipped: {exc}",
                    },
                )

        # Attempt to produce ready_to_upload.json
        if ai_enriched_path.exists():
            try:
                prepare_ready_to_upload(ai_enriched_path, ready_path)
            except Exception:
                # Non-fatal; fallback to existing data
                pass

        records = _load_result_records(data_dir) or combined
        normalized = _normalize_records(records, preview_mode=preview_mode)

        # Store results locally
        result_path = data_dir / "ai_enriched.json"
        result_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

        # Persist to Supabase
        await supabase_update_session(
            session_id,
            {
                "status": "completed",
                "result_json": normalized,
                "result_url": None,
                "openai_enhanced": openai_enhanced,
                "progress_message": "Completed",
            },
        )
    except Exception as exc:
        await supabase_update_session(
            session_id,
            {
                "status": "error",
                "error_message": str(exc),
                "progress_message": "Error during processing",
            },
        )
        raise
    finally:
        # optional: clean raw extracted files but keep result
        if raw_dir.exists():
            shutil.rmtree(raw_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/api/upload")
async def upload_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    preview_mode: bool = True,
):
    _require_supabase()

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    session_id = uuid.uuid4().hex
    session_dir = _session_dir(session_id)
    raw_dir = session_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    zip_path = raw_dir / "upload.zip"
    with zip_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create session record
    await supabase_upsert_session(
        {
            "session_id": session_id,
            "status": "processing",
            "zip_name": file.filename,
            "preview_mode": preview_mode,
            "progress_message": "Processing files...",
            "expires_at": _default_expiry().isoformat(),
        }
    )

    # Kick off background processing
    background_tasks.add_task(_process_session, session_id, file.filename, preview_mode)

    return {"session_id": session_id, "status": "processing"}


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    session = await supabase_fetch_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": session.get("status", "unknown"),
        "error_message": session.get("error_message"),
        "progress_message": session.get("progress_message"),
        "expires_at": session.get("expires_at"),
        "openai_enhanced": session.get("openai_enhanced", False),
    }


@app.get("/api/results/{session_id}")
async def get_results(session_id: str):
    session = await supabase_fetch_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    status = session.get("status")
    if status != "completed":
        # Mirror frontend expectations: return 202 while still processing
        return JSONResponse(
            status_code=202,
            content={"detail": f"Processing not complete (status={status})"},
        )

    expires_at = session.get("expires_at")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp_dt < _now_utc():
                raise HTTPException(status_code=410, detail="Results have expired")
        except ValueError:
            pass

    result_json = session.get("result_json") or []
    return {
        "recommendations": result_json,
        "openai_enhanced": session.get("openai_enhanced", False),
        "created_at": session.get("created_at"),
    }


# ---------------------------------------------------------------------------
# Background cleanup loop
# ---------------------------------------------------------------------------


async def _cleanup_loop():
    """Periodic cleanup of expired sessions in Supabase."""
    while True:
        try:
            await supabase_cleanup_expired()
        except Exception:
            # Log to stdout; keep loop alive
            pass
        await asyncio.sleep(6 * 60 * 60)  # every 6 hours


@app.on_event("startup")
async def startup_event():
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        asyncio.create_task(_cleanup_loop())

