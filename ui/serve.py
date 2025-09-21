#!/usr/bin/env python3
"""Simple HTTP server for PhotoCull UI that serves local files"""

import http.server
import socketserver
import os
import sys
from pathlib import Path
import json
import webbrowser
import argparse

class PhotoCullHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, output_dir="out", **kwargs):
        self.output_dir = Path(output_dir).resolve()
        super().__init__(*args, **kwargs)
    
    def translate_path(self, path):
        """Translate URL path to filesystem path"""
        # Remove URL parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        
        # For thumbnails, serve from output directory
        if path.startswith('/thumbnails/'):
            file_path = self.output_dir / path[1:]  # Remove leading /
            return str(file_path)
        
        # Default behavior for other files
        return super().translate_path(path)
    
    def end_headers(self):
        """Add CORS headers to allow local file access"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        super().end_headers()

def serve_ui(port=8000, output_dir="out"):
    """Start the UI server"""
    # Get absolute paths
    script_dir = Path(__file__).parent.resolve()
    output_dir = Path(output_dir).resolve()
    
    # Check if output directory exists
    if not output_dir.exists():
        print(f"Error: Output directory '{output_dir}' not found")
        print(f"Run 'python -m photocull.main' first to generate output")
        return
    
    # Check if report.json exists
    report_file = output_dir / "report.json"
    if not report_file.exists():
        print(f"Error: {report_file} not found")
        print(f"Run 'python -m photocull.main' first to generate report")
        return
    
    # Change to UI directory
    os.chdir(script_dir)
    
    # Create handler with output directory
    handler = lambda *args: PhotoCullHandler(*args, output_dir=output_dir)
    
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"PhotoCull UI Server")
        print(f"=" * 40)
        print(f"Serving UI at: {url}")
        print(f"Output directory: {output_dir}")
        print(f"Report file: {report_file}")
        print(f"=" * 40)
        print(f"Opening browser...")
        print(f"Press Ctrl+C to stop the server")
        
        # Open browser
        webbrowser.open(f"{url}?output={output_dir}")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve PhotoCull UI")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on (default: 8000)")
    parser.add_argument("--output", default="out", help="Output directory from PhotoCull (default: out)")
    
    args = parser.parse_args()
    serve_ui(args.port, args.output)