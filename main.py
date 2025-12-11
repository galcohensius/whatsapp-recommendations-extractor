#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local-only runner for extracting recommendations from local data."""

import argparse
from pathlib import Path

from src.extraction import run_extraction


def main():
    """CLI entry point for local-only extraction workflow."""
    parser = argparse.ArgumentParser(
        description='WhatsApp Recommendations Extractor - Local Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--data-dir', type=Path, default=None, help='Path to the input data directory (default: data/)')
    parser.add_argument('--no-save', action='store_true', help='Do not write extracted.json to disk (still prints summary)')
    parser.add_argument('--enrich', action='store_true', help='After extraction, call OpenAI to fill Service/Context and write enriched.json')

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("WHATSAPP RECOMMENDATIONS EXTRACTOR (LOCAL)")
    print("=" * 70)

    data_dir = Path(args.data_dir or 'data')
    records, outputs = run_extraction(
        data_dir=data_dir,
        save=not args.no_save,
    )

    print(f"\nExtracted {len(records)} records from {data_dir}")
    if args.no_save:
        print("JSON not saved (run without --no-save to persist separate files).")
    else:
        if outputs.get("combined"):
            print(f"Combined JSON: {outputs['combined']}")
        if outputs.get("vcf"):
            print(f"VCF JSON: {outputs['vcf']}")

    # Optional enrichment step
    if args.enrich:
        try:
            from src.ai_enrich import enrich_file
            import subprocess, sys
            from src.prepare_ready_to_upload import prepare_ready_to_upload
        except ImportError as exc:
            raise SystemExit(f"Enrichment failed: {exc}")
        enriched_path = enrich_file(data_dir / "extracted_vcf_and_text.json", data_dir / "ai_enriched.json")
        print(f"Enriched JSON: {enriched_path}")
        try:
            prepared_path = data_dir / "ready_to_upload.json"
            prepare_ready_to_upload(data_dir / "ai_enriched.json", prepared_path)
            print(f"Ready-to-upload JSON: {prepared_path}")
        except Exception as exc:
            raise SystemExit(f"Prepare ready_to_upload failed: {exc}")
    


if __name__ == '__main__':
    main()
