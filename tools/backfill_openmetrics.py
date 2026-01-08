import os
import sys
import time
from collections import defaultdict
from datetime import datetime
import requests


def iso_date(dt_str: str) -> str:
    return dt_str.split("T")[0]


def fetch_radarr_movies(url: str, api_key: str):
    r = requests.get(f"{url}/api/v3/movie", headers={"X-Api-Key": api_key}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_sonarr_series(url: str, api_key: str):
    r = requests.get(f"{url}/api/v3/series", headers={"X-Api-Key": api_key}, timeout=30)
    r.raise_for_status()
    return r.json()


def build_cumulative_by_date_radarr(movies):
    date_counts = defaultdict(int)
    for m in movies:
        added = m.get("added")
        if added:
            date_counts[iso_date(added)] += 1
    total = 0
    out = []  # list of (date_str, value)
    for d in sorted(date_counts.keys()):
        total += date_counts[d]
        out.append((d, total))
    return out


def build_cumulative_by_date_sonarr(series):
    date_counts = defaultdict(int)
    for s in series:
        added = s.get("added")
        ep_files = s.get("statistics", {}).get("episodeFileCount", 0)
        if added and ep_files > 0:
            date_counts[iso_date(added)] += ep_files
    total = 0
    out = []
    for d in sorted(date_counts.keys()):
        total += date_counts[d]
        out.append((d, total))
    return out


def to_unix_ms(date_str: str) -> int:
    # Interpret date as UTC midnight
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(time.mktime(dt.timetuple()) * 1000)


def write_openmetrics(radarr_series, sonarr_series, fp):
    fp.write("# TYPE radarr_cumulative_movies gauge\n")
    for d, v in radarr_series:
        fp.write(f"radarr_cumulative_movies {v} {to_unix_ms(d)}\n")
    fp.write("\n")

    fp.write("# TYPE sonarr_cumulative_episodes gauge\n")
    for d, v in sonarr_series:
        fp.write(f"sonarr_cumulative_episodes {v} {to_unix_ms(d)}\n")
    fp.write("\n# EOF\n")


def main():
    radarr_url = os.getenv("RADARR_URL")
    radarr_api = os.getenv("RADARR_API_KEY")
    sonarr_url = os.getenv("SONARR_URL")
    sonarr_api = os.getenv("SONARR_API_KEY")

    if not radarr_url or not radarr_api:
        print("Missing RADARR_URL or RADARR_API_KEY", file=sys.stderr)
        sys.exit(2)

    movies = fetch_radarr_movies(radarr_url.rstrip("/"), radarr_api)
    radarr_series = build_cumulative_by_date_radarr(movies)

    sonarr_series = []
    if sonarr_url and sonarr_api:
        series = fetch_sonarr_series(sonarr_url.rstrip("/"), sonarr_api)
        sonarr_series = build_cumulative_by_date_sonarr(series)

    out_path = os.getenv("BACKFILL_OUT", "backfill.om")
    with open(out_path, "w", encoding="utf-8") as fp:
        write_openmetrics(radarr_series, sonarr_series, fp)

    print(f"Wrote OpenMetrics backfill file: {out_path}")
    print("Next steps (Prometheus >= 2.40):")
    print("1) Stop Prometheus")
    print("2) Create blocks from OpenMetrics:")
    print("   promtool tsdb create-blocks-from openmetrics backfill.om ./backfill-blocks")
    print("3) Move generated blocks into Prometheus data dir (e.g., /var/lib/prometheus)")
    print("4) Start Prometheus")


if __name__ == "__main__":
    main()
