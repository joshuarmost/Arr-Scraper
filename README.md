# Media Services Exporter for Prometheus

Exports metrics from Radarr, Sonarr, and Jellyfin to Prometheus. Includes pre-built Grafana dashboards.

## Quick Start

### Option 1: Docker Compose

Create `compose.yaml`:

```yaml
services:
  media-exporter:
    image: ghcr.io/joshuarmost/arr-scraper:latest
    container_name: media-exporter
    ports:
      - "9877:9877"
    environment:
      RADARR_URL: "http://your-radarr:7878"
      RADARR_API_KEY: "your_api_key"
      SONARR_URL: "http://your-sonarr:8989"
      SONARR_API_KEY: "your_api_key"
      JELLYFIN_URL: "http://your-jellyfin:8096"
      JELLYFIN_API_KEY: "your_api_key"
    restart: unless-stopped
```

Metrics available at: `http://localhost:9877/metrics`

## Grafana Dashboards

Pre-built dashboards are in `grafana/dashboards/`.

### Direct Import URL (Unified Dashboard)

Import the unified dashboard directly in Grafana using this URL:

https://raw.githubusercontent.com/joshuarmost/Arr-Scraper/main/grafana/dashboards/media-overview.json
