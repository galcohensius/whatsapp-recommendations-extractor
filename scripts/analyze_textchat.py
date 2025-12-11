"""Quick analyzer for TextContext lengths in data/extracted.json."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
import time

DEBUG_LOG = Path(r"c:\Dev\whatsapp-recommendations-extractor\.cursor\debug.log")


def log(payload: dict) -> None:
    try:
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main() -> None:
    start_ts = int(time.time() * 1000)
    data_path = Path("data/extracted_vcf_and_text.json")
    if not data_path.exists():
        log(
            {
                "sessionId": "debug-session",
                "runId": "textchat-stats",
                "hypothesisId": "H_len",
                "location": "scripts/analyze_textchat.py:main",
                "message": "missing data/extracted.json",
                "data": {},
                "timestamp": start_ts,
            }
        )
        return

    records = json.loads(data_path.read_text(encoding="utf-8"))
    lengths = []
    max_entry = {"len": -1, "TextContext": ""}
    for rec in records:
        txt = rec.get("TextContext", "") or ""
        l = len(txt)
        lengths.append(l)
        if l > max_entry["len"]:
            max_entry = {"len": l, "TextContext": txt[:400]}

    summary = {
        "count": len(lengths),
        "avg_len": mean(lengths) if lengths else 0,
        "max_len": max_entry["len"],
        "max_sample": max_entry["TextContext"],
    }
    log(
        {
            "sessionId": "debug-session",
            "runId": "textchat-stats",
            "hypothesisId": "H_len",
            "location": "scripts/analyze_textchat.py:main",
            "message": "TextChat length stats",
            "data": summary,
            "timestamp": int(time.time() * 1000),
        }
    )


if __name__ == "__main__":
    main()

