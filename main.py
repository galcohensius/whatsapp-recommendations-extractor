#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for WhatsApp Recommendations Extractor

This script orchestrates the entire workflow:
1. Extract recommendations from data files
2. (Optional) Fix/clean recommendations
3. (Optional) Analyze recommendations
4. Display summary and next steps
"""

import sys
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


def run_extraction(use_openai: bool = False, openai_model: str = 'gpt-4o-mini'):
    """Run the main extraction script."""
    print("="*70)
    print("STEP 1: EXTRACTING RECOMMENDATIONS")
    print("="*70)
    
    from extract_recommendations import extract_recommendations
    from pathlib import Path
    
    project_root = Path(__file__).parent
    
    # Call the core extraction function (skip analysis, will run after fixes)
    extract_recommendations(
        use_openai=use_openai,
        openai_model=openai_model,
        project_root=project_root,
        run_analysis=False  # Skip analysis here, will run after fixes
    )
    
    print("\n" + "="*70)
    print("✓ Extraction complete!")
    print("="*70)


def run_fix(fix_after_extraction: bool = True):
    """Run the fix/cleanup script."""
    if not fix_after_extraction:
        return
    
    print("\n" + "="*70)
    print("STEP 2: FIXING RECOMMENDATIONS")
    print("="*70)
    
    from fix_recommendations import fix_recommendations
    
    project_root = Path(__file__).parent
    input_file = project_root / 'web' / 'recommendations.json'
    
    if not input_file.exists():
        print(f"⚠️  {input_file} not found. Skipping fix step.")
        return
    
    result = fix_recommendations(input_file)
    
    print("\n" + "="*70)
    print("✓ Fix complete!")
    print("="*70)


def run_analysis(analyze_after: bool = True):
    """Run the analysis script."""
    if not analyze_after:
        return
    
    print("\n" + "="*70)
    print("STEP 3: ANALYZING RECOMMENDATIONS")
    print("="*70)
    
    from analyze_recommendations import analyze_recommendations
    
    project_root = Path(__file__).parent
    json_file = project_root / 'web' / 'recommendations.json'
    
    if not json_file.exists():
        print(f"⚠️  {json_file} not found. Skipping analysis.")
        return
    
    analyze_recommendations(json_file, verbose=True)
    
    print("\n" + "="*70)
    print("✓ Analysis complete!")
    print("="*70)


def run_deployment(auto_commit: bool = False):
    """Run the deployment script to update GitHub Pages."""
    print("\n" + "="*70)
    print("STEP 4: DEPLOYING TO GITHUB PAGES")
    print("="*70)
    
    from pathlib import Path
    import sys
    
    project_root = Path(__file__).parent
    deploy_script = project_root / 'scripts' / 'deploy_to_gh_pages.py'
    
    if not deploy_script.exists():
        print(f"⚠️  Deployment script not found: {deploy_script}")
        return
    
    try:
        # Import and run the deployment function directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "deploy_to_gh_pages", 
            str(deploy_script)
        )
        if spec is None or spec.loader is None:
            print("⚠️  Failed to load deployment script module")
            return
        
        deploy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy_module)
        
        success = deploy_module.deploy_to_gh_pages(
            project_root=project_root, 
            auto_commit=auto_commit
        )
        
        if success:
            print("\n" + "="*70)
            print("✓ Deployment complete!")
            print("="*70)
        else:
            print("\n" + "="*70)
            print("⚠️  Deployment had issues. Check messages above.")
            print("="*70)
    except Exception as e:
        print(f"⚠️  Error during deployment: {e}")
        print("   You can run manually: python scripts/deploy_to_gh_pages.py")


def print_next_steps(deployed: bool = False):
    """Print instructions for viewing results."""
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    
    if deployed:
        print("\n🌐 Your site is deployed!")
        print("   It will be available at: https://galcohensius.github.io/whatsapp-recommendations-extractor/")
        print("   (Check DEPLOYMENT.md for setup instructions if this is your first time)")
    else:
        print("\n📊 To view the recommendations locally:")
        print("   1. Run: cd docs && python -m http.server 8000")
        print("   2. Open: http://localhost:8000")
    
    print("\n📁 Output files:")
    print("   - web/recommendations.json (main output)")
    print("   - web/recommendations_backup.json (backup before AI enhancement)")
    print("   - docs/index.html (edit this file to customize the interface)")
    print("   - docs/recommendations.json (updated during deployment)")
    
    print("\n💡 Tips:")
    print("   - Edit docs/index.html directly to customize the interface")
    print("   - Use --skip-fix to skip the cleanup step")
    print("   - Use --skip-analysis to skip the analysis step")
    print("   - Use --use-openai to enhance recommendations with AI")
    print("   - Use --deploy to update recommendations.json on GitHub Pages")
    print("="*70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='WhatsApp Recommendations Extractor - Main Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full workflow (extract, fix, analyze)
  python main.py
  
  # Extract with OpenAI enhancement
  python main.py --use-openai
  
  # Extract only, skip fix and analysis
  python main.py --skip-fix --skip-analysis
  
  # Use a specific OpenAI model
  python main.py --use-openai --openai-model gpt-4o
  
  # Deploy to GitHub Pages after extraction
  python main.py --deploy
  
  # Deploy with auto-commit
  python main.py --deploy --auto-commit
        """
    )
    
    parser.add_argument('--use-openai', action='store_true', help='Use OpenAI API to enhance recommendations (requires api_key.txt)')
    parser.add_argument('--openai-model', type=str, default='gpt-4o-mini',
                       choices=['gpt-5', 'gpt-4.1', 'o4-mini', 'gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
                       help='OpenAI model to use (default: gpt-4o-mini)')
    parser.add_argument('--skip-fix', action='store_true', help='Skip the fix/cleanup step')
    parser.add_argument('--skip-analysis', action='store_true', help='Skip the analysis step')
    parser.add_argument('--fix-only', action='store_true', help='Only run the fix step (skip extraction)')
    parser.add_argument('--analyze-only', action='store_true', help='Only run the analysis step (skip extraction)')
    parser.add_argument('--deploy', action='store_true', help='Deploy to GitHub Pages after extraction/fixes')
    parser.add_argument('--auto-commit', action='store_true', help='Automatically commit and push deployment changes (requires --deploy)')
    
    args = parser.parse_args()
    
    # Validate data directories exist
    project_root = Path(__file__).parent
    vcf_dir = project_root / 'data' / 'vcf'
    text_dir = project_root / 'data' / 'txt'
    
    print("\n" + "="*70)
    print("WHATSAPP RECOMMENDATIONS EXTRACTOR")
    print("="*70)
    print(f"\n📁 Data directories:")
    print(f"   VCF files: {vcf_dir}")
    print(f"   Chat files: {text_dir}")
    
    # Check if directories exist and have files
    if not vcf_dir.exists():
        print(f"   ⚠️  {vcf_dir} does not exist")
    else:
        vcf_count = len(list(vcf_dir.glob('*.vcf')))
        print(f"   ✓ Found {vcf_count} .vcf files")
    
    if not text_dir.exists():
        print(f"   ⚠️  {text_dir} does not exist")
    else:
        txt_count = len(list(text_dir.glob('*.txt')))
        print(f"   ✓ Found {txt_count} .txt files")
    
    # Handle different modes
    if args.fix_only:
        print("\n🔧 Running fix step only...")
        run_fix(fix_after_extraction=True)
        return
    
    if args.analyze_only:
        print("\n📊 Running analysis step only...")
        run_analysis(analyze_after=True)
        return
    
    # Normal workflow
    print("\n🚀 Starting workflow...")
    
    # Step 1: Extraction
    run_extraction(
        use_openai=args.use_openai,
        openai_model=args.openai_model
    )
    
    # Step 2: Fix (if not skipped)
    run_fix(fix_after_extraction=not args.skip_fix)
    
    # Step 3: Analysis (if not skipped)
    # Note: Analysis is already run inside extract_recommendations automatically
    # This step is for when you want to re-analyze after fixes
    if not args.skip_analysis:
        run_analysis(analyze_after=True)
    
    # Step 4: Deploy (if requested)
    deployed = False
    if args.deploy:
        run_deployment(auto_commit=args.auto_commit)
        deployed = True
    
    # Final summary
    print_next_steps(deployed=deployed)


if __name__ == '__main__':
    main()

