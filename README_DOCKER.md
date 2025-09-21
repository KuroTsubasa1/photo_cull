# PhotoCull Docker Setup

## Quick Start

### 1. Easy Start (Recommended)
```bash
./start.sh
```

This will:
- Build the Docker image
- Start the application
- Open at http://localhost:8000

### 2. Manual Docker Compose
```bash
docker-compose up --build
```

### 3. Manual Docker Build & Run
```bash
# Build the image
docker build -t photocull .

# Run the container
docker run -p 8000:8000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/output:/app/output \
  photocull
```

## Usage

1. **Open the Web UI**: Navigate to http://localhost:8000

2. **Process Photos**: 
   - Click "Process New Photos" button
   - Upload your photos via drag & drop or file selection
   - Configure processing options:
     - Similarity threshold (4-16)
     - Burst gap timing (100-5000ms)
     - Thumbnail size
     - Optional CLIP embeddings
   - Click "Start Processing"

3. **View Results**:
   - Processing happens in the background
   - View completed reports in the main UI
   - Use keyboard navigation:
     - ↑/↓: Navigate bursts
     - ←/→: Navigate images
     - Space: Promote to winner
     - [ ]: Resize preview panel

## Directory Structure

```
photocull/
├── uploads/     # Input photos (mounted volume)
├── output/      # Processing results (mounted volume)
│   └── [job_name]/
│       ├── report.json
│       ├── winners/
│       ├── similar/
│       └── thumbnails/
└── temp/        # Temporary files
```

## Features

- **Web-based UI**: No installation needed for users
- **Batch Processing**: Queue multiple jobs
- **Background Processing**: Non-blocking UI
- **Real-time Status**: Live processing updates
- **Result Viewer**: Interactive photo review interface
- **Keyboard Navigation**: Efficient photo review
- **Resizable Preview**: Adjustable preview panel
- **Persistent Storage**: Results saved to local volumes

## System Requirements

- Docker and Docker Compose
- 4GB RAM minimum (configurable in docker-compose.yml)
- Sufficient disk space for photos and thumbnails

## Configuration

Edit `docker-compose.yml` to adjust:
- Memory limits
- Port mapping
- Volume locations

## Troubleshooting

### Port Already in Use
Change the port in docker-compose.yml:
```yaml
ports:
  - "8080:8000"  # Use 8080 instead
```

### Permission Issues
Ensure the directories are writable:
```bash
chmod -R 755 uploads output temp
```

### Out of Memory
Increase memory limit in docker-compose.yml:
```yaml
deploy:
  resources:
    limits:
      memory: 8G
```

## Development

To modify and rebuild:
```bash
# Make changes to code
# Then rebuild
docker-compose build
docker-compose up
```

## Security Notes

- The application runs locally only (not exposed to network)
- Uploaded files are stored in local volumes
- No external services or data transmission

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Report issues on GitHub