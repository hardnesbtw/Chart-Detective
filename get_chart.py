import os
import json
import logging
import contextlib
from pathlib import Path

import requests
from apify_client import ApifyClient
from dotenv import load_dotenv


load_dotenv()

logging.getLogger("apify_client").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)

_map_path = Path(__file__).parent / "apple_music_country_slug_map.json"
with open(_map_path, "r", encoding="utf-8") as f:
    COUNTRY_CODE_MAP = json.load(f)


class SpotifyService:
    base_url = "https://customer.api.soundcharts.com/api"
    access_token = None

    def __init__(self):
        self.app_id = os.getenv("APP_ID")
        self.api_key = os.getenv("API_KEY")
        self.apify_token = os.getenv("APIFY_API_TOKEN")

    def get_access_token(self):
        """Возвращает API-ключ для SoundCharts."""
        return self.api_key

    def get_country_chart(self, country_code, offset=0, limit=5):
        """Запрашивает чарт страны у SoundCharts."""
        url = f"{self.base_url}/v2.14/chart/song/{country_code}/ranking/latest"
        response = requests.get(
            url,
            headers={"x-app-id": self.app_id, "x-api-key": self.api_key},
            params={"offset": str(offset), "limit": str(limit)},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def extract_tracks(self, api_response):
        """Преобразует ответ API в список треков."""
        tracks = []
        for item in api_response.get("items", []):
            song = item.get("song", {})
            uuid = song.get("uuid")
            tracks.append({
                "uuid": uuid,
                "title": song.get("name"),
                "artist": song.get("creditName"),
                "image": song.get("imageUrl"),
                "spotify_url": self._get_spotify_url(uuid) if uuid else None,
            })
        return tracks

    def get_top_tracks(self, country_code, limit=5):
        """Возвращает треки."""
        tracks = []
        offset = 0
        while len(tracks) < limit:
            chart = self.get_country_chart(country_code, offset=offset, limit=limit)
            batch = self.extract_tracks(chart)
            if not batch:
                break
            for track in batch:
                if track["spotify_url"]:
                    tracks.append(track)
                    if len(tracks) == limit:
                        break
            offset += limit
        return tracks

    def _get_spotify_url(self, song_uuid):
        url = f"{self.base_url}/v2/song/{song_uuid}/identifiers"
        response = requests.get(
            url,
            headers={"x-app-id": self.app_id, "x-api-key": self.api_key},
            params={"platform": "spotify", "offset": "0", "limit": "1"},
            timeout=30,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return items[0].get("url") if items else None

    def _add_mp3_links(self, tracks):
        """Добавляет ссылки для треков"""
        if not tracks:
            return tracks

        client = ApifyClient(self.apify_token)
        links = [t["spotify_url"] for t in tracks]

        with open(os.devnull, "w") as devnull, \
             contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            run = client.actor("easyapi/spotify-music-mp3-downloader").call(
                run_input={"links": links}
            )

        mp3_links = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            result = item.get("result")
            if not result or result.get("error"):
                continue
            medias = result.get("medias", [])
            if medias:
                mp3_links.append(medias[0].get("url"))

        for i, track in enumerate(tracks):
            track["mp3_url"] = mp3_links[i] if i < len(mp3_links) else None
        return tracks

    def get_tracks_for_country(self, country_name, limit=5):
        code = COUNTRY_CODE_MAP.get(country_name)
        if not code:
            raise ValueError(f"Нет страны '{country_name}' в apple_music_country_slug_map.json")
        tracks = self.get_top_tracks(code, limit=limit)
        return self._add_mp3_links(tracks)