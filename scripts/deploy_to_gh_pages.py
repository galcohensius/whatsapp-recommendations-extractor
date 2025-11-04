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


def deploy_to_gh_pages(project_root: Path = None, auto_commit: bool = False) -> bool:
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
    
    # Files to copy
    files_to_copy = [
        ('index.html', 'index.html'),
        ('recommendations.json', 'recommendations.json')
    ]
    
    print("="*70)
    print("DEPLOYING TO GITHUB PAGES")
    print("="*70)
    print(f"\nSource: {web_dir}")
    print(f"Destination: {docs_dir}\n")
    
    # Copy files
    copied_files = []
    for src_name, dst_name in files_to_copy:
        src_file = web_dir / src_name
        dst_file = docs_dir / dst_name
        
        if not src_file.exists():
            print(f"⚠️  Warning: {src_file} not found, skipping...")
            continue
        
        try:
            shutil.copy2(src_file, dst_file)
            copied_files.append(dst_name)
            print(f"✓ Copied: {src_name} → docs/{dst_name}")
        except Exception as e:
            print(f"✗ Error copying {src_name}: {e}")
            return False
    
    if not copied_files:
        print("⚠️  No files were copied. Check if source files exist.")
        return False
    
    print(f"\n✓ Successfully deployed {len(copied_files)} file(s) to docs/")
    
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

