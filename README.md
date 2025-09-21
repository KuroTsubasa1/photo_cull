# PhotoCull - Intelligent Photo Selection Tool

A fast, local-first photo culling tool that uses perceptual hashing, classical computer vision, and optional AI embeddings to automatically select the best photos from bursts and similar shots.

## Features

- **Raw file support**: Handles Canon CR3, CR2, Nikon NEF, Sony ARW, and other major raw formats
- **Automatic thumbnail generation**: Creates JPEG previews for UI display (essential for raw files)
- **Burst detection**: Groups photos by EXIF timestamp with configurable gap threshold (supports CR3/RAW via ExifTool)
- **Near-duplicate detection**: Uses pHash and dHash with Hamming distance
- **Quality metrics**:
  - Sharpness (variance of Laplacian & Tenengrad)
  - Blur detection (global, face-region, and motion blur)
  - Exposure quality (histogram clipping analysis)
  - Eyes-open detection (MediaPipe Face Mesh + EAR)
  - Face counting
- **Optional CLIP embeddings**: Semantic similarity clustering via FAISS
- **Static review UI**: Browser-based interface to review and adjust selections

## Prerequisites

- **Python 3.8+** with pip
- **ExifTool** (required for RAW file timestamp extraction)
  - macOS: `brew install exiftool`
  - Ubuntu/Debian: `sudo apt install exiftool` or `sudo apt install libimage-exiftool-perl`
  - Windows: Download from [exiftool.org](https://exiftool.org/)

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

### Method 1: Using the built-in server (Recommended)
```bash
# After running photocull to generate output
cd ui
python serve.py --output ../out

# Or specify a custom output directory
python serve.py --output /path/to/your/output
```

This will:
- Start a local web server on http://localhost:8000
- Automatically open your browser
- Serve thumbnails properly for viewing

### Method 2: Direct file opening (Limited)
1. Open `ui/index.html` in your browser
2. Load the `report.json` file
3. Note: Images may not display due to browser security restrictions

### Using the UI
1. Browse bursts in the left sidebar
2. Review clusters and their winners
3. Click "Promote" to change winners
4. Export the updated JSON with your changes

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