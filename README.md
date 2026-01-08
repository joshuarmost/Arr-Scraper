# Media Services Exporter for Prometheus

Exports metrics from Radarr, Sonarr, and Jellyfin to Prometheus. Includes pre-built Grafana dashboards.

## Quick Start

### Option 1: Docker Image Only

```bash
docker pull ghcr.io/joshuarmost/arr-scraper:latest

docker run -d \
  --name media-exporter \
  -p 9877:9877 \
  -e RADARR_URL=http://your-radarr:7878 \
  -e RADARR_API_KEY=your_api_key \
  -e SONARR_URL=http://your-sonarr:8989 \
  -e SONARR_API_KEY=your_api_key \
  -e JELLYFIN_URL=http://your-jellyfin:8096 \
  -e JELLYFIN_API_KEY=your_api_key \
  ghcr.io/joshuarmost/arr-scraper:latest
```

Metrics available at: `http://localhost:9877/metrics`

### Option 2: Full Stack (Exporter + Prometheus + Grafana)

```bash
git clone https://github.com/joshuarmost/Arr-Scraper
cd Arr-Scraper

# Configure your services
cp .env.example .env
nano .env  # Add your URLs and API keys

# Start everything
docker-compose up -d
```

**Access:**
- Grafana: http://localhost:3000 (login: admin/admin)
- Prometheus: http://localhost:9090
- Exporter: http://localhost:9877/metrics

## Prometheus Setup

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'media-exporter'
    scrape_interval: 60s
    static_configs:
      - targets: ['exporter-host:9877']
```

## Grafana Dashboards

Pre-built dashboards are in `grafana/dashboards/`:

### How to Import Dashboards

**Method 1: Via Grafana UI**
1. Open Grafana (http://localhost:3000)
2. Login (default: admin/admin)
3. Click **☰** menu → **Dashboards** → **Import**
4. Click **Upload JSON file**
5. Select a dashboard file from `grafana/dashboards/`
6. Choose your **Prometheus** datasource
7. Click **Import**

**Method 2: Copy-Paste JSON**
1. Open a dashboard JSON file in a text editor
2. Copy all contents
3. In Grafana: **Dashboards** → **Import** → **Import via panel json**
4. Paste the JSON
5. Select Prometheus datasource → **Import**

**Method 3: Auto-provisioned (docker-compose only)**
- Dashboards are automatically loaded on startup
- No manual import needed if using `docker-compose.yml`

### Available Dashboards
- **radarr-overview.json** - Movies, disk usage, codecs, genres
- **sonarr-overview.json** - Series, episodes, status, codecs
- **jellyfin-overview.json** - Streams, users, playback stats

## Configuration

### Required for Each Service:

| Service | Variables |
|---------|-----------|
| **Radarr** | `RADARR_URL`, `RADARR_API_KEY` |
| **Sonarr** | `SONARR_URL`, `SONARR_API_KEY` |
| **Jellyfin** | `JELLYFIN_URL`, `JELLYFIN_API_KEY` |

*Configure at least one service.*

### Get API Keys:

**Radarr/Sonarr:** Settings → General → API Key  
**Jellyfin:** Dashboard → API Keys → New API Key

## What Gets Monitored

- **Radarr:** Movie counts, disk usage, genres, codecs, download queue, historical data
- **Sonarr:** Series/episode counts, disk usage, genres, status, download queue
- **Jellyfin:** Active streams, user activity, playback methods, top content

## Example Queries

```promql
# Total library size in TB
(radarr_disk_usage_bytes + sonarr_disk_usage_bytes) / 1024^4

# Percentage downloaded
(radarr_movies_downloaded / radarr_movies_total) * 100

# Active streams
jellyfin_active_streams
```

## Building from Source

```bash
docker build -t media-exporter .
```

## License

Public domain
