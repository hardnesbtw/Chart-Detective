import json
import random
import logging
import os
import shutil

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

import db
from db_models import User, Game, Round
from config import Config
from country_neighbors import MAX_SCORE_PER_ROUND
from get_chart import SoundChartsService


# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Создание приложения
app = Flask(__name__)
app.config.from_object(Config)

db.init_db(app.config['DATABASE_PATH'])

# Очищаем аудиокэш при каждом старте — файлы из предыдущей сессии уже сироты
shutil.rmtree(Config.AUDIO_CACHE_DIR, ignore_errors=True)
os.makedirs(Config.AUDIO_CACHE_DIR)
shutil.rmtree(Config.IMAGE_CACHE_DIR, ignore_errors=True)
os.makedirs(Config.IMAGE_CACHE_DIR)

# Вход пользователей
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Войдите в систему для доступа к этой странице'
login_manager.login_message_category = 'error'

# Сервис музыки
music_service = SoundChartsService()


# Слово "страна"
@app.template_filter('country_plural')
def country_word(count):
    mod10 = count % 10
    mod100 = count % 100
    if mod10 == 1 and mod100 != 11:
        return 'страна'
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return 'страны'
    return 'стран'


@app.template_filter('country_display')
def country_display_name(country_name):
    return COUNTRY_DISPLAY_NAMES.get(country_name, country_name)


# Данные стран
with open(Config.AVAILABLE_COUNTRIES_PATH, encoding='utf-8') as f:
    ISO_TO_COUNTRY = json.load(f)

with open(Config.COUNTRY_DISPLAY_NAMES_PATH, encoding='utf-8') as f:
    COUNTRY_DISPLAY_NAMES = json.load(f)

with open(Config.APPLE_MUSIC_COUNTRY_SLUG_PATH, encoding='utf-8') as f:
    APPLE_MUSIC_COUNTRY_SLUGS = json.load(f)

with open(Config.CONTINENT_GROUPS_PATH, encoding='utf-8') as f:
    CONTINENT_DEFINITIONS = json.load(f)

COUNTRY_TO_ISO = {name: iso for iso, name in ISO_TO_COUNTRY.items()}

# Страны для игры
COUNTRIES = {}

for country in APPLE_MUSIC_COUNTRY_SLUGS:
    iso = COUNTRY_TO_ISO.get(country)
    if iso:
        iso = str(iso).strip().upper()
        COUNTRIES[iso] = country

missing = [c for c in APPLE_MUSIC_COUNTRY_SLUGS if c not in COUNTRY_TO_ISO]
if missing:
    raise RuntimeError(f"Нет ISO-кода для стран: {', '.join(sorted(missing))}")


def make_country_groups():
    continent_map = {}
    for group in CONTINENT_DEFINITIONS:
        for code in group['codes']:
            continent_map[str(code).strip().upper()] = group['id']

    groups_by_id = {}
    for group in CONTINENT_DEFINITIONS:
        groups_by_id[group['id']] = {
            'id': group['id'],
            'label': group['label'],
            'icon': group['icon'],
            'countries': [],
        }

    other_group = {
        'id': 'other',
        'label': 'Другие страны',
        'icon': 'ti ti-world',
        'countries': [],
    }

    for iso, name in COUNTRIES.items():
        group_id = continent_map.get(iso)
        if group_id:
            group = groups_by_id[group_id]
        else:
            group = other_group

        display_name = COUNTRY_DISPLAY_NAMES.get(name, name)
        group['countries'].append({
            'iso': iso,
            'value': name,
            'name': display_name,
            'search_name': f'{name} {display_name}'.casefold(),
        })

    groups = []
    for group_info in CONTINENT_DEFINITIONS:
        group = groups_by_id[group_info['id']]
        if group['countries']:
            groups.append(group)

    if other_group['countries']:
        groups.append(other_group)

    for group in groups:
        group['countries'].sort(key=lambda c: c['name'].casefold())

    return groups


COUNTRY_GROUPS = make_country_groups()

countries_count = sum(len(group['countries']) for group in COUNTRY_GROUPS)


# Загрузка пользователя
@login_manager.user_loader
def load_user(user_id):
    db_session = db.create_session()
    user = db_session.get(User, int(user_id))
    if user:
        db_session.expunge(user)
    db_session.close()
    return user


# Удаление аудиофайлов раунда
def delete_round_audio(tracks):
    for track in tracks:
        url = track.get('mp3_url') or ''
        if not url.startswith('/static/audio_cache/'):
            continue
        path = os.path.join(Config.AUDIO_CACHE_DIR, url.split('/')[-1])
        try:
            os.remove(path)
        except OSError:
            pass


# Удаление изображений раунда
def delete_round_images(tracks):
    for track in tracks:
        url = track.get('image') or ''
        if not url.startswith('/static/image_cache/'):
            continue
        path = os.path.join(Config.IMAGE_CACHE_DIR, url.split('/')[-1])
        try:
            os.remove(path)
        except OSError:
            pass


# Очистка игры
def clear_game():
    session.pop('game_active', None)
    session.pop('game_id', None)
    session.pop('game_countries', None)
    session.pop('current_round', None)
    session.pop('game_score', None)
    session.pop('round_results', None)
    session.pop('round_tracks', None)


# Удаление незавершенной игры
def remove_unfinished_game():
    game_id = session.get('game_id')
    if not game_id:
        return

    for tracks in session.get('round_tracks', {}).values():
        delete_round_audio(tracks)
        delete_round_images(tracks)

    db_session = db.create_session()
    try:
        game = db_session.get(Game, game_id)
        if game and not game.is_finished:
            db_session.query(Round).filter(Round.game_id == game.id).delete()
            db_session.delete(game)
            db_session.commit()
    finally:
        db_session.close()


# Проверка конца игры
def is_game_done():
    return session.get('current_round', 0) >= len(session.get('game_countries', []))


# Сохранение раунда
def save_round(selected_country='', reason=None):
    round_index = session.get('current_round', 0)
    countries = session.get('game_countries', [])
    if round_index >= len(countries):
        return

    correct_country = countries[round_index]

    round_data = Round(
        game_id=session.get('game_id'),
        round_number=round_index + 1,
        correct_country=correct_country,
    )

    if reason:
        round_data.match_type = reason
    else:
        round_data.check_answer(selected_country)

    db_session = db.create_session()
    try:
        game = db_session.get(Game, session.get('game_id'))
        if not game:
            logger.warning('Не найдена игра %s при сохранении раунда', session.get('game_id'))
            clear_game()
            return
        game.add_round(db_session, round_data)
        round_result = round_data.get_result()
        round_score = round_data.round_score
    finally:
        db_session.close()

    results = session.get('round_results', [])
    results.append(round_result)
    session['round_results'] = results
    session['game_score'] = session.get('game_score', 0) + round_score
    session['current_round'] = round_index + 1


# Главная
@app.route('/')
def index():
    return render_template('index.html')


# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_text = request.form.get('login', '').strip()
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')
        password_repeat = request.form.get('password_repeat', '')

        error = None
        if not login_text or not nickname or not password or not password_repeat:
            error = 'Все поля обязательны для заполнения'
        elif len(login_text) < 3 or len(login_text) > 50:
            error = 'Логин должен быть от 3 до 50 символов'
        elif len(nickname) < 2 or len(nickname) > 50:
            error = 'Никнейм должен быть от 2 до 50 символов'
        elif password != password_repeat:
            error = 'Пароли не совпадают'
        elif len(password) < 6:
            error = 'Пароль должен содержать минимум 6 символов'

        if error:
            flash(error, 'error')
            return render_template('register.html')

        user = User(
            login=login_text,
            nickname=nickname,
            password=generate_password_hash(password),
        )
        db_session = db.create_session()
        error = user.register(db_session)
        db_session.close()

        if error:
            flash(error, 'error')
            return render_template('register.html')

        flash('Регистрация успешна! Теперь вы можете войти', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_text = request.form.get('login', '').strip()
        password = request.form.get('password', '')

        if not login_text or not password:
            flash('Все поля обязательны для заполнения', 'error')
            return render_template('login.html')

        db_session = db.create_session()
        user = db_session.query(User).filter(User.login == login_text).first()

        if not user or not user.login_user(password):
            db_session.close()
            flash('Неверный логин или пароль', 'error')
            return render_template('login.html')

        nickname = user.nickname
        login_user(user, remember=True)
        db_session.close()

        flash(f'Добро пожаловать, {nickname}!', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')


# Выход
@app.route('/logout')
@login_required
def logout():
    remove_unfinished_game()
    clear_game()
    logout_user()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('index'))


# Профиль
@app.route('/profile')
@login_required
def profile():
    db_session = db.create_session()
    user = db_session.get(User, current_user.id)
    games = user.get_game_history(db_session, limit=20)

    if games:
        average_score = round(sum(g.total_score for g in games) / len(games))
    else:
        average_score = None

    db_session.close()
    return render_template('profile.html', user=user, games=games, average_score=average_score)


# Игра
@app.route('/game/start')
def game_start():
    remove_unfinished_game()
    clear_game()

    countries = list(COUNTRIES.values())
    if len(countries) < Config.ROUNDS_PER_GAME:
        flash('Недостаточно доступных стран для игры', 'error')
        return redirect(url_for('index'))

    game_countries = random.sample(countries, Config.ROUNDS_PER_GAME)

    db_session = db.create_session()
    game = Game(user_id=current_user.id if current_user.is_authenticated else None)
    game.start_game(db_session)
    game_id = game.id
    db_session.close()

    session['game_active'] = True
    session['game_id'] = game_id
    session['game_countries'] = game_countries
    session['current_round'] = 0
    session['game_score'] = 0
    session['round_results'] = []
    return redirect(url_for('game'))


@app.route('/game')
def game():
    if not session.get('game_active'):
        flash('Начните новую игру', 'error')
        return redirect(url_for('index'))

    if is_game_done():
        return redirect(url_for('results'))

    current_round = session.get('current_round', 0)
    return render_template(
        'game.html',
        round_number=current_round + 1,
        total_rounds=Config.ROUNDS_PER_GAME,
        round_time=Config.ROUND_TIME_SECONDS,
        country_groups=COUNTRY_GROUPS,
        total_countries=countries_count,
        current_score=session.get('game_score', 0),
    )


@app.route('/api/game/data')
def game_data():
    if not session.get('game_active'):
        return jsonify({'status': 'inactive'}), 400

    if is_game_done():
        return jsonify({'status': 'finished'})

    current_round = session.get('current_round', 0)
    round_key = str(current_round)

    # Если треки уже загружены для этого раунда — отдаём из кэша
    cached = session.get('round_tracks', {})
    if round_key in cached:
        return jsonify({'status': 'ok', 'tracks': cached[round_key]})

    country = session['game_countries'][current_round]

    try:
        tracks = music_service.get_tracks(country, limit=Config.TRACKS_PER_ROUND)
    except Exception as e:
        logger.exception('Ошибка API для %s: %s', country, e)
        save_round(reason='error')
        return jsonify({'status': 'error', 'message': 'Ошибка загрузки музыки'})

    if not tracks:
        save_round(reason='skipped')
        return jsonify({'status': 'skipped', 'message': 'Треки не найдены'})

    cached[round_key] = tracks
    session['round_tracks'] = cached

    return jsonify({'status': 'ok', 'tracks': tracks})


@app.route('/game/answer', methods=['POST'])
def game_answer():
    if not session.get('game_active'):
        flash('Игра не активна', 'error')
        return redirect(url_for('index'))

    if is_game_done():
        return redirect(url_for('results'))

    # Защита от повторной отправки — раунд уже сохранён
    current_round = session.get('current_round', 0)
    if len(session.get('round_results', [])) > current_round:
        return redirect(url_for('round_result'))

    answer = request.form.get('selected_country', '').strip()
    save_round(selected_country=answer)

    # Удаляем медиафайлы и треки завершённого раунда
    cached = session.get('round_tracks', {})
    round_key = str(current_round)
    if round_key in cached:
        delete_round_audio(cached[round_key])
        delete_round_images(cached[round_key])
        del cached[round_key]
        session['round_tracks'] = cached

    return redirect(url_for('round_result'))


@app.route('/game/round-result')
def round_result():
    if not session.get('game_active'):
        return redirect(url_for('index'))

    results = session.get('round_results', [])
    if not results:
        return redirect(url_for('game'))

    is_last = session.get('current_round', 0) >= Config.ROUNDS_PER_GAME
    return render_template(
        'round_result.html',
        result=results[-1],
        total_rounds=Config.ROUNDS_PER_GAME,
        current_score=session.get('game_score', 0),
        is_last=is_last,
    )


@app.route('/results')
def results():
    if not session.get('game_active'):
        flash('Нет активной игры', 'error')
        return redirect(url_for('index'))

    if not is_game_done():
        flash('Сначала завершите все раунды', 'error')
        if session.get('round_results'):
            return redirect(url_for('round_result'))
        return redirect(url_for('game'))

    final_score = session.get('game_score', 0)
    round_results = session.get('round_results', [])
    max_possible = Config.ROUNDS_PER_GAME * MAX_SCORE_PER_ROUND

    db_session = db.create_session()
    game = db_session.get(Game, session.get('game_id'))
    if game:
        game.finish_game(db_session)
    db_session.close()

    clear_game()

    return render_template(
        'results.html',
        final_score=final_score,
        max_possible=max_possible,
        round_results=round_results,
    )


@app.errorhandler(404)
def page_not_found(_):
    return render_template('error.html', error_code=404, error_message='Страница не найдена'), 404


@app.errorhandler(500)
def server_error(_):
    return render_template('error.html', error_code=500, error_message='Внутренняя ошибка сервера'), 500


@app.errorhandler(403)
def forbidden(_):
    return render_template('error.html', error_code=403, error_message='Доступ запрещён'), 403


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/x-icon')


@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    return send_from_directory(app.static_folder, 'apple-touch-icon.png')


@app.route('/apple-touch-icon-precomposed.png')
def apple_touch_icon_precomposed():
    return send_from_directory(app.static_folder, 'apple-touch-icon-precomposed.png')


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes', 'on'})
