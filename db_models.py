import datetime

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from db import SqlAlchemyBase
from country_neighbors import calculate_score


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    login = sa.Column(sa.String(50), unique=True, index=True, nullable=False)
    password = sa.Column(sa.String(255), nullable=False)
    nickname = sa.Column(sa.String(50), unique=True, index=True, nullable=False)
    game_count = sa.Column(sa.Integer, default=0, nullable=False)
    best_score = sa.Column(sa.Integer, default=0, nullable=False)
    registered_at = sa.Column(sa.DateTime, default=datetime.datetime.now, nullable=False)

    games = relationship('Game', back_populates='user')

    def register(self, db_sess):
        """Регистрирует пользователя. Возвращает строку ошибки или None."""
        if db_sess.query(User).filter(User.login == self.login).first():
            return 'Пользователь с таким логином уже существует'
        if db_sess.query(User).filter(User.nickname == self.nickname).first():
            return 'Пользователь с таким никнеймом уже существует'
        db_sess.add(self)
        db_sess.commit()
        return None

    def login_user(self, password):
        """Проверяет пароль. Возвращает True если верный."""
        return check_password_hash(self.password, password)

    def get_profile_data(self):
        return {
            'id': self.id,
            'login': self.login,
            'nickname': self.nickname,
            'game_count': self.game_count,
            'best_score': self.best_score,
            'registered_at': self.registered_at,
        }

    def get_game_history(self, db_sess, limit=20):
        return db_sess.query(Game).filter(
            Game.user_id == self.id
        ).order_by(Game.played_at.desc()).limit(limit).all()


class Game(SqlAlchemyBase):
    __tablename__ = 'games'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'), nullable=True, index=True)
    total_score = sa.Column(sa.Integer, default=0, nullable=False)
    played_at = sa.Column(sa.DateTime, default=datetime.datetime.now, nullable=False)
    is_finished = sa.Column(sa.Boolean, default=False, nullable=False)

    user = relationship('User', back_populates='games')
    rounds = relationship('Round', back_populates='game', order_by='Round.round_number')

    def start_game(self, db_sess):
        """Сохраняет новую игру в базе данных."""
        db_sess.add(self)
        db_sess.commit()

    def add_round(self, db_sess, round_obj):
        """Добавляет раунд к игре и сохраняет в базе данных."""
        round_obj.game_id = self.id
        db_sess.add(round_obj)
        db_sess.commit()

    def calculate_total_score(self):
        return sum(r.round_score for r in self.rounds)

    def finish_game(self, db_sess):
        """Завершает игру: считает итоговый счёт и обновляет профиль пользователя."""
        self.total_score = self.calculate_total_score()
        self.is_finished = True

        if self.user_id:
            user = db_sess.get(User, self.user_id)
            if user:
                user.game_count += 1
                if self.total_score > user.best_score:
                    user.best_score = self.total_score

        db_sess.commit()

    def save_result(self, db_sess):
        """Записывает текущее состояние игры в базу данных."""
        db_sess.commit()


class Round(SqlAlchemyBase):
    __tablename__ = 'rounds'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    game_id = sa.Column(sa.Integer, sa.ForeignKey('games.id'), nullable=False, index=True)
    round_number = sa.Column(sa.Integer, nullable=False)
    country_code = sa.Column(sa.String(10), nullable=True)
    correct_country = sa.Column(sa.String(100), nullable=False)
    selected_country = sa.Column(sa.String(100), default='', nullable=False)
    round_score = sa.Column(sa.Integer, default=0, nullable=False)
    match_type = sa.Column(sa.String(20), default='no_answer', nullable=False)

    game = relationship('Game', back_populates='rounds')

    def check_answer(self, selected_country):
        """Проверяет ответ и считает очки. Возвращает True если ответ засчитан."""
        self.selected_country = selected_country
        self.round_score, self.match_type = calculate_score(self.correct_country, selected_country)
        return self.round_score > 0

    def calculate_score(self):
        return self.round_score

    def get_result(self):
        return {
            'round': self.round_number,
            'correct_country': self.correct_country,
            'selected_country': self.selected_country,
            'score': self.round_score,
            'match_type': self.match_type,
        }
