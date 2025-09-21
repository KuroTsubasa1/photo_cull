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
from urllib.parse import parse_qs, urlparse, unquote
import traceback

from .main import process_folder

class ProcessingQueue:
    """Manages background processing jobs"""
    def __init__(self):
        self.queue = queue.Queue()
        self.current_job = None
        self.job_history = []
        self.processing_stage = ""
        self.processing_progress = {}
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()
    
    def _worker(self):
        """Background worker thread"""
        while True:
            job = self.queue.get()
            self.current_job = job
            self.processing_stage = "Starting..."
            self.processing_progress = {}
            
            try:
                job['status'] = 'processing'
                job['start_time'] = time.time()
                
                # Create a custom process function with stage updates
                self._process_with_stages(job)
                
                job['status'] = 'completed'
                job['end_time'] = time.time()
                job['duration'] = job['end_time'] - job['start_time']
                self.processing_stage = "Complete!"
                
            except Exception as e:
                job['status'] = 'failed'
                job['error'] = str(e)
                job['traceback'] = traceback.format_exc()
                self.processing_stage = f"Failed: {str(e)}"
                print(f"Processing failed: {e}")
            
            self.job_history.append(job)
            self.current_job = None
            self.queue.task_done()
    
    def _process_with_stages(self, job):
        """Process with stage updates"""
        from .main import list_images
        from .features import FeatureExtractor, extract_clip_embedding
        from .clustering import cluster_by_hash, score_images, group_into_bursts
        
        input_dir = job['input_dir']
        output_dir = job['output_dir']
        
        # Stage 1: Scanning
        self.processing_stage = "Scanning for images..."
        paths = list(list_images(input_dir))
        self.processing_progress['total_images'] = len(paths)
        
        if not paths:
            raise ValueError("No images found in upload directory")
        
        # Create output directories
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        winners_dir = Path(output_dir) / "winners"
        similar_dir = Path(output_dir) / "similar"
        thumbnails_dir = Path(output_dir) / "thumbnails"
        
        for d in [winners_dir, similar_dir, thumbnails_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Stage 2: Feature extraction
        self.processing_stage = "Extracting features..."
        extractor = FeatureExtractor()
        metrics = []
        
        for i, path in enumerate(paths):
            self.processing_progress['current_image'] = i + 1
            self.processing_progress['current_file'] = Path(path).name
            self.processing_stage = f"Processing {i+1}/{len(paths)}: {Path(path).name}"
            
            m = extractor.extract_all_features(path)
            
            # Generate thumbnails
            from .raw_utils import create_thumbnail, is_raw_file
            import hashlib
            
            if job.get('generate_thumbnails', True) or is_raw_file(path):
                file_hash = hashlib.md5(path.encode()).hexdigest()[:8]
                thumb_name = f"{Path(path).stem}_{file_hash}.jpg"
                thumb_path = thumbnails_dir / thumb_name
                
                if not thumb_path.exists():
                    create_thumbnail(path, str(thumb_path), 
                                   (job.get('thumbnail_size', 800), job.get('thumbnail_size', 800)))
                    m.thumbnail_path = f"thumbnails/{thumb_name}"
            
            metrics.append(m)
        
        
        # Stage 3: Scoring
        self.processing_stage = "Computing quality scores..."
        score_images(metrics)
        
        # Stage 4: Grouping
        self.processing_stage = "Grouping into bursts..."
        bursts = group_into_bursts(paths, gap_ms=job.get('burst_gap_ms', 700))
        print(f"[DEBUG] Burst grouping result: {len(bursts)} bursts")
        print(f"[DEBUG] First few bursts: {bursts[:3] if len(bursts) > 0 else 'none'}")
        print(f"[DEBUG] Burst sizes: {[len(b) for b in bursts[:5]]}")
        self.processing_progress['burst_count'] = len(bursts)
        
        # Stage 5: Clustering
        self.processing_stage = "Finding similar images..."
        all_cluster_reports = []
        cluster_id_counter = 0
        
        # Process clusters (simplified from main.py)
        all_items = [
            {"idx": i, "phash": m.phash, "dhash": m.dhash}
            for i, m in enumerate(metrics)
        ]
        global_hash_clusters = cluster_by_hash(all_items, dist_thresh=job.get('hash_dist', 8))
        self.processing_progress['cluster_count'] = len(global_hash_clusters)
        
        # Stage 6: Selecting winners
        self.processing_stage = "Selecting best photos..."
        processed_indices = set()
        
        # Create a mapping from image index to burst index
        idx_to_burst = {}
        for burst_idx, burst in enumerate(bursts):
            for img_idx in burst:
                idx_to_burst[img_idx] = burst_idx
        
        for cluster_idx, global_cluster in enumerate(global_hash_clusters):
            self.processing_stage = f"Selecting winners {cluster_idx+1}/{len(global_hash_clusters)}..."
            
            if all(idx in processed_indices for idx in global_cluster):
                continue
            
            # Get scores and sort
            cluster_metrics = [(i, metrics[i].score) for i in global_cluster]
            cluster_metrics.sort(key=lambda x: x[1], reverse=True)
            
            # Winner is highest scoring
            winner_idx = cluster_metrics[0][0]
            winner_path = metrics[winner_idx].path
            
            # Determine which burst this cluster belongs to (use winner's burst)
            burst_id = idx_to_burst.get(winner_idx, 0)
            
            # Copy winner
            import shutil
            dst = winners_dir / Path(winner_path).name
            try:
                shutil.copy2(winner_path, dst)
            except Exception as e:
                print(f"[copy] Error copying winner: {e}")
            
            # Copy similar
            for idx, score in cluster_metrics[1:]:
                similar_path = metrics[idx].path
                dst = similar_dir / f"cluster{cluster_id_counter}_{Path(similar_path).name}"
                try:
                    shutil.copy2(similar_path, dst)
                except Exception as e:
                    print(f"[copy] Error copying similar: {e}")
            
            # Add to report with burst_id
            all_cluster_reports.append({
                "cluster_id": cluster_id_counter,
                "burst_id": burst_id,
                "members": [metrics[i].path for i, _ in cluster_metrics],
                "winner": winner_path,
                "scores": [float(score) for _, score in cluster_metrics]
            })
            
            for idx, _ in cluster_metrics:
                processed_indices.add(idx)
            
            cluster_id_counter += 1
        
        # Stage 7: Saving report
        self.processing_stage = "Generating report..."
        report = {
            "params": job,
            "images": [m.to_dict() for m in metrics],
            "hash_clusters": all_cluster_reports,
            "bursts": bursts
        }
        
        report_path = Path(output_dir) / "report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        self.processing_progress['winners'] = len(all_cluster_reports)
        self.processing_stage = "Processing complete!"
    
    def add_job(self, job):
        """Add a processing job to the queue"""
        job['id'] = len(self.job_history) + self.queue.qsize() + 1
        job['status'] = 'queued'
        self.queue.put(job)
        return job['id']
    
    def get_status(self):
        """Get current processing status"""
        status = {
            'current': self.current_job,
            'queue_size': self.queue.qsize(),
            'history': self.job_history[-10:],  # Last 10 jobs
            'stage': self.processing_stage,
            'progress': self.processing_progress
        }
        
        # Add stage to current job if processing
        if self.current_job and self.current_job.get('status') == 'processing':
            status['current']['stage'] = self.processing_stage
            status['current']['progress'] = self.processing_progress
        
        return status

# Global processing queue
processing_queue = ProcessingQueue()


class PhotoCullHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with processing capabilities"""
    
    def translate_path(self, path):
        """Translate URL path to filesystem path"""
        # Parse URL and decode
        parsed = urlparse(path)
        path = unquote(parsed.path)
        
        # API endpoints don't map to files
        if path.startswith('/api/'):
            return None
            
        # Handle thumbnail, output, and upload paths
        if '/thumbnails/' in path or '/out/' in path or '/report.json' in path or '/uploads/' in path:
            # Map to local directories
            if path.startswith('/'):
                path = path[1:]
            
            # Check if it's a specific report
            if path.startswith('output/') or path.startswith('uploads/'):
                # Use current working directory for local development
                file_path = Path.cwd() / path
            else:
                # Default to latest output in current directory
                file_path = Path.cwd() / 'output' / path
            
            return str(file_path)
        
        # Default to UI directory
        if path == '/':
            path = '/home.html'
        # Use current working directory for local development
        ui_path = Path.cwd() / 'ui' / path[1:]
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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_DELETE(self):
        """Handle DELETE requests"""
        if self.path.startswith('/api/'):
            self.handle_api_delete()
        else:
            self.send_error(404)
    
    def handle_api_delete(self):
        """Handle API DELETE requests"""
        if self.path.startswith('/api/reports/'):
            # Delete specific report
            report_name = self.path[13:]  # Remove '/api/reports/'
            
            # Validate report name (no path traversal)
            if not report_name or '/' in report_name or '..' in report_name:
                self.send_json_response({'error': 'Invalid report name'}, 400)
                return
            
            # Check if report exists
            report_dir = Path.cwd() / 'output' / report_name
            if not report_dir.exists() or not (report_dir / 'report.json').exists():
                self.send_json_response({'error': 'Report not found'}, 404)
                return
            
            try:
                # Delete the entire report directory
                import shutil
                shutil.rmtree(report_dir)
                self.send_json_response({'success': True, 'message': f'Report "{report_name}" deleted'})
            except Exception as e:
                self.send_json_response({'error': f'Failed to delete report: {str(e)}'}, 500)
        
        else:
            self.send_error(404)
    
    def handle_api_get(self):
        """Handle API GET requests"""
        if self.path == '/api/status':
            # Get processing status
            status = processing_queue.get_status()
            self.send_json_response(status)
            
        elif self.path == '/api/reports':
            # List available reports
            reports = []
            output_dir = Path.cwd() / 'output'
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
            input_dir = params.get('input_dir', str(Path.cwd() / 'uploads'))
            if not Path(input_dir).exists():
                self.send_json_response({'error': 'Input directory not found'}, 400)
                return
            
            # Create unique output directory
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            output_name = params.get('name', f'process_{timestamp}')
            output_dir = str(Path.cwd() / 'output' / output_name)
            
            # Ensure paths are local, not Docker paths
            print(f"Processing job - Input: {input_dir}, Output: {output_dir}")
            
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
            
        elif self.path == '/api/export-winners':
            # Export winner images
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data)
            
            report_name = params.get('report_name')
            if not report_name:
                self.send_json_response({'error': 'Report name required'}, 400)
                return
            
            # Load report
            report_path = Path.cwd() / 'output' / report_name / 'report.json'
            if not report_path.exists():
                self.send_json_response({'error': 'Report not found'}, 404)
                return
            
            try:
                with open(report_path) as f:
                    report = json.load(f)
                
                # Create export directory
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                export_dir = Path.cwd() / 'output' / report_name / f'winners_export_{timestamp}'
                export_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy winner images
                exported_files = []
                for cluster in report.get('hash_clusters', []):
                    winner_path = cluster['winner']
                    winner_file = Path(winner_path)
                    
                    if winner_file.exists():
                        # Copy with cluster prefix
                        dst_name = f"cluster_{cluster['cluster_id']:03d}_{winner_file.name}"
                        dst_path = export_dir / dst_name
                        shutil.copy2(winner_path, dst_path)
                        exported_files.append({
                            'original': winner_path,
                            'exported': str(dst_path),
                            'cluster_id': cluster['cluster_id']
                        })
                
                # Create export summary
                summary = {
                    'export_dir': str(export_dir),
                    'exported_count': len(exported_files),
                    'files': exported_files,
                    'timestamp': timestamp
                }
                
                # Save export log
                summary_path = export_dir / 'export_summary.json'
                with open(summary_path, 'w') as f:
                    json.dump(summary, f, indent=2)
                
                self.send_json_response(summary)
                
            except Exception as e:
                self.send_json_response({'error': f'Export failed: {str(e)}'}, 500)
        
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
            upload_dir = Path.cwd() / 'uploads' / timestamp
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
    print(f"Upload directory: {Path.cwd() / 'uploads'}")
    print(f"Output directory: {Path.cwd() / 'output'}")
    print(f"UI directory: {Path.cwd() / 'ui'}")
    print(f"=" * 40)
    print(f"Press Ctrl+C to stop")
    
    with socketserver.TCPServer(("", PORT), PhotoCullHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")


if __name__ == "__main__":
    main()