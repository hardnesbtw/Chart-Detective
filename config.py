import os
from dotenv import load_dotenv

load_dotenv()

# Пути проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')


# Настройки приложения
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'chart_detective.db'))
    DATA_DIR = DATA_DIR
    APPLE_MUSIC_COUNTRY_SLUG_PATH = os.path.join(DATA_DIR, 'apple_music_country_slug.json')
    AVAILABLE_COUNTRIES_PATH = os.path.join(DATA_DIR, 'available_countries.json')
    CONTINENT_GROUPS_PATH = os.path.join(DATA_DIR, 'continent_groups.json')
    COUNTRY_NEIGHBORS_PATH = os.path.join(DATA_DIR, 'country_neighbors.json')
    ROUNDS_PER_GAME = 3
    ROUND_TIME_SECONDS = 60
    TRACKS_PER_ROUND = 5
