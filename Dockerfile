# Dockerfile

# 1. Base image
FROM python:3.10-slim

# 2. Don’t write .pyc, unbuffered logs, and add /app to module search path
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 3. Working directory
WORKDIR /app

# 4. Copy & install only requirements first (for layer caching)
COPY requirements.txt .

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/* \
 # upgrade pip, install your deps + pytest
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt pytest

# 5. Copy the rest of your code (including run.py and tests/)
COPY . .

# 6. Expose your Flask port
EXPOSE 5000

# 7. Default command (Gunicorn will look for the Flask `app` in run.py)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
