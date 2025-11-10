#!/usr/bin/env python3
"""Create a test ZIP file from existing data for testing the upload feature."""

import zipfile
import os
from pathlib import Path

# Create ZIP file
zip_path = Path('test_upload.zip')
if zip_path.exists():
    zip_path.unlink()

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    # Add all TXT files from data/txt
    txt_dir = Path('data/txt')
    if txt_dir.exists():
        for txt_file in txt_dir.glob('*.txt'):
            z.write(txt_file, txt_file.name)
            print(f"Added: {txt_file.name}")
    
    # Add first 10 VCF files from data/vcf (to keep size reasonable)
    vcf_dir = Path('data/vcf')
    if vcf_dir.exists():
        vcf_files = list(vcf_dir.glob('*.vcf'))[:10]
        for vcf_file in vcf_files:
            z.write(vcf_file, f'vcf/{vcf_file.name}')
            print(f"Added: vcf/{vcf_file.name}")

size_mb = zip_path.stat().st_size / (1024 * 1024)
print(f"\n✓ Created test_upload.zip ({size_mb:.2f} MB)")
print(f"  Location: {zip_path.absolute()}")

