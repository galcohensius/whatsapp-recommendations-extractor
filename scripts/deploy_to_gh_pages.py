#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy web files to GitHub Pages docs folder.

This script copies the web interface files to the docs/ folder
so they can be served by GitHub Pages.
"""

import shutil
import sys
from pathlib import Path
from typing import Optional


def deploy_to_gh_pages(project_root: Optional[Path] = None, auto_commit: bool = False) -> bool:
    """Deploy web files to GitHub Pages docs folder.
    
    Args:
        project_root: Project root directory (defaults to parent of scripts/)
        auto_commit: If True, automatically commit and push changes (default: False)
    
    Returns:
        True if deployment successful, False otherwise
    """
    if project_root is None:
        # Assume script is in scripts/ directory
        project_root = Path(__file__).parent.parent
    
    web_dir = project_root / 'web'
    docs_dir = project_root / 'docs'
    
    # Ensure docs directory exists
    docs_dir.mkdir(exist_ok=True)
    
    # Only copy recommendations.json (index.html is edited directly in docs/)
    print("="*70)
    print("DEPLOYING TO GITHUB PAGES")
    print("="*70)
    print(f"\nSource: {web_dir}/recommendations.json")
    print(f"Destination: {docs_dir}\n")
    
    # Ensure docs directory exists
    docs_dir.mkdir(exist_ok=True)
    
    # Copy only recommendations.json
    src_file = web_dir / 'recommendations.json'
    dst_file = docs_dir / 'recommendations.json'
    
    if not src_file.exists():
        print(f"⚠️  Warning: {src_file} not found!")
        print(f"   Make sure you've run the extraction first: python main.py")
        return False
    
    try:
        shutil.copy2(src_file, dst_file)
        print(f"✓ Copied: recommendations.json → docs/recommendations.json")
        copied_files = ['recommendations.json']
    except Exception as e:
        print(f"✗ Error copying recommendations.json: {e}")
        return False
    
    # Verify docs/index.html exists
    if not (docs_dir / 'index.html').exists():
        print(f"\n⚠️  Warning: docs/index.html not found!")
        print(f"   Make sure docs/index.html exists (it should be committed to git)")
        return False
    
    print(f"✓ Verified: docs/index.html exists")
    
    print(f"\n✓ Successfully updated recommendations.json in docs/")
    
    # Auto-commit if requested
    if auto_commit:
        print("\n" + "="*70)
        print("COMMITTING CHANGES")
        print("="*70)
        
        try:
            import subprocess
            
            # Check if git is available
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("⚠️  Git not found. Skipping auto-commit.")
                print("   Please commit manually: git add docs/ && git commit -m 'Update GitHub Pages'")
                return True
            
            # Add files
            subprocess.run(['git', 'add', 'docs/'], check=True, cwd=project_root)
            print("✓ Added docs/ to git staging")
            
            # Commit
            subprocess.run(['git', 'commit', '-m', 'Update GitHub Pages deployment'], 
                         check=True, cwd=project_root)
            print("✓ Committed changes")
            
            # Push
            subprocess.run(['git', 'push'], check=True, cwd=project_root)
            print("✓ Pushed to remote repository")
            print("\n✓ Deployment complete! Your site will be available shortly.")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Error during git operations: {e}")
            print("   Please commit and push manually:")
            print("   git add docs/")
            print("   git commit -m 'Update GitHub Pages'")
            print("   git push")
            return False
        except Exception as e:
            print(f"⚠️  Unexpected error: {e}")
            return False
    else:
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\nFiles are ready in docs/ folder.")
        print("To publish:")
        print("  1. Commit: git add docs/ && git commit -m 'Update GitHub Pages'")
        print("  2. Push: git push")
        print("  3. Your site will be available at: https://<username>.github.io/<repo-name>/")
    
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Deploy web files to GitHub Pages docs folder'
    )
    parser.add_argument('--auto-commit', action='store_true',
                       help='Automatically commit and push changes')
    args = parser.parse_args()
    
    success = deploy_to_gh_pages(auto_commit=args.auto_commit)
    sys.exit(0 if success else 1)

