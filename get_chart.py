import os
import json
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from apify_client import ApifyClient
from dotenv import load_dotenv

from config import Config

logger = logging.getLogger(__name__)


load_dotenv()

with open(Config.APPLE_MUSIC_COUNTRY_SLUG_PATH, "r", encoding="utf-8") as f:
    COUNTRY_CODES = json.load(f)


class SoundChartsService:
    BASE_URL = "https://customer.api.soundcharts.com/api"

    def __init__(self):
        self.app_id = os.getenv("APP_ID")
        self.api_key = os.getenv("API_KEY")
        self.apify_token = os.getenv("APIFY_API_TOKEN")

    def get_chart(self, country_code, offset=0, limit=5):
        url = f"{self.BASE_URL}/v2.14/chart/song/{country_code}/ranking/latest"
        response = requests.get(
            url,
            headers={"x-app-id": self.app_id, "x-api-key": self.api_key},
            params={"offset": str(offset), "limit": str(limit)},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_spotify_url(self, song_uuid):
        url = f"{self.BASE_URL}/v2/song/{song_uuid}/identifiers"
        response = requests.get(
            url,
            headers={"x-app-id": self.app_id, "x-api-key": self.api_key},
            params={"platform": "spotify", "offset": "0", "limit": "1"},
            timeout=30,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return items[0].get("url") if items else None

    def get_top_tracks(self, country_code, limit=5):
        tracks = []
        offset = 0

        while len(tracks) < limit:
            chart = self.get_chart(country_code, offset=offset, limit=limit)
            items = chart.get("items", [])
            if not items:
                break

            page_tracks = []
            for item in items:
                song = item.get("song", {})
                if song.get("uuid"):
                    page_tracks.append({
                        "uuid": song.get("uuid"),
                        "title": song.get("name"),
                        "artist": song.get("creditName"),
                        "image": song.get("imageUrl"),
                        "spotify_url": None,
                    })

            if page_tracks:
                with ThreadPoolExecutor(max_workers=len(page_tracks)) as executor:
                    futures = {executor.submit(self.get_spotify_url, t["uuid"]): t for t in page_tracks}
                    for future in as_completed(futures):
                        track = futures[future]
                        try:
                            track["spotify_url"] = future.result()
                        except Exception:
                            track["spotify_url"] = None

            for track in page_tracks:
                if track["spotify_url"]:
                    tracks.append(track)
                    if len(tracks) == limit:
                        break

            offset += limit

        return tracks

    def get_tracks(self, country_name, limit=5):
        country_code = COUNTRY_CODES.get(country_name)
        if not country_code:
            raise ValueError(f"Страна '{country_name}' не найдена")

        tracks = self.get_top_tracks(country_code, limit=limit)

        if not tracks or not self.apify_token:
            for track in tracks:
                track["mp3_url"] = None
            return tracks

        client = ApifyClient(self.apify_token)
        spotify_links = [t["spotify_url"] for t in tracks]

        logger.info("Apify Actor запущен, ссылок: %d", len(spotify_links))
        result = client.actor("easyapi/spotify-music-mp3-downloader").call(
            run_input={
                "links": spotify_links,
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["BUYPROXIES94952"],
                },
            },
        )
        cdn_urls = _parse_apify_dataset(client, result["defaultDatasetId"], spotify_links)
        logger.info("CDN-ссылок получено: %d из %d", sum(1 for u in cdn_urls if u), len(tracks))

        local_urls = [None] * len(tracks)
        with ThreadPoolExecutor(max_workers=max(len(tracks), 1)) as executor:
            download_futures = {
                executor.submit(_download_mp3, cdn_urls[i], Config.AUDIO_CACHE_DIR): i
                for i in range(len(cdn_urls)) if cdn_urls[i]
            }
            for future in as_completed(download_futures):
                i = download_futures[future]
                try:
                    local_urls[i] = future.result()
                except Exception as e:
                    logger.error("Трек %d не скачался: %s", i, e)

        for i, track in enumerate(tracks):
            track["mp3_url"] = local_urls[i]

        return tracks


def _parse_apify_dataset(client, dataset_id, spotify_links):
    cdn_urls = []
    for idx, item in enumerate(client.dataset(dataset_id).iterate_items()):
        data = item.get("result")
        if not data or data.get("error"):
            spotify_url = spotify_links[idx] if idx < len(spotify_links) else "?"
            logger.warning("Apify error трек %d (%s)", idx, spotify_url)
            cdn_urls.append(None)
            continue
        files = data.get("medias", [])
        url = files[0].get("url") if files else None
        cdn_urls.append(url)
    return cdn_urls


def _download_mp3(cdn_url, cache_dir):
    name = hashlib.sha256(cdn_url.encode()).hexdigest()[:20] + '.mp3'
    path = os.path.join(cache_dir, name)

    if os.path.exists(path):
        return '/static/audio_cache/' + name

    resp = requests.get(cdn_url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
    return '/static/audio_cache/' + name
