# PhotoCull Usage Examples

## Basic Usage

### 1. Simple photo culling
```bash
python -m photocull.main --input ~/Pictures/vacation --out ./results
```

This will:
- Scan all images in `~/Pictures/vacation`
- Group them into bursts (700ms gap default)
- Detect near-duplicates using perceptual hashing
- Score each image based on sharpness, exposure, and eyes-open detection
- Copy winners to `./results/winners/`
- Copy similar/lower-scoring images to `./results/similar/`
- Generate `./results/report.json` with detailed metrics

### 2. Adjust burst detection sensitivity
```bash
# Tighter bursts (500ms gap)
python -m photocull.main --input ~/Pictures/event --out ./results --burst-gap-ms 500

# Looser bursts (2 seconds gap)
python -m photocull.main --input ~/Pictures/sports --out ./results --burst-gap-ms 2000
```

### 3. Adjust duplicate detection sensitivity
```bash
# More strict (only very similar images grouped)
python -m photocull.main --input ~/Pictures --out ./results --hash-dist 5

# More lenient (group somewhat similar images)
python -m photocull.main --input ~/Pictures --out ./results --hash-dist 12
```

### 4. Include semantic similarity (requires optional dependencies)
```bash
# First install optional dependencies
pip install transformers torch open-clip-torch faiss-cpu

# Run with CLIP embeddings
python -m photocull.main --input ~/Pictures --out ./results --with-embeddings
```

## Review UI Usage

### 1. Open the review interface
```bash
# After running the CLI, open the UI
open photocull/ui/index.html  # macOS
# or
xdg-open photocull/ui/index.html  # Linux
# or just open in your browser
```

### 2. Load and review results
1. Click "Load report.json"
2. Navigate to your output folder and select `report.json`
3. Browse bursts in the left sidebar
4. Review clusters and their selected winners
5. Click "Promote to Winner" to change selections
6. Click "Export JSON" to save your changes

### 3. Keyboard shortcuts in UI
- Arrow keys: Navigate between bursts
- Click on image: View full size
- Escape: Close image modal

## Python API Usage

```python
from photocull.features import FeatureExtractor, ImageMetrics
from photocull.clustering import group_into_bursts, cluster_by_hash, score_images

# Extract features from a single image
extractor = FeatureExtractor()
metrics = extractor.extract_all_features("path/to/image.jpg")
print(f"Sharpness: {metrics.sharpness}")
print(f"Eyes open: {metrics.eyes_open * 100}%")
print(f"Faces detected: {metrics.face_count}")

# Process a batch of images
paths = ["img1.jpg", "img2.jpg", "img3.jpg"]
all_metrics = [extractor.extract_all_features(p) for p in paths]

# Score and rank images
score_images(all_metrics)
ranked = sorted(all_metrics, key=lambda m: m.score, reverse=True)
print(f"Best image: {ranked[0].path} (score: {ranked[0].score})")

# Group into bursts
bursts = group_into_bursts(paths, gap_ms=700)
print(f"Found {len(bursts)} bursts")

# Cluster by similarity
items = [{"idx": i, "phash": m.phash, "dhash": m.dhash} 
         for i, m in enumerate(all_metrics)]
clusters = cluster_by_hash(items, dist_thresh=8)
print(f"Found {len(clusters)} unique photo clusters")
```

## Tuning Guidelines

### Sharpness threshold
- Default variance threshold works for most cameras
- For high-resolution cameras (>24MP), you may need to increase thresholds
- Test with a few known sharp/blurry images to calibrate

### Eyes detection
- Default EAR threshold: 0.22
- Decrease to 0.20 for stricter "eyes open" detection
- Increase to 0.25 for more lenient detection
- Works best with frontal faces

### Hash distance
- 0-4: Nearly identical images only
- 5-8: Very similar (default range)
- 9-12: Somewhat similar (may group different poses)
- 13+: Quite different (not recommended)

### Burst gaps
- 500-700ms: Typical continuous shooting bursts
- 1000-2000ms: Action sequences
- 3000ms+: Separate photo sessions

## Troubleshooting

### "No module named 'cv2'"
```bash
pip install opencv-python
```

### "No module named 'mediapipe'"
```bash
pip install mediapipe
```

### Images not showing in UI
- The UI needs local file access
- Use a local web server if needed:
```bash
cd photocull/ui
python -m http.server 8000
# Then open http://localhost:8000
```

### Slow processing
- Reduce image resolution before processing
- Skip embeddings if not needed (don't use --with-embeddings)
- Process smaller batches of images