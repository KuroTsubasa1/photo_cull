"""Utilities for handling raw image files"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import cv2
import os


def is_raw_file(file_path: str) -> bool:
    """Check if a file is a raw image format"""
    raw_extensions = {
        '.cr2', '.cr3', '.crw',  # Canon
        '.nef', '.nrw',           # Nikon
        '.arw', '.srf', '.sr2',   # Sony
        '.raf',                   # Fujifilm
        '.orf',                   # Olympus
        '.rw2',                   # Panasonic
        '.pef', '.ptx',           # Pentax
        '.dng',                   # Adobe
        '.iiq',                   # Phase One
        '.rwl', '.raw',           # Leica
        '.3fr',                   # Hasselblad
        '.x3f',                   # Sigma
        '.srw'                    # Samsung
    }
    return Path(file_path).suffix.lower() in raw_extensions


def load_raw_as_rgb(file_path: str) -> Tuple[Optional[np.ndarray], Optional[Image.Image]]:
    """Load a raw file and convert to RGB
    
    Returns:
        Tuple of (opencv_image, PIL_image) or (None, None) if loading fails
    """
    try:
        import rawpy
        import imageio
        
        # Load raw file
        with rawpy.imread(file_path) as raw:
            # Process raw to RGB
            # use_camera_wb: Use camera white balance
            # half_size: For faster processing (reduces resolution by half)
            # no_auto_bright: Don't auto-adjust brightness
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,  # Full resolution
                no_auto_bright=False,
                output_bps=8
            )
        
        # Convert to PIL Image
        img_pil = Image.fromarray(rgb)
        
        # Convert RGB to BGR for OpenCV
        img_cv = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        
        return img_cv, img_pil
        
    except ImportError:
        print("[raw] rawpy not installed, cannot process raw files")
        print("[raw] Install with: pip install rawpy")
        return None, None
    except Exception as e:
        print(f"[raw] Error loading raw file {file_path}: {e}")
        return None, None


def load_image_universal(file_path: str) -> Tuple[Optional[np.ndarray], Optional[Image.Image]]:
    """Load any supported image format (raw or standard)
    
    Returns:
        Tuple of (opencv_image, PIL_image) or (None, None) if loading fails
    """
    if is_raw_file(file_path):
        return load_raw_as_rgb(file_path)
    else:
        # Standard image format
        try:
            img_pil = Image.open(file_path).convert('RGB')
            img_cv = cv2.imread(file_path)
            return img_cv, img_pil
        except Exception as e:
            print(f"[load] Error loading image {file_path}: {e}")
            return None, None


def extract_raw_metadata(file_path: str) -> dict:
    """Extract metadata from raw files
    
    Returns dictionary with camera settings and EXIF data
    """
    metadata = {}
    
    try:
        import rawpy
        
        with rawpy.imread(file_path) as raw:
            # Camera info
            metadata['camera_make'] = raw.camera_make.decode('utf-8', errors='ignore')
            metadata['camera_model'] = raw.camera_model.decode('utf-8', errors='ignore')
            
            # Shooting info
            metadata['timestamp'] = raw.timestamp
            metadata['shot_order'] = raw.shot_order
            metadata['shutter_speed'] = raw.shutter_speed
            metadata['iso'] = raw.iso_speed
            metadata['focal_length'] = raw.focal_length
            metadata['aperture'] = raw.aperture
            
            # Image info
            metadata['raw_pattern'] = str(raw.raw_pattern.tolist())
            metadata['black_level'] = raw.black_level
            metadata['white_level'] = raw.white_level
            metadata['color_matrix'] = raw.color_matrix.tolist() if raw.color_matrix is not None else None
            
            # White balance
            metadata['daylight_wb'] = raw.daylight_whitebalance
            metadata['camera_wb'] = raw.camera_whitebalance
            
    except ImportError:
        print("[raw] rawpy not installed, cannot extract raw metadata")
    except Exception as e:
        print(f"[raw] Error extracting metadata from {file_path}: {e}")
    
    return metadata


def create_raw_thumbnail(file_path: str, size: Tuple[int, int] = (256, 256)) -> Optional[Image.Image]:
    """Create a thumbnail from a raw file
    
    Args:
        file_path: Path to raw file
        size: Thumbnail size (width, height)
    
    Returns:
        PIL Image thumbnail or None if failed
    """
    try:
        import rawpy
        
        with rawpy.imread(file_path) as raw:
            # Extract embedded thumbnail if available (faster)
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    import io
                    thumb_img = Image.open(io.BytesIO(thumb.data))
                    thumb_img.thumbnail(size, Image.Resampling.LANCZOS)
                    return thumb_img
            except rawpy.LibRawError:
                pass  # No embedded thumbnail
            
            # Fall back to processing with half_size for speed
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=True,  # Faster processing
                no_auto_bright=False,
                output_bps=8
            )
            
            img = Image.fromarray(rgb)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img
            
    except Exception as e:
        print(f"[raw] Error creating thumbnail for {file_path}: {e}")
        return None