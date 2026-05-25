# Use Python 3.10 slim as base
FROM python:3.10-slim

# Install system dependencies (including ffmpeg and system packages needed for browser automation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    xz-utils \
    build-essential \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers

WORKDIR /app

# Copy requirements file first to cache pip layers
COPY requirements.txt .

# Install dependencies (use CPU-only PyTorch to minimize build size and time)
RUN pip install --upgrade pip setuptools wheel && \
    pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Download and install rustypipe-botguard (needed by yt-dlp-get-pot-rustypipe plugin for PO Tokens)
RUN curl -L -o /tmp/rustypipe.tar.xz https://codeberg.org/ThetaDev/rustypipe-botguard/releases/download/v0.1.2/rustypipe-botguard-v0.1.2-x86_64-unknown-linux-gnu.tar.xz && \
    tar -xf /tmp/rustypipe.tar.xz -C /tmp && \
    mv /tmp/rustypipe-botguard /usr/local/bin/ && \
    chmod +x /usr/local/bin/rustypipe-botguard && \
    rm /tmp/rustypipe.tar.xz

# Install Playwright & Phantomwright Chromium and its system dependencies
RUN playwright install --with-deps chromium && \
    python -m phantomwright install chromium

# Copy application source code
COPY . .

# Pre-download Whisper models into the image (avoids runtime download + OOM restarts)
RUN python pre_download_models.py

# Expose backend port
EXPOSE 8000

# Start FastAPI server using Uvicorn (respecting the platform-provided PORT env var)
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
