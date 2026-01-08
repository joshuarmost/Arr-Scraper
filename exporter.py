#!/usr/bin/env python3
"""
Media Services Prometheus Exporter
Exports metrics from Radarr, Sonarr, and Jellyfin for Prometheus scraping
"""

import os
import time
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any

import requests
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Configuration from environment variables"""
    
    # Radarr
    RADARR_URL = os.getenv("RADARR_URL", "")
    RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")
    
    # Sonarr
    SONARR_URL = os.getenv("SONARR_URL", "")
    SONARR_API_KEY = os.getenv("SONARR_API_KEY", "")
    
    # Jellyfin
    JELLYFIN_URL = os.getenv("JELLYFIN_URL", "")
    JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", "")
    
    # TMDB (optional, for actor data)
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    THETVDB_API_KEY = os.getenv("THETVDB_API_KEY", "")
    
    # Exporter settings
    EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9877"))
    SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))


class RadarrCollector:
    """Collects metrics from Radarr"""
    
    def __init__(self, url: str, api_key: str, tmdb_api_key: str = ""):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.tmdb_api_key = tmdb_api_key
        self.headers = {"X-Api-Key": api_key}
        self.session = requests.Session()
        
    def _get(self, endpoint: str, params: Dict = None) -> Any:
        """Make GET request to Radarr API"""
        try:
            url = f"{self.url}/api/v3/{endpoint}"
            response = self.session.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            return None
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect all Radarr metrics"""
        metrics = {}
        
        # Get all movies
        movies = self._get("movie")
        if not movies:
            return metrics
        
        # Basic counts
        total_movies = len(movies)
        movies_with_files = [m for m in movies if m.get("hasFile", False)]
        metrics['radarr_movies_total'] = total_movies
        metrics['radarr_movies_downloaded'] = len(movies_with_files)
        metrics['radarr_movies_missing'] = total_movies - len(movies_with_files)
        
        # Disk usage
        total_size = sum(m.get("sizeOnDisk", 0) for m in movies_with_files)
        metrics['radarr_disk_usage_bytes'] = total_size
        
        # Average size
        if movies_with_files:
            avg_size = total_size / len(movies_with_files)
            metrics['radarr_avg_movie_size_bytes'] = avg_size
        
        # Genre breakdown
        genre_counts = defaultdict(int)
        for movie in movies:
            for genre in movie.get("genres", []):
                genre_counts[genre] += 1
        metrics['radarr_genres'] = dict(genre_counts)
        
        # Year breakdown
        year_counts = defaultdict(int)
        for movie in movies:
            year = movie.get("year")
            if year:
                year_counts[str(year)] += 1
        metrics['radarr_movies_by_year'] = dict(year_counts)
        
        # File types and codecs
        filetype_counts = defaultdict(int)
        video_codec_counts = defaultdict(int)
        audio_codec_counts = defaultdict(int)
        
        for movie in movies_with_files:
            movie_file = movie.get("movieFile", {})
            if movie_file:
                # File type
                path = movie_file.get("relativePath", "")
                if path:
                    ext = path.split(".")[-1].lower()
                    filetype_counts[ext] += 1
                
                # Codecs
                media_info = movie_file.get("mediaInfo", {})
                video_codec = media_info.get("videoCodec", "Unknown")
                audio_codec = media_info.get("audioCodec", "Unknown")
                
                # Normalize video codec names
                codec_map = {'x265': 'HEVC', 'h265': 'HEVC', 'x264': 'H.264', 'h264': 'H.264'}
                video_codec = codec_map.get(video_codec, video_codec)
                
                video_codec_counts[video_codec] += 1
                audio_codec_counts[audio_codec] += 1
        
        metrics['radarr_filetypes'] = dict(filetype_counts)
        metrics['radarr_video_codecs'] = dict(video_codec_counts)
        metrics['radarr_audio_codecs'] = dict(audio_codec_counts)
        
        # Movies added over time (cumulative)
        date_counts = defaultdict(int)
        for movie in movies:
            added = movie.get("added")
            if added:
                date_str = added.split("T")[0]
                date_counts[date_str] += 1
        
        # Calculate cumulative
        cumulative = {}
        total = 0
        for date in sorted(date_counts.keys()):
            total += date_counts[date]
            cumulative[date] = total
        metrics['radarr_cumulative_movies'] = cumulative
        
        # Quality profiles
        quality_counts = defaultdict(int)
        for movie in movies:
            profile = movie.get("qualityProfileId")
            if profile:
                quality_counts[f"profile_{profile}"] += 1
        metrics['radarr_quality_profiles'] = dict(quality_counts)
        
        # Queue/download info
        queue = self._get("queue")
        if queue:
            records = queue.get("records", [])
            metrics['radarr_queue_total'] = len(records)
            metrics['radarr_queue_downloading'] = len([r for r in records if r.get("status") == "downloading"])
            
            # Calculate average download time for active downloads
            download_times = []
            for record in records:
                if record.get("status") == "downloading":
                    estimated = record.get("estimatedCompletionTime")
                    added = record.get("added")
                    if estimated and added:
                        try:
                            est_time = datetime.fromisoformat(estimated.replace("Z", "+00:00"))
                            add_time = datetime.fromisoformat(added.replace("Z", "+00:00"))
                            duration = (est_time - add_time).total_seconds()
                            if duration > 0:
                                download_times.append(duration)
                        except:
                            pass
            
            if download_times:
                metrics['radarr_avg_download_time_seconds'] = sum(download_times) / len(download_times)
        
        # History - average time from grab to import
        history = self._get("history", {"pageSize": 100, "eventType": 1})  # eventType 1 = grabbed
        if history and history.get("records"):
            import_times = []
            grabbed_events = {r["movieId"]: r["date"] for r in history["records"] if r.get("eventType") == "grabbed"}
            
            import_history = self._get("history", {"pageSize": 100, "eventType": 3})  # eventType 3 = imported
            if import_history and import_history.get("records"):
                for record in import_history["records"]:
                    movie_id = record.get("movieId")
                    if movie_id in grabbed_events:
                        try:
                            import_time = datetime.fromisoformat(record["date"].replace("Z", "+00:00"))
                            grab_time = datetime.fromisoformat(grabbed_events[movie_id].replace("Z", "+00:00"))
                            duration = (import_time - grab_time).total_seconds()
                            if duration > 0 and duration < 86400 * 7:  # Less than 7 days
                                import_times.append(duration)
                        except:
                            pass
            
            if import_times:
                metrics['radarr_avg_import_time_seconds'] = sum(import_times) / len(import_times)
        
        logger.info(f"Collected Radarr metrics: {total_movies} total movies, {len(movies_with_files)} downloaded")
        return metrics


class SonarrCollector:
    """Collects metrics from Sonarr"""
    
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {"X-Api-Key": api_key}
        self.session = requests.Session()
    
    def _get(self, endpoint: str, params: Dict = None) -> Any:
        """Make GET request to Sonarr API"""
        try:
            url = f"{self.url}/api/v3/{endpoint}"
            response = self.session.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            return None
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect all Sonarr metrics"""
        metrics = {}
        
        # Get all series
        series = self._get("series")
        if not series:
            return metrics
        
        # Basic counts
        total_series = len(series)
        metrics['sonarr_series_total'] = total_series
        
        # Episode and disk statistics
        total_episodes = 0
        total_episode_files = 0
        total_size = 0
        series_sizes = []
        episode_counts = []
        
        for show in series:
            stats = show.get("statistics", {})
            ep_count = stats.get("episodeCount", 0)
            ep_file_count = stats.get("episodeFileCount", 0)
            size = stats.get("sizeOnDisk", 0)
            
            total_episodes += ep_count
            total_episode_files += ep_file_count
            total_size += size
            
            if size > 0:
                series_sizes.append(size)
            if ep_count > 0:
                episode_counts.append(ep_count)
        
        metrics['sonarr_episodes_total'] = total_episodes
        metrics['sonarr_episodes_downloaded'] = total_episode_files
        metrics['sonarr_episodes_missing'] = total_episodes - total_episode_files
        metrics['sonarr_disk_usage_bytes'] = total_size
        
        # Averages
        if series_sizes:
            metrics['sonarr_avg_series_size_bytes'] = sum(series_sizes) / len(series_sizes)
        if episode_counts:
            metrics['sonarr_avg_episodes_per_series'] = sum(episode_counts) / len(episode_counts)
        
        # Genre breakdown
        genre_counts = defaultdict(int)
        for show in series:
            for genre in show.get("genres", []):
                genre_counts[genre] += 1
        metrics['sonarr_genres'] = dict(genre_counts)
        
        # Status breakdown
        status_counts = defaultdict(int)
        for show in series:
            status = show.get("status", "unknown")
            status_counts[status] += 1
        metrics['sonarr_series_by_status'] = dict(status_counts)
        
        # Episodes added over time (cumulative)
        date_counts = defaultdict(int)
        for show in series:
            added = show.get("added")
            episode_count = show.get("statistics", {}).get("episodeFileCount", 0)
            if added and episode_count > 0:
                date_str = added.split("T")[0]
                date_counts[date_str] += episode_count
        
        # Calculate cumulative
        cumulative = {}
        total = 0
        for date in sorted(date_counts.keys()):
            total += date_counts[date]
            cumulative[date] = total
        metrics['sonarr_cumulative_episodes'] = cumulative
        
        # Get file types from a sample of episodes (to avoid too many API calls)
        # We'll just get from the first few series
        filetype_counts = defaultdict(int)
        video_codec_counts = defaultdict(int)
        audio_codec_counts = defaultdict(int)
        
        for show in series[:10]:  # Sample first 10 shows
            episodes = self._get("episode", {"seriesId": show["id"]})
            if episodes:
                for ep in episodes[:5]:  # Sample first 5 episodes per show
                    ep_file = ep.get("episodeFile")
                    if ep_file:
                        # File type
                        path = ep_file.get("relativePath", "")
                        if path:
                            ext = path.split(".")[-1].lower()
                            filetype_counts[ext] += 1
                        
                        # Codecs
                        media_info = ep_file.get("mediaInfo", {})
                        video_codec = media_info.get("videoCodec", "Unknown")
                        audio_codec = media_info.get("audioCodec", "Unknown")
                        
                        # Normalize video codec
                        codec_map = {'x265': 'HEVC', 'h265': 'HEVC', 'x264': 'H.264', 'h264': 'H.264'}
                        video_codec = codec_map.get(video_codec, video_codec)
                        
                        video_codec_counts[video_codec] += 1
                        audio_codec_counts[audio_codec] += 1
        
        if filetype_counts:
            metrics['sonarr_filetypes'] = dict(filetype_counts)
            metrics['sonarr_video_codecs'] = dict(video_codec_counts)
            metrics['sonarr_audio_codecs'] = dict(audio_codec_counts)
        
        # Queue info
        queue = self._get("queue")
        if queue:
            records = queue.get("records", [])
            metrics['sonarr_queue_total'] = len(records)
            metrics['sonarr_queue_downloading'] = len([r for r in records if r.get("status") == "downloading"])
        
        logger.info(f"Collected Sonarr metrics: {total_series} series, {total_episode_files} episodes")
        return metrics


class JellyfinCollector:
    """Collects metrics from Jellyfin"""
    
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {"X-Emby-Token": api_key}
        self.session = requests.Session()
    
    def _get(self, endpoint: str, params: Dict = None) -> Any:
        """Make GET request to Jellyfin API"""
        try:
            url = f"{self.url}/{endpoint}"
            response = self.session.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            return None
    
    def _post(self, endpoint: str, data: Dict = None) -> Any:
        """Make POST request to Jellyfin API"""
        try:
            url = f"{self.url}/{endpoint}"
            headers = {
                **self.headers,
                "Content-Type": "application/json"
            }
            response = self.session.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting to {endpoint}: {e}")
            return None
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect all Jellyfin metrics"""
        metrics = {}
        
        # Get active sessions
        sessions = self._get("Sessions")
        if sessions:
            active_streams = [s for s in sessions if s.get("NowPlayingItem")]
            metrics['jellyfin_active_streams'] = len(active_streams)
            
            # Breakdown by media type
            stream_types = defaultdict(int)
            for session in active_streams:
                media_type = session.get("NowPlayingItem", {}).get("Type", "Unknown")
                stream_types[media_type] += 1
            metrics['jellyfin_streams_by_type'] = dict(stream_types)
        else:
            metrics['jellyfin_active_streams'] = 0
        
        # Get users
        users = self._get("Users")
        if users:
            metrics['jellyfin_users_total'] = len(users)
            user_ids = [u["Id"] for u in users]
        else:
            user_ids = []
        
        # Playback statistics (requires user_usage_stats plugin)
        try:
            query_data = {
                "CustomQueryString": """
                    SELECT ROWID, * FROM PlaybackActivity 
                    WHERE DateCreated >= datetime('now', '-30 days') 
                    ORDER BY DateCreated DESC
                """,
                "ReplaceUserId": True
            }
            headers_custom = {
                "Accept": "application/json",
                "Authorization": f"MediaBrowser Token={self.api_key}",
                "Content-Type": "application/json"
            }
            response = self.session.post(
                f"{self.url}/user_usage_stats/submit_custom_query",
                json=query_data,
                headers=headers_custom,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                columns = data.get("colums", [])  # Note: API typo
                
                # Count playback methods
                playback_methods = defaultdict(int)
                for row in results:
                    playback_data = dict(zip(columns, row))
                    method = playback_data.get("PlaybackMethod", "Unknown")
                    playback_methods[method] += 1
                
                metrics['jellyfin_playback_methods'] = dict(playback_methods)
                metrics['jellyfin_playback_count_30d'] = len(results)
                
                # Heatmap data - playback by hour
                hour_counts = defaultdict(int)
                for row in results:
                    playback_data = dict(zip(columns, row))
                    date_created = playback_data.get("DateCreated")
                    if date_created:
                        try:
                            dt = datetime.strptime(date_created[:13], "%Y-%m-%d %H")
                            hour_counts[dt.hour] += 1
                        except:
                            pass
                
                metrics['jellyfin_playback_by_hour'] = dict(hour_counts)
        except Exception as e:
            logger.warning(f"Could not fetch playback stats (user_usage_stats plugin may not be installed): {e}")
        
        # User activity (30 days)
        try:
            response = self._get("user_usage_stats/user_activity", {"days": 30, "timezoneOffset": 0})
            if response:
                user_activity = {}
                for user in response:
                    username = user.get("user_name", "Unknown")
                    play_count = user.get("total_count", 0)
                    user_activity[username] = play_count
                metrics['jellyfin_user_play_counts'] = user_activity
        except Exception as e:
            logger.warning(f"Could not fetch user activity: {e}")
        
        # Popular movies (30 days)
        if user_ids:
            try:
                for user_id in user_ids[:1]:  # Just use first user for popular content
                    movies = self._get("user_usage_stats/MoviesReport", {
                        "days": 30,
                        "UserId": user_id,
                        "timezoneOffset": 0
                    })
                    if movies:
                        # Top 10 movies
                        top_movies = sorted(movies, key=lambda x: x.get("count", 0), reverse=True)[:10]
                        movie_counts = {m.get("label", "Unknown"): m.get("count", 0) for m in top_movies}
                        metrics['jellyfin_top_movies'] = movie_counts
                        break
            except Exception as e:
                logger.warning(f"Could not fetch popular movies: {e}")
            
            # Popular shows (30 days)
            try:
                for user_id in user_ids[:1]:
                    shows = self._get("user_usage_stats/GetTvShowsReport", {
                        "days": 30,
                        "UserId": user_id,
                        "timezoneOffset": 0
                    })
                    if shows:
                        # Top 10 shows
                        top_shows = sorted(shows, key=lambda x: x.get("count", 0), reverse=True)[:10]
                        show_counts = {s.get("label", "Unknown"): s.get("count", 0) for s in top_shows}
                        metrics['jellyfin_top_shows'] = show_counts
                        break
            except Exception as e:
                logger.warning(f"Could not fetch popular shows: {e}")
        
        logger.info(f"Collected Jellyfin metrics: {metrics.get('jellyfin_active_streams', 0)} active streams")
        return metrics


class MediaExporter:
    """Main Prometheus exporter class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.radarr = None
        self.sonarr = None
        self.jellyfin = None
        
        # Initialize collectors
        if config.RADARR_URL and config.RADARR_API_KEY:
            self.radarr = RadarrCollector(config.RADARR_URL, config.RADARR_API_KEY, config.TMDB_API_KEY)
            logger.info("Radarr collector initialized")
        
        if config.SONARR_URL and config.SONARR_API_KEY:
            self.sonarr = SonarrCollector(config.SONARR_URL, config.SONARR_API_KEY)
            logger.info("Sonarr collector initialized")
        
        if config.JELLYFIN_URL and config.JELLYFIN_API_KEY:
            self.jellyfin = JellyfinCollector(config.JELLYFIN_URL, config.JELLYFIN_API_KEY)
            logger.info("Jellyfin collector initialized")
        
        # Prometheus metrics
        self.gauges = {}
    
    def _get_or_create_gauge(self, name: str, description: str, labels: List[str] = None) -> Gauge:
        """Get or create a Prometheus Gauge"""
        if name not in self.gauges:
            self.gauges[name] = Gauge(name, description, labels or [])
        return self.gauges[name]
    
    def export_metrics(self, metrics: Dict[str, Any], prefix: str):
        """Export metrics to Prometheus"""
        for key, value in metrics.items():
            metric_name = f"{prefix}_{key}" if not key.startswith(prefix) else key
            
            if isinstance(value, (int, float)):
                # Simple numeric metric
                gauge = self._get_or_create_gauge(metric_name, f"{metric_name} value")
                gauge.set(value)
            
            elif isinstance(value, dict):
                # Labeled metric
                if not value:
                    continue
                    
                # Determine if values are numeric or need special handling
                sample_value = next(iter(value.values()))
                
                if isinstance(sample_value, (int, float)):
                    # Create labeled gauge
                    gauge = self._get_or_create_gauge(
                        metric_name,
                        f"{metric_name} breakdown",
                        ['label']
                    )
                    for label, val in value.items():
                        gauge.labels(label=str(label)).set(val)
    
    def collect_and_export(self):
        """Collect metrics from all sources and export"""
        logger.info("Starting metric collection...")
        
        # Collect from Radarr
        if self.radarr:
            try:
                radarr_metrics = self.radarr.collect_metrics()
                self.export_metrics(radarr_metrics, 'radarr')
            except Exception as e:
                logger.error(f"Error collecting Radarr metrics: {e}")
        
        # Collect from Sonarr
        if self.sonarr:
            try:
                sonarr_metrics = self.sonarr.collect_metrics()
                self.export_metrics(sonarr_metrics, 'sonarr')
            except Exception as e:
                logger.error(f"Error collecting Sonarr metrics: {e}")
        
        # Collect from Jellyfin
        if self.jellyfin:
            try:
                jellyfin_metrics = self.jellyfin.collect_metrics()
                self.export_metrics(jellyfin_metrics, 'jellyfin')
            except Exception as e:
                logger.error(f"Error collecting Jellyfin metrics: {e}")
        
        logger.info("Metric collection completed")
    
    def run(self):
        """Run the exporter"""
        # Start Prometheus HTTP server
        start_http_server(self.config.EXPORTER_PORT)
        logger.info(f"Prometheus exporter started on port {self.config.EXPORTER_PORT}")
        
        # Collect metrics periodically
        while True:
            try:
                self.collect_and_export()
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
            
            time.sleep(self.config.SCRAPE_INTERVAL)


def main():
    """Main entry point"""
    logger.info("Starting Media Services Prometheus Exporter")
    
    config = Config()
    
    # Validate configuration
    if not any([
        config.RADARR_URL,
        config.SONARR_URL,
        config.JELLYFIN_URL
    ]):
        logger.error("No services configured! Please set at least one of RADARR_URL, SONARR_URL, or JELLYFIN_URL")
        return
    
    exporter = MediaExporter(config)
    exporter.run()


if __name__ == "__main__":
    main()
