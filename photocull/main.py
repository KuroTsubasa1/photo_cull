"""Main CLI entry point for PhotoCull"""

import os
import json
import shutil
import argparse
from pathlib import Path
from typing import List, Optional
import numpy as np

from .features import FeatureExtractor, ImageMetrics, extract_clip_embedding
from .clustering import (
    cluster_by_hash, cluster_by_embeddings, group_into_bursts,
    score_images, read_timestamp
)


def list_images(directory: str) -> List[str]:
    """List all image files in a directory"""
    # Standard image formats
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    
    # Raw formats from various manufacturers
    raw_extensions = {
        # Canon
        '.cr2', '.cr3', '.crw',
        # Nikon
        '.nef', '.nrw',
        # Sony
        '.arw', '.srf', '.sr2',
        # Fujifilm
        '.raf',
        # Olympus
        '.orf',
        # Panasonic
        '.rw2',
        # Pentax
        '.pef', '.ptx',
        # Adobe
        '.dng',
        # Phase One
        '.iiq',
        # Leica
        '.rwl', '.raw',
        # Hasselblad
        '.3fr',
        # Sigma
        '.x3f',
        # Samsung
        '.srw'
    }
    
    all_extensions = image_extensions | raw_extensions
    path = Path(directory)
    
    images = []
    for file in path.rglob('*'):
        if file.is_file() and file.suffix.lower() in all_extensions:
            images.append(str(file))
    
    return sorted(images)


def process_folder(
    input_dir: str,
    with_embeddings: bool = False,
    hash_dist: int = 8,
    out_dir: str = "out",
    burst_gap_ms: int = 700,
    generate_thumbnails: bool = True,
    thumbnail_size: int = 800
):
    """Process a folder of images and select the best ones
    
    Args:
        input_dir: Path to folder containing images
        with_embeddings: Whether to compute CLIP embeddings
        hash_dist: Hamming distance threshold for near-duplicates
        out_dir: Output directory for results
        burst_gap_ms: Maximum gap in milliseconds for burst grouping
    """
    print(f"[process] Scanning {input_dir}...")
    paths = list(list_images(input_dir))
    
    if not paths:
        print(f"[process] No images found in {input_dir}")
        return
    
    print(f"[process] Found {len(paths)} images")
    
    # Create output directories
    out_path = Path(out_dir)
    winners_dir = out_path / "winners"
    similar_dir = out_path / "similar"
    thumbnails_dir = out_path / "thumbnails"
    
    for d in [out_path, winners_dir, similar_dir, thumbnails_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Extract features
    print("[process] Extracting features...")
    if generate_thumbnails:
        print(f"[process] Generating thumbnails (size: {thumbnail_size}px)...")
    
    from .raw_utils import create_thumbnail, is_raw_file
    import hashlib
    
    extractor = FeatureExtractor()
    metrics = []
    
    clip_model = None
    clip_processor = None
    
    for i, path in enumerate(paths):
        if (i + 1) % 10 == 0:
            print(f"[process] Processing {i+1}/{len(paths)}...")
        
        m = extractor.extract_all_features(path)
        
        # Generate thumbnail if requested (always for raw files)
        needs_thumbnail = generate_thumbnails or is_raw_file(path)
        
        if needs_thumbnail:
            # Create unique thumbnail name based on file path hash
            file_hash = hashlib.md5(path.encode()).hexdigest()[:8]
            thumb_name = f"{Path(path).stem}_{file_hash}.jpg"
            thumb_path = thumbnails_dir / thumb_name
            
            if not thumb_path.exists():
                if (i + 1) % 10 == 0 or is_raw_file(path):
                    print(f"[thumb] Creating thumbnail for {Path(path).name}...")
                    
                success = create_thumbnail(path, str(thumb_path), (thumbnail_size, thumbnail_size))
                if success:
                    m.thumbnail_path = str(thumb_path)
                else:
                    # Fallback to original if thumbnail creation fails
                    m.thumbnail_path = path
                    if is_raw_file(path):
                        print(f"[thumb] WARNING: Could not create thumbnail for raw file {Path(path).name}")
                        print(f"[thumb] Raw file will not display in UI")
            else:
                m.thumbnail_path = str(thumb_path)
        else:
            # No thumbnail requested, use original
            m.thumbnail_path = path
        
        # Optional: extract CLIP embeddings
        if with_embeddings:
            if clip_model is None:
                try:
                    import open_clip
                    clip_model, _, clip_processor = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
                    clip_model.eval()
                except ImportError:
                    print("[process] CLIP not available, skipping embeddings")
                    with_embeddings = False
            
            if clip_model:
                m.embedding = extract_clip_embedding(path, clip_model, clip_processor)
        
        metrics.append(m)
    
    # Score all images
    print("[process] Computing quality scores...")
    score_images(metrics)
    
    # Group into bursts
    print(f"[process] Grouping into bursts (gap={burst_gap_ms}ms)...")
    bursts = group_into_bursts(paths, gap_ms=burst_gap_ms)
    print(f"[process] Found {len(bursts)} bursts")
    
    # Process each burst
    all_cluster_reports = []
    cluster_id_counter = 0
    
    for burst_id, burst_indices in enumerate(bursts):
        # Get metrics for this burst
        burst_items = [
            {"idx": i, "phash": metrics[i].phash, "dhash": metrics[i].dhash}
            for i in burst_indices
        ]
        
        # Cluster by hash within burst
        hash_clusters = cluster_by_hash(burst_items, dist_thresh=hash_dist)
        
        # Select winner from each cluster
        for cluster_indices in hash_clusters:
            # Get scores and sort
            cluster_metrics = [(i, metrics[i].score) for i in cluster_indices]
            cluster_metrics.sort(key=lambda x: x[1], reverse=True)
            
            # Winner is highest scoring
            winner_idx = cluster_metrics[0][0]
            winner_path = metrics[winner_idx].path
            
            # Copy winner to output
            dst = winners_dir / Path(winner_path).name
            try:
                shutil.copy2(winner_path, dst)
            except Exception as e:
                print(f"[copy] Error copying winner: {e}")
            
            # Copy similar images
            for idx, score in cluster_metrics[1:]:
                similar_path = metrics[idx].path
                dst = similar_dir / f"cluster{cluster_id_counter}_{Path(similar_path).name}"
                try:
                    shutil.copy2(similar_path, dst)
                except Exception as e:
                    print(f"[copy] Error copying similar: {e}")
            
            # Add to report
            all_cluster_reports.append({
                "cluster_id": cluster_id_counter,
                "burst_id": burst_id,
                "members": [metrics[i].path for i, _ in cluster_metrics],
                "winner": winner_path,
                "scores": [float(score) for _, score in cluster_metrics]
            })
            
            cluster_id_counter += 1
    
    # Optional: compute embedding clusters for reference
    emb_clusters = None
    if with_embeddings:
        embeddings = [m.embedding for m in metrics if m.embedding is not None]
        if len(embeddings) == len(metrics):
            emb_array = np.vstack(embeddings)
            emb_clusters = cluster_by_embeddings(emb_array)
    
    # Write report
    report = {
        "params": {
            "hash_dist_thresh": hash_dist,
            "with_embeddings": with_embeddings,
            "burst_gap_ms": burst_gap_ms,
            "generate_thumbnails": generate_thumbnails,
            "thumbnail_size": thumbnail_size,
            "thumbnails_dir": str(thumbnails_dir)
        },
        "images": [m.to_dict() for m in metrics],
        "hash_clusters": all_cluster_reports,
        "embedding_clusters": emb_clusters,
        "bursts": bursts
    }
    
    report_path = out_path / "report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"[process] Complete! Results in {out_dir}/")
    print(f"[process] Winners: {len(all_cluster_reports)}")
    print(f"[process] Report: {report_path}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="PhotoCull - Intelligent photo selection")
    parser.add_argument("--input", "-i", required=True, help="Input folder containing images")
    parser.add_argument("--out", "-o", default="out", help="Output folder (default: out)")
    parser.add_argument("--with-embeddings", action="store_true", 
                       help="Compute CLIP embeddings for semantic similarity")
    parser.add_argument("--hash-dist", type=int, default=8,
                       help="Hamming distance threshold for near-duplicates (default: 8)")
    parser.add_argument("--burst-gap-ms", type=int, default=700,
                       help="Maximum gap in milliseconds for burst grouping (default: 700)")
    parser.add_argument("--no-thumbnails", action="store_true",
                       help="Skip thumbnail generation (UI won't work for raw files)")
    parser.add_argument("--thumbnail-size", type=int, default=800,
                       help="Maximum thumbnail size in pixels (default: 800)")
    
    args = parser.parse_args()
    
    process_folder(
        args.input,
        with_embeddings=args.with_embeddings,
        hash_dist=args.hash_dist,
        out_dir=args.out,
        burst_gap_ms=args.burst_gap_ms,
        generate_thumbnails=not args.no_thumbnails,
        thumbnail_size=args.thumbnail_size
    )


if __name__ == "__main__":
    main()