# PhotoCull - Intelligent Photo Selection Tool

A fast, local-first photo culling tool that uses perceptual hashing, classical computer vision, and optional AI embeddings to automatically select the best photos from bursts and similar shots.

## Features

- **Raw file support**: Handles Canon CR3, CR2, Nikon NEF, Sony ARW, and other major raw formats
- **Automatic thumbnail generation**: Creates JPEG previews for UI display (essential for raw files)
- **Burst detection**: Groups photos by EXIF timestamp (or file mtime) with configurable gap threshold
- **Near-duplicate detection**: Uses pHash and dHash with Hamming distance
- **Quality metrics**:
  - Sharpness (variance of Laplacian & Tenengrad)
  - Blur detection (global, face-region, and motion blur)
  - Exposure quality (histogram clipping analysis)
  - Eyes-open detection (MediaPipe Face Mesh + EAR)
  - Face counting
- **Optional CLIP embeddings**: Semantic similarity clustering via FAISS
- **Static review UI**: Browser-based interface to review and adjust selections

## Quickstart

```bash
# Setup
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Basic usage (fast: pHash/dHash + classical QA)
python -m photocull.main --input /path/to/images --out /path/to/output

# With semantic clustering (CLIP + FAISS)
python -m photocull.main --input /path/to/images --out /path/to/output --with-embeddings

# Custom burst detection gap (default: 700ms)
python -m photocull.main --input /path/to/images --out /path/to/output --burst-gap-ms 500

# Custom thumbnail size (default: 800px)
python -m photocull.main --input /path/to/images --out /path/to/output --thumbnail-size 1200

# Skip thumbnail generation (not recommended for raw files)
python -m photocull.main --input /path/to/images --out /path/to/output --no-thumbnails
```

## Output Structure

```
output/
├── winners/      # Best photos from each cluster
├── similar/      # Near-duplicates and lower-scoring variants
├── thumbnails/   # JPEG previews for UI display (auto-generated)
└── report.json   # Detailed metrics and clustering data
```

## Review UI

1. Run the CLI to generate `report.json`
2. Open `ui/index.html` in your browser
3. Load the `report.json` file
4. Review bursts and clusters
5. Click "Promote" to change winners
6. Export the updated JSON

## How It Works

1. **Burst grouping**: Images are grouped by timestamp (EXIF or mtime) with a configurable gap
2. **Hash clustering**: Within each burst, near-duplicates are identified using perceptual hashes
3. **Quality scoring**: Each image gets scored based on:
   - Sharpness (40% weight)
   - Blur detection (20% weight) 
   - Eyes-open percentage (25% weight)  
   - Exposure quality (15% weight)
   - Additional penalties for motion blur and face blur
4. **Winner selection**: Highest-scoring image per cluster is selected
5. **Review**: Optional UI for manual override of selections

## Configuration

Default thresholds (tunable via code):
- Burst gap: 700ms
- Hash distance: ≤8 Hamming distance = near-duplicate
- Blur threshold: ~150-300 variance (camera-dependent)
- Eyes closed: EAR < 0.22

## Supported File Formats

### Standard Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- BMP (.bmp)
- TIFF (.tif, .tiff)

### Raw Formats
- **Canon**: CR2, CR3, CRW
- **Nikon**: NEF, NRW
- **Sony**: ARW, SRF, SR2
- **Fujifilm**: RAF
- **Olympus**: ORF
- **Panasonic**: RW2
- **Pentax**: PEF, PTX
- **Adobe**: DNG
- **Others**: Leica (RWL), Hasselblad (3FR), Phase One (IIQ), Sigma (X3F)

## Requirements

- Python 3.8+
- OpenCV
- MediaPipe
- NumPy
- Pillow
- imagehash
- rawpy (for raw file support)
- imageio
- Optional: CLIP (transformers), FAISS