#!/usr/bin/env python3
"""Test script to check raw file support"""

import sys
import os
from pathlib import Path

def test_rawpy_support():
    """Test if rawpy is installed and what formats it supports"""
    print("Testing raw file support...")
    print("-" * 50)
    
    # Check if rawpy is installed
    try:
        import rawpy
        print("✓ rawpy is installed")
        print(f"  Version: {rawpy.version}")
    except ImportError:
        print("✗ rawpy is not installed")
        print("  Install with: pip install rawpy")
        return False
    
    # Check LibRaw version
    try:
        libraw_version = rawpy.libraw_version
        print(f"✓ LibRaw version: {libraw_version}")
    except:
        print("  Could not determine LibRaw version")
    
    return True

def test_file(file_path):
    """Test if a specific file can be processed"""
    import rawpy
    from photocull.raw_utils import is_raw_file, create_thumbnail
    
    file_path = Path(file_path)
    print(f"\nTesting: {file_path.name}")
    print(f"  Extension: {file_path.suffix}")
    print(f"  Is raw file: {is_raw_file(str(file_path))}")
    
    if is_raw_file(str(file_path)):
        try:
            with rawpy.imread(str(file_path)) as raw:
                print(f"  ✓ Can open with rawpy")
                print(f"    Camera: {raw.camera_make.decode()} {raw.camera_model.decode()}")
                print(f"    Size: {raw.sizes.raw_width}x{raw.sizes.raw_height}")
                
                # Try to create thumbnail
                thumb_path = f"test_thumb_{file_path.stem}.jpg"
                if create_thumbnail(str(file_path), thumb_path, (400, 400)):
                    print(f"  ✓ Thumbnail created: {thumb_path}")
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                else:
                    print(f"  ✗ Failed to create thumbnail")
                    
        except rawpy._rawpy.LibRawFileUnsupportedError:
            print(f"  ✗ Format not supported by LibRaw")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print(f"  Not detected as raw file")

if __name__ == "__main__":
    if test_rawpy_support():
        if len(sys.argv) > 1:
            # Test specific files
            for file_path in sys.argv[1:]:
                if os.path.exists(file_path):
                    test_file(file_path)
                else:
                    print(f"\nFile not found: {file_path}")
        else:
            print("\nUsage: python test_raw_support.py [file1] [file2] ...")
            print("\nSupported raw formats (theoretical):")
            formats = [
                "Canon: CR2, CR3*, CRW",
                "Nikon: NEF, NRW",
                "Sony: ARW, SRF, SR2",
                "Fujifilm: RAF",
                "Olympus: ORF",
                "Panasonic: RW2",
                "Pentax: PEF, PTX",
                "Adobe: DNG",
                "Others: 3FR, IIQ, RWL, X3F, SRW"
            ]
            for fmt in formats:
                print(f"  {fmt}")
            print("\n* CR3 requires LibRaw 0.20+ (may not work with older versions)")