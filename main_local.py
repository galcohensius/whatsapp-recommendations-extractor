#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local-only runner that reuses main.py workflow helpers (no deploy/git)."""

import argparse
import sys
from pathlib import Path

# Reuse main.py helpers
from main import (
    run_extraction,
    run_pre_enhancement_cleanup,
    run_ai_enhancement,
    run_post_enhancement_cleanup,
    run_analysis,
    print_next_steps,
)


def main():
    """CLI entry point for local-only workflow."""
    parser = argparse.ArgumentParser(
        description='WhatsApp Recommendations Extractor - Local Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--use-openai', action='store_true', help='Use OpenAI API to enhance recommendations (requires api_key.txt or env var)')
    parser.add_argument('--openai-model', type=str, default='gpt-4o-mini',
                       choices=['gpt-5', 'gpt-4.1', 'o4-mini', 'gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
                       help='OpenAI model to use (default: gpt-4o-mini)')
    parser.add_argument('--skip-fix', action='store_true', help='Skip cleanup steps')
    parser.add_argument('--skip-analysis', action='store_true', help='Skip analysis step')

    args = parser.parse_args()

    # Local workflow: extract -> optional clean -> optional AI -> final clean -> optional analysis
    print("\n" + "=" * 70)
    print("WHATSAPP RECOMMENDATIONS EXTRACTOR (LOCAL)")
    print("=" * 70)

    # Step 1: Extraction (always)
    run_extraction()

    # Step 2: Pre-cleanup
    if not args.skip_fix:
        run_pre_enhancement_cleanup()

    # Step 3: Optional AI + post-cleanup
    if args.use_openai:
        run_ai_enhancement(openai_model=args.openai_model)
        if not args.skip_fix:
            run_post_enhancement_cleanup()
    elif not args.skip_fix:
        run_post_enhancement_cleanup()

    # Step 4: Analysis
    if not args.skip_analysis:
        run_analysis(analyze_after=True)

    print_next_steps(deployed=False)


if __name__ == '__main__':
    main()


