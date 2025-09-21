#!/bin/bash

echo "🚀 Starting PhotoCull with Docker..."
echo "=================================="

# Create necessary directories
mkdir -p uploads output temp

# Build and start with docker-compose
docker-compose up --build

echo "=================================="
echo "✨ PhotoCull is running at http://localhost:8000"
echo "📁 Upload photos at http://localhost:8000/process.html"