FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    ca-certificates \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies including gunicorn for production
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copy application code and entrypoint script
COPY app app
COPY scripts scripts
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Make entrypoint script executable and create non-root user
RUN chmod +x /docker-entrypoint.sh \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Use entrypoint script for graceful shutdown
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive=65"]