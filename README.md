# Chart Detective

Веб-игра, в которой нужно угадать страну по её музыкальному чарту. Игрок слушает топ-5 треков из случайной страны и выбирает ответ из списка — за точное попадание начисляется максимум очков, за соседние страны — частично.

## Возможности

- Регистрация, вход и личный кабинет с историей игр
- Игра из нескольких раундов с таймером
- Топ-чарты в реальном времени из SoundCharts API
- Воспроизведение MP3 прямо в браузере (через Apify + локальный кэш)
- Поиск и группировка стран по континентам
- Светлая и тёмная темы

## Стек

**Backend:** Python · Flask · Flask-Login · SQLAlchemy · SQLite
**Frontend:** Jinja2 · CSS · vanilla JS · Tabler Icons
**Внешние API:** SoundCharts (чарты), Apify (MP3 со Spotify)

## Установка

```bash
git clone https://github.com/hardnesbtw/Chart-Detective.git
cd Chart-Detective

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env               # затем впишите свои ключи
```

В `.env` нужно указать:

| Переменная         | Описание                                  |
|--------------------|-------------------------------------------|
| `SECRET_KEY`       | Секрет Flask-сессии                       |
| `APP_ID`, `API_KEY`| Ключи SoundCharts                         |
| `APIFY_API_TOKEN`  | Токен Apify (для MP3)                     |
| `DATABASE_PATH`    | Путь к SQLite (по умолчанию `chart_detective.db`) |

Для получения API-ключей для тестирования проекта обратитесь к разработчикам в Telegram: [@coawy](https://t.me/coawy) или [@hardnesbtw](https://t.me/hardnesbtw).

## Запуск

```bash
python app.py
```

Приложение поднимется на http://localhost:5000.

## Структура

```
.
├── app.py                  # Flask-приложение и маршруты
├── config.py               # Конфигурация
├── db.py, db_models.py     # SQLAlchemy: User, Game, Round
├── get_chart.py            # Сервис SoundCharts + Apify
├── country_neighbors.py    # Логика подсчёта очков по соседям
├── data/                   # JSON со списками стран
├── templates/              # Jinja2-шаблоны
└── static/                 # CSS, JS, иконки, кэш аудио
```

## Подсчёт очков

| Результат                  | Очки |0
|----------------------------|------|
| Точное попадание           | 100  |
| Соседняя страна (1-й круг) | 700   |
| Соседняя страна (2-й круг) | 500   |
| Промах / нет ответа        | 0    |
