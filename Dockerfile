# Dockerfile

# 1. Base image
FROM python:3.10-slim

# 2. Prevent .pyc files, unbuffer stdout/stderr, and add /app to PYTHONPATH
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 3. Work directory
WORKDIR /app

# 4. System deps (if needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Install your requirements + pytest
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest

# 6. Copy in your entire project (including run.py and tests/)
COPY . .

# 7. Expose the Flask port
EXPOSE 5000

# 8. Default command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]


CMD ["pytest", "-q"]
