#!/usr/bin/env python3
"""Web server with UI and processing capabilities"""

import http.server
import socketserver
import os
import json
import shutil
import threading
import queue
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import traceback

from .main import process_folder

class ProcessingQueue:
    """Manages background processing jobs"""
    def __init__(self):
        self.queue = queue.Queue()
        self.current_job = None
        self.job_history = []
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()
    
    def _worker(self):
        """Background worker thread"""
        while True:
            job = self.queue.get()
            self.current_job = job
            try:
                job['status'] = 'processing'
                job['start_time'] = time.time()
                
                # Run the processing
                process_folder(
                    job['input_dir'],
                    with_embeddings=job.get('with_embeddings', False),
                    hash_dist=job.get('hash_dist', 8),
                    out_dir=job['output_dir'],
                    burst_gap_ms=job.get('burst_gap_ms', 700),
                    generate_thumbnails=True,
                    thumbnail_size=job.get('thumbnail_size', 800)
                )
                
                job['status'] = 'completed'
                job['end_time'] = time.time()
                job['duration'] = job['end_time'] - job['start_time']
                
            except Exception as e:
                job['status'] = 'failed'
                job['error'] = str(e)
                job['traceback'] = traceback.format_exc()
                print(f"Processing failed: {e}")
            
            self.job_history.append(job)
            self.current_job = None
            self.queue.task_done()
    
    def add_job(self, job):
        """Add a processing job to the queue"""
        job['id'] = len(self.job_history) + self.queue.qsize() + 1
        job['status'] = 'queued'
        self.queue.put(job)
        return job['id']
    
    def get_status(self):
        """Get current processing status"""
        return {
            'current': self.current_job,
            'queue_size': self.queue.qsize(),
            'history': self.job_history[-10:]  # Last 10 jobs
        }

# Global processing queue
processing_queue = ProcessingQueue()


class PhotoCullHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with processing capabilities"""
    
    def translate_path(self, path):
        """Translate URL path to filesystem path"""
        # Parse URL
        parsed = urlparse(path)
        path = parsed.path
        
        # API endpoints don't map to files
        if path.startswith('/api/'):
            return None
            
        # Handle thumbnail and output paths
        if '/thumbnails/' in path or '/out/' in path or '/report.json' in path:
            # Map to output directory
            if path.startswith('/'):
                path = path[1:]
            
            # Check if it's a specific report
            if path.startswith('output/'):
                file_path = Path('/app') / path
            else:
                # Default to latest output
                file_path = Path('/app/output') / path
            
            return str(file_path)
        
        # Default to UI directory
        if path == '/':
            path = '/index.html'
        ui_path = Path('/app/ui') / path[1:]
        return str(ui_path)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path.startswith('/api/'):
            self.handle_api_get()
        else:
            # Serve static files
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path.startswith('/api/'):
            self.handle_api_post()
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        """Handle preflight OPTIONS requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def handle_api_get(self):
        """Handle API GET requests"""
        if self.path == '/api/status':
            # Get processing status
            status = processing_queue.get_status()
            self.send_json_response(status)
            
        elif self.path == '/api/reports':
            # List available reports
            reports = []
            output_dir = Path('/app/output')
            for report_file in output_dir.glob('*/report.json'):
                try:
                    with open(report_file) as f:
                        data = json.load(f)
                    reports.append({
                        'name': report_file.parent.name,
                        'path': str(report_file.relative_to(output_dir)),
                        'images': len(data.get('images', [])),
                        'clusters': len(data.get('hash_clusters', []))
                    })
                except:
                    pass
            self.send_json_response(reports)
            
        else:
            self.send_error(404)
    
    def handle_api_post(self):
        """Handle API POST requests"""
        if self.path == '/api/process':
            # Start processing job
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data)
            
            # Validate parameters
            input_dir = params.get('input_dir', '/app/uploads')
            if not Path(input_dir).exists():
                self.send_json_response({'error': 'Input directory not found'}, 400)
                return
            
            # Create unique output directory
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            output_name = params.get('name', f'process_{timestamp}')
            output_dir = f'/app/output/{output_name}'
            
            # Add job to queue
            job = {
                'input_dir': input_dir,
                'output_dir': output_dir,
                'name': output_name,
                'hash_dist': params.get('hash_dist', 8),
                'burst_gap_ms': params.get('burst_gap_ms', 700),
                'with_embeddings': params.get('with_embeddings', False),
                'thumbnail_size': params.get('thumbnail_size', 800)
            }
            
            job_id = processing_queue.add_job(job)
            self.send_json_response({'job_id': job_id, 'status': 'queued'})
            
        elif self.path == '/api/upload':
            # Handle file upload
            content_type = self.headers.get('Content-Type', '')
            
            # Parse boundary from content-type
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, 'Expected multipart/form-data')
                return
            
            # Get boundary
            boundary = content_type.split('boundary=')[1] if 'boundary=' in content_type else None
            if not boundary:
                self.send_error(400, 'No boundary in multipart/form-data')
                return
            
            # Read the entire body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Create upload directory
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            upload_dir = Path('/app/uploads') / timestamp
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Parse multipart data
            files_saved = []
            boundary_bytes = f'--{boundary}'.encode()
            parts = post_data.split(boundary_bytes)
            
            for part in parts[1:-1]:  # Skip first (empty) and last (closing)
                if not part:
                    continue
                    
                # Split headers and content
                try:
                    header_end = part.index(b'\r\n\r\n')
                    headers = part[:header_end].decode('utf-8', errors='ignore')
                    content = part[header_end + 4:]
                    
                    # Remove trailing \r\n
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    
                    # Parse filename from Content-Disposition header
                    if 'filename=' in headers:
                        # Extract filename
                        filename_start = headers.index('filename="') + 10
                        filename_end = headers.index('"', filename_start)
                        filename = headers[filename_start:filename_end]
                        
                        # Save file
                        if filename:
                            file_path = upload_dir / filename
                            with open(file_path, 'wb') as f:
                                f.write(content)
                            files_saved.append(filename)
                            print(f"Saved: {file_path}")
                
                except Exception as e:
                    print(f"Error parsing part: {e}")
                    continue
            
            # Send response
            self.send_json_response({
                'upload_dir': str(upload_dir),
                'files_saved': files_saved,
                'count': len(files_saved)
            })
            
        else:
            self.send_error(404)
    
    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def end_headers(self):
        """Add CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()


def main():
    """Start the server"""
    PORT = int(os.environ.get('PORT', 8000))
    
    print(f"PhotoCull Server Starting")
    print(f"=" * 40)
    print(f"Web UI: http://localhost:{PORT}")
    print(f"Upload directory: /app/uploads")
    print(f"Output directory: /app/output")
    print(f"=" * 40)
    print(f"Press Ctrl+C to stop")
    
    with socketserver.TCPServer(("", PORT), PhotoCullHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")


if __name__ == "__main__":
    main()