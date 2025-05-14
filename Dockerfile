# Dockerfile

# 1. Use an official Python runtime as a parent image
FROM python:3.10-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Create and set work directory
WORKDIR /app

# 4. Install system dependencies (if any)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python dependencies + pytest
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest

# 6. Copy project
COPY . .

# 7. Expose port (match your Flask run port)
EXPOSE 5000

# 8. Default startup command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
