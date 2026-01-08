FROM python:3.11-slim

LABEL maintainer="Media Services Exporter"
LABEL description="Prometheus exporter for Radarr, Sonarr, and Jellyfin"

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy exporter script
COPY exporter.py .

# Create non-root user
RUN useradd -m -u 1000 exporter && \
    chown -R exporter:exporter /app

USER exporter

# Expose metrics port
EXPOSE 9877

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9877')" || exit 1

# Run exporter
CMD ["python", "-u", "exporter.py"]
