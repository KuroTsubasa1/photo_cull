"""Alternative raw processing using imageio-ffmpeg for CR3 files"""

import os
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import numpy as np
import subprocess
import tempfile


def extract_cr3_thumbnail_exiftool(cr3_path: str, output_path: str) -> bool:
    """Extract embedded JPEG from CR3 using exiftool (if available)
    
    Many CR3 files contain a full-resolution JPEG preview that can be extracted.
    """
    try:
        # Check if exiftool is available
        result = subprocess.run(['exiftool', '-b', '-JpgFromRaw', cr3_path], 
                              capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            # Write the extracted JPEG
            with open(output_path, 'wb') as f:
                f.write(result.stdout)
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return False


def extract_cr3_thumbnail_ffmpeg(cr3_path: str, output_path: str, size: Tuple[int, int] = (800, 800)) -> bool:
    """Extract thumbnail from CR3 using ffmpeg (fallback method)
    
    Some CR3 files can be read by ffmpeg as they contain embedded video streams.
    """
    try:
        # Use ffmpeg to extract a frame
        cmd = [
            'ffmpeg', '-i', cr3_path,
            '-vframes', '1',
            '-vf', f'scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease',
            '-y', output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0 and os.path.exists(output_path)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return False


def create_cr3_thumbnail(cr3_path: str, output_path: str, size: Tuple[int, int] = (800, 800)) -> bool:
    """Try multiple methods to extract a thumbnail from CR3 file
    
    CR3 is a complex format based on ISO Base Media File Format (similar to MP4).
    LibRaw support is limited, so we try alternative methods.
    """
    # Method 1: Try exiftool to extract embedded JPEG
    if extract_cr3_thumbnail_exiftool(cr3_path, output_path):
        # Resize the extracted JPEG if needed
        try:
            img = Image.open(output_path)
            if img.width > size[0] or img.height > size[1]:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.save(output_path, 'JPEG', quality=85, optimize=True)
            return True
        except:
            pass
    
    # Method 2: Try ffmpeg
    if extract_cr3_thumbnail_ffmpeg(cr3_path, output_path, size):
        return True
    
    # Method 3: Try using PIL/Pillow directly (some CR3s have embedded previews)
    try:
        from PIL import Image
        img = Image.open(cr3_path)
        # Try to get the thumbnail or convert the image
        if hasattr(img, '_getexif'):
            img.thumbnail(size, Image.Resampling.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            return True
    except:
        pass
    
    return False