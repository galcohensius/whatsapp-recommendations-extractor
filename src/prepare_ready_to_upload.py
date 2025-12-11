"""Prepare cleaned upload JSON from ai_enriched.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any


def build_final_context(rec: Dict[str, Any]) -> str:
    if rec.get("FinalContext"):
        return rec["FinalContext"]
    parts = []
    for key in ("vcfContext", "TextContext"):
        val = rec.get(key) or ""
        val = val.strip()
        if val:
            parts.append(val)
    return " | ".join(parts)


def clean_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for rec in records:
        service = (rec.get("Service") or "").strip()
        if not service:
            continue  # drop entries with no service
        rec["Service"] = service
        rec["FinalContext"] = build_final_context(rec)
        cleaned.append(rec)
    return cleaned


def prepare_ready_to_upload(input_path: Path, output_path: Path) -> int:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("ai_enriched.json must be a list")
    cleaned = clean_records(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cleaned)} records to {output_path}")
    return len(cleaned)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Prepare ready_to_upload.json")
    parser.add_argument("--input", type=Path, default=Path("data/ai_enriched.json"))
    parser.add_argument("--output", type=Path, default=Path("data/ready_to_upload.json"))
    args = parser.parse_args()
    prepare_ready_to_upload(args.input, args.output)


if __name__ == "__main__":
    main()

