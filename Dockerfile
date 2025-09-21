FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY photocull/ ./photocull/
COPY ui/ ./ui/

# Create directories for uploads and output
RUN mkdir -p /app/uploads /app/output /app/temp

# Expose port for UI server
EXPOSE 8000

# Start the UI server
CMD ["python", "-m", "photocull.server"]