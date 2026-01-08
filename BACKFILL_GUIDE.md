# Historical Data Backfill Guide

This guide shows you how to import your historical Radarr/Sonarr data into Prometheus so your cumulative graphs show the full timeline.

## What This Does

- Reads your Radarr/Sonarr library
- Creates a file with historical cumulative counts (movies/episodes) for each date
- Imports that data into Prometheus with proper timestamps
- Your Grafana graphs will show the full history from when you first added content

## Prerequisites

- Docker containers running (Prometheus, exporter, Grafana)
- Python 3.x installed on your host machine

## Step-by-Step Instructions

### 1. Set Your API Credentials

Open PowerShell and run:

```powershell
$env:RADARR_URL="http://192.168.1.78:7878"
$env:RADARR_API_KEY="your_radarr_api_key_here"
$env:SONARR_URL="http://192.168.1.78:8989"
$env:SONARR_API_KEY="your_sonarr_api_key_here"
```

**Replace** `192.168.1.78` with your actual server IP and paste your real API keys.

### 2. Generate the Historical Data File

```powershell
cd "C:\Users\joshuarmost\Desktop\Joshua Most\Programming\Arr Scraper"
python tools/backfill_openmetrics.py
```

This creates a file called `backfill.om` in the current directory.

### 3. Stop Prometheus

```powershell
docker-compose stop prometheus
```

### 4. Convert to Prometheus Blocks

```powershell
docker run --rm -v ${PWD}:/data prom/prometheus:latest promtool tsdb create-blocks-from openmetrics /data/backfill.om /data/backfill-blocks
```

This creates a `backfill-blocks` folder with Prometheus data blocks.

### 5. Copy Blocks into Prometheus Data Directory

```powershell
# Find the Prometheus data directory
docker-compose exec prometheus ls -la /prometheus

# Copy the blocks
docker cp backfill-blocks/. arr-scraper-prometheus-1:/prometheus/
```

**Note:** Replace `arr-scraper-prometheus-1` with your actual Prometheus container name (check with `docker ps`).

### 6. Fix Permissions

```powershell
docker-compose exec prometheus chown -R nobody:nobody /prometheus
```

### 7. Start Prometheus

```powershell
docker-compose start prometheus
```

### 8. Verify in Grafana

1. Open Grafana (http://localhost:3000)
2. Go to your Media Overview dashboard
3. Set time range to "Last 1 year" or "Last 2 years"
4. The "Movies Library Size Over Time" and "Episodes Library Size Over Time" panels should now show the full historical curve

## Troubleshooting

**"ModuleNotFoundError: No module named 'requests'"**
```powershell
pip install requests
```

**"Container name not found"**
```powershell
# List running containers to find the exact name
docker ps
# Use the name shown under "NAMES" column
```

**"Permission denied" when copying blocks**
```powershell
# Make sure Prometheus is stopped before copying
docker-compose stop prometheus
# Then retry step 5
```

## You Only Need to Do This Once

After backfilling, the exporter will continue adding new data points automatically. You never need to run this again unless you want to re-import after adding old movies.

## Clean Up

After successful import:

```powershell
rm backfill.om
rm -r backfill-blocks
```
