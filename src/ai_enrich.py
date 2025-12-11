"""AI enrichment for WhatsApp recommendations."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any

import httpx

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"
MAX_RETRIES = 3
RETRY_DELAY = 2.0
# Smaller batches to reduce latency/timeout risk
BATCH_SIZE = 5
REQUEST_TIMEOUT = 180

def _load_api_key() -> str:
    key_path = Path("api_key.txt")
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    raise RuntimeError("OpenAI API key not found. Set OPENAI_API_KEY or provide api_key.txt")


def _load_project_id() -> str:
    project = os.environ.get("OPENAI_PROJECT")
    if project:
        return project.strip()
    project_path = Path("openai_project.txt")
    if project_path.exists():
        return project_path.read_text(encoding="utf-8").strip()
    return ""


SYSTEM_PROMPT = """You are a precise extractor. Given records with fields Service, Name, Phone, Date, Recommender, vcfContext, FinalContext, TextContext, fill only:
- Service: a single Hebrew occupation/role word (e.g., אינסטלטור, חשמלאי, טכנאי גז, טכנאי מזגנים, נהג, נגר). Do NOT output generic 'טכנאי' alone. 
- FinalContext: concise, relevant details from vcfContext/TextContext (e.g., specialty, location, materials, availability). No generic praise/marketing (avoid 'מומלץ', 'great', etc.).
Return the updated records as JSON array, preserving all original fields and values that are not being filled.
If you cannot determine Service, leave it empty. If no relevant context, leave FinalContext empty."""


def _chunk(records: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


KEYWORD_SERVICE_MAP = [
    ("גז", "טכנאי גז"),
    ("מזגן", "טכנאי מזגנים"),
    ("מזגנים", "טכנאי מזגנים"),
    ("קירור", "טכנאי מקררים"),
    ("מקרר", "טכנאי מקררים"),
    ("מקררים", "טכנאי מקררים"),
    ("אינסטל", "אינסטלטור"),
    ("דליפה", "אינסטלטור"),
    ("צנרת", "אינסטלטור"),
    ("ביוב", "אינסטלטור"),
    ("חשמל", "חשמלאי"),
    ("תמי 4", "טכנאי מטהרי מים"),
    ("מטהר מים", "טכנאי מטהרי מים"),
    ("מים", "אינסטלטור"),
    ("סיבים", "טכנאי אינטרנט"),
    ("אינטרנט", "טכנאי אינטרנט"),
    ("ראוטר", "טכנאי אינטרנט"),
    ("רשת", "טכנאי אינטרנט"),
    ("מחשב", "טכנאי מחשבים"),
    ("מחשבים", "טכנאי מחשבים"),
    ("קבלן", "קבלן"),
    ("בניה", "קבלן"),
    ("שיפוץ", "קבלן שיפוצים"),
    ("שיפוצים", "קבלן שיפוצים"),
    ("שיפוצניק", "קבלן שיפוצים"),
]


def _refine_service(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic to avoid generic 'טכנאי' by inferring trade from context."""
    svc = (rec.get("Service") or "").strip()
    if svc and svc != "טכנאי":
        return rec
    haystack = " ".join(
        str(rec.get(k, "") or "") for k in ("TextContext", "FinalContext", "vcfContext")
    ).lower()
    for needle, replacement in KEYWORD_SERVICE_MAP:
        if needle in haystack:
            rec["Service"] = replacement
            return rec
    # Leave as-is (may be empty or generic)
    return rec


def _enrich_batch(api_key: str, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    project_id = _load_project_id()
    if project_id:
        headers["OpenAI-Project"] = project_id
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(batch, ensure_ascii=False),
            },
        ],
        "temperature": 0.2,
    }
    resp = httpx.post(OPENAI_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.text[:500]
        except Exception:
            pass
        raise httpx.HTTPStatusError(
            f"{exc}. Response body (truncated): {detail}",
            request=exc.request,
            response=exc.response,
        ) from None
    payload_json = resp.json()
    content = payload_json["choices"][0]["message"]["content"]
    if not content or not str(content).strip():
        raise RuntimeError(f"Empty completion content. Raw response (truncated): {str(payload_json)[:400]}")
    cleaned = str(content).strip()
    # Remove Markdown fences if present
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
        # drop trailing fence
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        snippet = cleaned[:400]
        raise RuntimeError(f"Failed to parse model output as JSON: {exc}. Content (truncated): {snippet}") from None


def enrich_file(input_path: Path, output_path: Path) -> Path:
    api_key = _load_api_key()
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of records")

    enriched: List[Dict[str, Any]] = []
    batches = _chunk(data, BATCH_SIZE)
    total = len(batches)
    start_time = time.time()
    for idx, batch in enumerate(batches, start=1):
        batch_start = time.time()
        print(f"[enrich] batch {idx}/{total} (size {len(batch)})...")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                enriched_batch = [_refine_service(rec) for rec in _enrich_batch(api_key, batch)]
                enriched.extend(enriched_batch)
                break
            except Exception:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(RETRY_DELAY * attempt)
        elapsed_batch = time.time() - batch_start
        print(f"[enrich] done batch {idx}/{total} in {elapsed_batch:.1f}s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed_total = time.time() - start_time
    print(f"[enrich] wrote {len(enriched)} records to {output_path} in {elapsed_total:.1f}s")
    return output_path


