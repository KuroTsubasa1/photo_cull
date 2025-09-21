"""Clustering algorithms for photo grouping"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import exifread
from dateutil import parser as dtparser
import os


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hash strings"""
    if len(hash1) != len(hash2):
        return max(len(hash1), len(hash2))
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def cluster_by_hash(items: List[Dict], dist_thresh: int = 8) -> List[List[int]]:
    """Cluster items by perceptual hash similarity
    
    Args:
        items: List of dicts with 'idx', 'phash', 'dhash' keys
        dist_thresh: Maximum Hamming distance to consider similar
    
    Returns:
        List of clusters, where each cluster is a list of indices
    """
    if not items:
        return []
    
    # Check for empty hashes
    empty_hash_count = sum(1 for item in items if not item.get('phash') or not item.get('dhash'))
    if empty_hash_count > 0:
        # If all items have empty hashes, create individual clusters for each
        if empty_hash_count == len(items):
            return [[item['idx']] for item in items]
        # Filter out items with empty hashes for clustering, but they should still be processed
        valid_items = [item for item in items if item.get('phash') and item.get('dhash')]
        empty_items = [item for item in items if not item.get('phash') or not item.get('dhash')]
    else:
        valid_items = items
        empty_items = []
    
    clusters = []
    clustered = set()
    
    # Cluster valid items with hashes
    for i, item in enumerate(valid_items):
        if item['idx'] in clustered:
            continue
        
        # Start new cluster
        cluster = [item['idx']]
        clustered.add(item['idx'])
        
        # Find all similar items
        for j, other in enumerate(valid_items[i+1:], start=i+1):
            if other['idx'] in clustered:
                continue
            
            # Check hash similarity
            phash_dist = hamming_distance(item['phash'], other['phash'])
            dhash_dist = hamming_distance(item['dhash'], other['dhash'])
            
            # More stringent: require BOTH hashes to be similar, or one to be very similar
            # This reduces false positives where images are grouped incorrectly
            very_similar_threshold = dist_thresh // 2  # Half the threshold for "very similar"
            
            is_similar = False
            if phash_dist <= very_similar_threshold or dhash_dist <= very_similar_threshold:
                # If one hash is very similar, that's enough
                is_similar = True
            elif phash_dist <= dist_thresh and dhash_dist <= dist_thresh:
                # Both hashes must be reasonably similar
                is_similar = True
            
            if is_similar:
                cluster.append(other['idx'])
                clustered.add(other['idx'])
        
        clusters.append(cluster)
    
    # Add items with empty hashes as individual clusters
    for item in empty_items:
        clusters.append([item['idx']])
    
    return clusters


def cluster_by_embeddings(embeddings: np.ndarray, k: Optional[int] = None) -> List[List[int]]:
    """Cluster images by semantic embeddings using FAISS
    
    Args:
        embeddings: Array of embeddings, shape (n_images, embedding_dim)
        k: Number of clusters (auto-determined if None)
    
    Returns:
        List of clusters, where each cluster is a list of indices
    """
    try:
        import faiss
        from sklearn.cluster import HDBSCAN
    except ImportError:
        print("[cluster] FAISS/HDBSCAN not installed, skipping embedding clustering")
        return [[i] for i in range(len(embeddings))]
    
    n_samples = len(embeddings)
    
    if n_samples < 2:
        return [[0]]
    
    # Normalize embeddings
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    if k is None:
        # Use HDBSCAN for automatic cluster detection
        clusterer = HDBSCAN(min_cluster_size=2, metric='euclidean')
        labels = clusterer.fit_predict(embeddings)
        
        # Group by label (-1 means noise, treat as singleton clusters)
        clusters = {}
        for idx, label in enumerate(labels):
            if label == -1:
                clusters[f"noise_{idx}"] = [idx]
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(idx)
        
        return list(clusters.values())
    else:
        # Use k-means for fixed number of clusters
        d = embeddings.shape[1]
        kmeans = faiss.Kmeans(d, k, niter=20, verbose=False, gpu=False)
        kmeans.train(embeddings.astype(np.float32))
        _, labels = kmeans.index.search(embeddings.astype(np.float32), 1)
        
        clusters = {}
        for idx, label in enumerate(labels.flatten()):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)
        
        return list(clusters.values())


def read_timestamp(img_path: str) -> float:
    """Extract timestamp from EXIF or file modification time
    
    Returns:
        Unix timestamp in seconds
    """
    from pathlib import Path
    
    # Check if it's a raw file and try to get metadata from rawpy first
    # DISABLED: This causes "File format not recognized" errors for CR3 files
    # CR3 files should use standard EXIF extraction instead
    # raw_extensions = {'.cr2', '.nef', '.nrw', '.arw', '.raf', '.orf', '.rw2', '.dng'}
    # if Path(img_path).suffix.lower() in raw_extensions:
    #     try:
    #         import rawpy
    #         with rawpy.imread(img_path) as raw:
    #             if raw.timestamp:
    #                 return float(raw.timestamp)
    #     except Exception:
    #         pass  # Fall back to standard EXIF
    
    try:
        with open(img_path, 'rb') as f:
            tags = exifread.process_file(f, details=False, stop_tag='EXIF DateTimeOriginal')
        
        datetime_str = None
        for key in ('EXIF DateTimeOriginal', 'EXIF DateTime', 'Image DateTime'):
            if key in tags:
                datetime_str = str(tags[key])
                break
        
        if datetime_str:
            # Parse EXIF datetime (format: "YYYY:MM:DD HH:MM:SS")
            dt = dtparser.parse(datetime_str.replace(':', '-', 2))
            return dt.timestamp()
    except Exception:
        pass
    
    # Try alternative approaches for RAW files that exifread can't handle (like CR3)
    try:
        from pathlib import Path
        file_ext = Path(img_path).suffix.lower()
        raw_extensions = {'.cr3', '.cr2', '.nef', '.nrw', '.arw', '.raf', '.orf', '.rw2', '.dng'}
        
        if file_ext in raw_extensions:
            # First try exiftool if available (optional dependency)
            try:
                import subprocess
                result = subprocess.run(
                    ['exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', '-S', '-s', img_path],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    datetime_str = result.stdout.strip()
                    if datetime_str:
                        dt = dtparser.parse(datetime_str.replace(':', '-', 2))
                        return dt.timestamp()
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                pass  # exiftool not available or failed
            
            # Try python-exiv2 as alternative to exiftool
            try:
                import exiv2
                img = exiv2.ImageFactory.open(img_path)
                exif_data = img.readMetadata()
                if exif_data:
                    # Look for datetime fields
                    for key in ['Exif.Photo.DateTimeOriginal', 'Exif.Image.DateTime']:
                        if key in exif_data:
                            datetime_str = str(exif_data[key])
                            if datetime_str:
                                dt = dtparser.parse(datetime_str.replace(':', '-', 2))
                                return dt.timestamp()
            except (ImportError, Exception):
                pass  # python-exiv2 not available or failed
    except Exception:
        pass
    
    # Try file creation time (more accurate than modification time for uploads)
    try:
        import platform
        path_obj = Path(img_path)
        
        if platform.system() == 'Darwin':  # macOS
            # On macOS, use stat().st_birthtime for creation time
            stat_result = path_obj.stat()
            if hasattr(stat_result, 'st_birthtime'):
                return stat_result.st_birthtime
        elif platform.system() == 'Windows':  # Windows
            # On Windows, use stat().st_ctime for creation time
            return path_obj.stat().st_ctime
    except Exception:
        pass
    
    # Fallback to file modification time
    return os.path.getmtime(img_path)


def group_into_bursts(image_paths: List[str], gap_ms: int = 700) -> List[List[int]]:
    """Group images into bursts based on timestamp gaps
    
    Args:
        image_paths: List of image file paths
        gap_ms: Maximum gap in milliseconds to consider same burst
    
    Returns:
        List of bursts, where each burst is a list of indices into image_paths
    """
    if not image_paths:
        return []
    
    # Get timestamps and sort by time
    timestamps = [(i, read_timestamp(path)) for i, path in enumerate(image_paths)]
    timestamps.sort(key=lambda x: x[1])
    
    bursts = []
    current_burst = [timestamps[0][0]]
    last_ts = timestamps[0][1]
    
    for idx, ts in timestamps[1:]:
        gap = (ts - last_ts) * 1000  # Convert to milliseconds
        
        if gap <= gap_ms:
            # Same burst
            current_burst.append(idx)
        else:
            # New burst
            bursts.append(current_burst)
            current_burst = [idx]
        
        last_ts = ts
    
    # Add final burst
    if current_burst:
        bursts.append(current_burst)
    
    return bursts


def score_images(metrics_list: List) -> None:
    """Compute quality scores for all images
    
    Modifies metrics in-place by adding z-scores and final scores
    """
    if not metrics_list:
        return
    
    # Compute z-scores for sharpness
    sharpness_values = [m.sharpness for m in metrics_list]
    mean_sharp = np.mean(sharpness_values)
    std_sharp = np.std(sharpness_values)
    
    if std_sharp > 0:
        for m in metrics_list:
            m.sharpness_z = (m.sharpness - mean_sharp) / std_sharp
    else:
        for m in metrics_list:
            m.sharpness_z = 0.0
    
    # Compute final scores with aesthetic considerations
    for m in metrics_list:
        # Base technical quality score
        technical_score = (
            0.3 * m.sharpness_z +  # Sharpness is important
            0.2 * m.blur_score +   # No blur
            0.15 * m.exposure_ok   # Good exposure
        )
        
        # Portrait quality (if faces detected)
        portrait_score = 0.0
        if m.face_count > 0:
            # Eyes open is critical for portraits
            portrait_score += 0.25 * m.eyes_open
            
            # Face sharpness matters more in portraits
            if m.face_blur_scores:
                avg_face_blur = sum(m.face_blur_scores) / len(m.face_blur_scores)
                portrait_score += 0.1 * avg_face_blur
        else:
            # No faces - redistribute portrait weight to technical
            technical_score += 0.35
        
        # Aesthetic considerations
        aesthetic_score = 0.0
        
        # Prefer well-exposed images (not too dark or bright)
        if m.exposure_ok > 0.8:
            aesthetic_score += 0.05
        
        # Slight preference for images without motion blur
        if not m.has_motion_blur:
            aesthetic_score += 0.05
        
        # Composition hint: prefer images with 1-3 faces over crowds
        if 1 <= m.face_count <= 3:
            aesthetic_score += 0.05
        elif m.face_count > 5:
            aesthetic_score -= 0.05
        
        # Calculate final score
        m.score = technical_score + portrait_score + aesthetic_score
        
        # Ensure score is in reasonable range
        m.score = max(-2.0, min(2.0, m.score))