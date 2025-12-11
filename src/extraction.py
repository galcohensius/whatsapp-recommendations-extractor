"""Extraction helpers for WhatsApp recommendations."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any
import re

FIELDS = ["Service", "Name", "Phone", "Date", "Recommender", "vcfContext", "FinalContext", "TextContext"]


@dataclass
class Recommendation:
    Service: str = ""
    Name: str = ""
    Phone: str = ""
    Date: str = ""
    Recommender: str = ""
    vcfContext: str = ""
    FinalContext: str = ""  # combine text+vcf context and AI reasoning
    TextContext: str = ""

    def to_dict(self) -> dict:
        return {field: getattr(self, field, "") for field in FIELDS}


def _clean_value(val: Optional[str]) -> str:
    if not val:
        return ""
    v = val.strip()
    if v.lower() in {"null", "none", "undefined"}:
        return ""
    return v


def _normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = phone.strip()
    if phone.startswith("+972 "):
        phone = "0" + phone[len("+972 "):]
    if phone.startswith("+972"):
        phone = "0" + phone[len("+972"):]
    return phone.replace(" ", "")


def _clean_message_text(text: str) -> str:
    """Remove timestamps/phones (already excluded), strip vcf suffixes, and drop bidi/zero-width noise."""
    if not text:
        return ""
    # Remove common Unicode control/bidi marks
    CONTROL_CHARS = dict.fromkeys(
        map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200b\u200c\u200d"),
        None,
    )
    t = text.translate(CONTROL_CHARS).strip()
    # Replace ".vcf (file attached)" or ".vcf" with just the stem
    if t.lower().endswith(".vcf (file attached)"):
        t = t[: -len(".vcf (file attached)")].strip()
    elif t.lower().endswith(".vcf"):
        t = t[: -len(".vcf")].strip()

    # Strip leading mention tokens like @~Name or @Name (common in WhatsApp exports)
    t = re.sub(r"^(?:@~?\S+\s*)+", "", t).strip()

    # Decode percent-encoded URLs to improve readability (keep full URL)
    def _strip_url(match: re.Match) -> str:
        url = match.group(0)
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(url)
            path = unquote(parsed.path)
            query = unquote(parsed.query)
            rebuilt = f"{parsed.scheme}://{parsed.netloc}{path}"
            if query:
                rebuilt += f"?{query}"
            return rebuilt
        except Exception:
            return url

    t = re.sub(r"https?://[^\s]+", _strip_url, t)
    return t


def extract_from_vcf(data_dir: Path) -> List[dict]:
    """Extract recommendations from VCF files under data_dir/vcf (VCF data only)."""
    records: List[dict] = []
    vcf_dir = data_dir / "vcf"
    for vcf_file in sorted(vcf_dir.rglob("*.vcf")) if vcf_dir.exists() else []:
        name = ""
        phone = ""
        org = ""
        title = ""
        note = ""
        email = ""
        url = ""
        address = ""
        date = ""
        try:
            content = vcf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("FN:"):
                name = _clean_value(line.partition("FN:")[2])
            elif line.startswith("N:") and not name:
                name = _clean_value(line.partition("N:")[2].replace(";", " "))
            elif line.upper().startswith("TEL"):
                phone = _normalize_phone(_clean_value(line.split(":", 1)[1] if ":" in line else line))
            elif line.upper().startswith("ORG"):
                org = _clean_value(line.split(":", 1)[1] if ":" in line else line)
            elif line.upper().startswith("TITLE"):
                title = _clean_value(line.split(":", 1)[1] if ":" in line else line)
            elif line.upper().startswith("EMAIL"):
                email = _clean_value(line.split(":", 1)[1] if ":" in line else line)
            elif line.upper().startswith("URL"):
                url = _clean_value(line.split(":", 1)[1] if ":" in line else line)
            elif line.upper().startswith("NOTE"):
                note = _clean_value(line.split(":", 1)[1] if ":" in line else line)
            elif line.upper().startswith("ADR"):
                address = _clean_value(line.split(":", 1)[1].replace(";", " ") if ":" in line else line)
            elif line.upper().startswith("BDAY") or line.upper().startswith("REV"):
                date = _clean_value(line.split(":", 1)[1] if ":" in line else line)

        context_bits = [_clean_value(org), _clean_value(title), _clean_value(note), _clean_value(email), _clean_value(url), _clean_value(address)]
        context = " | ".join(bit for bit in context_bits if bit)
        records.append(
            Recommendation(
                Service="",
                Name=name,
                Phone=phone,
                Date=date,
                Recommender="",
                vcfContext=context,
                FinalContext="",
                TextContext="",
            ).to_dict()
        )
    return records


def parse_chat_messages(data_dir: Path) -> List[Dict[str, Any]]:
    """Parse WhatsApp chat export into structured messages."""
    txt_dir = data_dir / "txt"
    wa_pattern = re.compile(
        r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2})\s+-\s+(?P<sender>[^:]+):\s+(?P<message>.*)$"
    )

    def looks_like_phone(s: str) -> bool:
        return bool(re.match(r"^\+?\d[\d\s\-]{6,}$", s.strip()))

    messages: List[Dict[str, Any]] = []
    for txt_file in sorted(txt_dir.rglob("*.txt")) if txt_dir.exists() else []:
        try:
            lines = txt_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            m = wa_pattern.match(line)
            if not m:
                # continuation; append to last message if exists
                if messages:
                    messages[-1]["text"] += " " + line
                continue

            sender = m.group("sender").strip()
            text = m.group("message").strip()
            attachments = [token for token in text.split() if token.lower().endswith(".vcf")]
            messages.append(
                {
                    "datetime": f"{m.group('date')} {m.group('time')}",
                    "sender": sender,
                    "sender_phone": sender if looks_like_phone(sender) else "",
                    "text": text,
                    "attachments": attachments,
                }
            )
    return messages


def enrich_with_chat_context(
    vcf_records: List[dict], messages: List[Dict[str, Any]]
) -> List[dict]:
    """For each vCard record, find matching chat message and add +-3 window to TextChat."""
    # Build index by attached filename
    index_by_filename: Dict[str, int] = {}
    for idx, msg in enumerate(messages):
        for att in msg.get("attachments", []):
            index_by_filename[att.lower()] = idx

    def matches(record: dict, msg: Dict[str, Any]) -> bool:
        phone = record.get("Phone", "").replace(" ", "")
        name = record.get("Name", "").lower()
        sender = msg["sender"].lower()
        text_lower = msg["text"].lower()
        phone_in_sender = phone and phone in msg.get("sender_phone", "").replace(" ", "")
        phone_in_text = phone and phone in text_lower.replace(" ", "")
        name_in_sender = name and name in sender
        name_in_text = name and name in text_lower
        return phone_in_sender or phone_in_text or name_in_sender or name_in_text

    enriched: List[dict] = []
    for rec in vcf_records:
        rec = dict(rec)  # work on a copy so raw VCF output stays untouched
        idx = None
        # First try filename match (if we saw an attachment)
        fname = f"{rec.get('Name','').strip().replace(' ', '_')}.vcf".lower()
        if fname in index_by_filename:
            idx = index_by_filename[fname]
        else:
            # Fallback: scan for name/phone match
            for i, msg in enumerate(messages):
                if matches(rec, msg):
                    idx = i
                    break
        if idx is not None:
            window = messages[max(0, idx - 3): idx + 4]
            rendered = []
            for m in window:
                body = _clean_message_text(m["text"])
                # Drop body if it matches the vCard name (duplicate of Name field)
                if body and body.strip() != rec.get("Name", "").strip():
                    rendered.append(body)
            rec["Recommender"] = _normalize_phone(messages[idx]["sender"])
            rec["Date"] = messages[idx]["datetime"]
            joined = " || ".join(rendered)
            MAX_CHAT = 800
            rec["TextContext"] = joined[:MAX_CHAT] if len(joined) > MAX_CHAT else joined
        enriched.append(rec)
    return enriched


def _write_json(records: Iterable[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(list(records), f, ensure_ascii=False, indent=2)
    return output_path


def run_extraction(
    data_dir: Path,
    save: bool = True,
    output_name: str = "extracted_vcf_and_text.json",
):
    """Run both extractors and optionally persist JSON.

    Returns:
        combined_records: list of all records
        outputs: dict with keys combined/vcf -> Path | None
    """
    data_dir = data_dir.resolve()
    messages = parse_chat_messages(data_dir)
    vcf_records = extract_from_vcf(data_dir)
    combined = enrich_with_chat_context(vcf_records, messages)

    outputs = {"combined": None, "vcf": None}
    if save:
        outputs["combined"] = _write_json(combined, data_dir / output_name)
        outputs["vcf"] = _write_json(vcf_records, data_dir / "extracted_vcf.json")

    return combined, outputs

