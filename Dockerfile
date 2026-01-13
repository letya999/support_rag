FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# Pre-download models (cache this layer)
COPY scripts/download_models.py scripts/
RUN python scripts/download_models.py

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
# Production mode: no reload, proper number of workers
# For development, use: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
