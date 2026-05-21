# Use Python 3.10 slim as base
FROM python:3.10-slim

# Install system dependencies (including ffmpeg and system packages needed for browser automation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Copy requirements file first to cache pip layers
COPY requirements.txt .

# Install dependencies (use CPU-only PyTorch to minimize build size and time)
RUN pip install --upgrade pip setuptools wheel && \
    pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Install Playwright Chromium and its system dependencies
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application source code
COPY . .

# Expose backend port
EXPOSE 8000

# Start FastAPI server using Uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
