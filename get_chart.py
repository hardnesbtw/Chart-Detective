import os
import json

import requests
from apify_client import ApifyClient
from dotenv import load_dotenv

from config import Config


load_dotenv()

with open(Config.APPLE_MUSIC_COUNTRY_SLUG_PATH, "r", encoding="utf-8") as f:
    COUNTRY_CODES = json.load(f)


class SoundChartsService:
    base_url = "https://customer.api.soundcharts.com/api"

    def __init__(self):
        # Ключи API
        self.app_id = os.getenv("APP_ID")
        self.api_key = os.getenv("API_KEY")
        self.apify_token = os.getenv("APIFY_API_TOKEN")

    def get_country_chart(self, country_code, offset=0, limit=5):
        # Запрос чарта
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
        # Данные треков
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
        # Треки со Spotify
        tracks = []
        offset = 0
        while len(tracks) < limit:
            chart = self.get_country_chart(country_code, offset=offset, limit=limit)
            new_tracks = self.extract_tracks(chart)
            if not new_tracks:
                break
            for track in new_tracks:
                if track["spotify_url"]:
                    tracks.append(track)
                    if len(tracks) == limit:
                        break
            offset += limit
        return tracks

    def _get_spotify_url(self, song_uuid):
        # Ссылка Spotify
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
        # MP3 ссылки
        if not tracks:
            return tracks
        if not self.apify_token:
            for track in tracks:
                track["mp3_url"] = None
            return tracks

        client = ApifyClient(self.apify_token)
        spotify_links = [track["spotify_url"] for track in tracks]
        download_task = client.actor("easyapi/spotify-music-mp3-downloader").call(
            run_input={"links": spotify_links}
        )

        mp3_links = []
        for item in client.dataset(download_task["defaultDatasetId"]).iterate_items():
            download_result = item.get("result")
            if not download_result or download_result.get("error"):
                mp3_links.append(None)
                continue
            media_files = download_result.get("medias", [])
            mp3_links.append(media_files[0].get("url") if media_files else None)

        for index, track in enumerate(tracks):
            track["mp3_url"] = mp3_links[index] if index < len(mp3_links) else None
        return tracks

    def get_tracks_for_country(self, country_name, limit=5):
        # Треки страны
        country_code = COUNTRY_CODES.get(country_name)
        if not country_code:
            raise ValueError(f"Нет страны '{country_name}' в apple_music_country_slug.json")
        tracks = self.get_top_tracks(country_code, limit=limit)
        return self._add_mp3_links(tracks)
