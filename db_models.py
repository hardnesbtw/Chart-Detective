import datetime

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from werkzeug.security import check_password_hash

from db import SqlAlchemyBase
from country_neighbors import calculate_score


# Пользователь
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

    def register(self, db_session):
        if db_session.query(User).filter(User.login == self.login).first():
            return 'Пользователь с таким логином уже существует'
        if db_session.query(User).filter(User.nickname == self.nickname).first():
            return 'Пользователь с таким никнеймом уже существует'
        db_session.add(self)
        db_session.commit()
        return None

    def login_user(self, password):
        return check_password_hash(self.password, password)

    def get_game_history(self, db_session, limit=20):
        return db_session.query(Game).filter(
            Game.user_id == self.id,
            Game.is_finished.is_(True),
        ).order_by(Game.played_at.desc()).limit(limit).all()


# Игра
class Game(SqlAlchemyBase):
    __tablename__ = 'games'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'), nullable=True, index=True)
    total_score = sa.Column(sa.Integer, default=0, nullable=False)
    played_at = sa.Column(sa.DateTime, default=datetime.datetime.now, nullable=False)
    is_finished = sa.Column(sa.Boolean, default=False, nullable=False)

    user = relationship('User', back_populates='games')
    rounds = relationship('Round', back_populates='game', order_by='Round.round_number')

    def start_game(self, db_session):
        db_session.add(self)
        db_session.commit()

    def add_round(self, db_session, round_data):
        round_data.game_id = self.id
        db_session.add(round_data)
        db_session.commit()

    def finish_game(self, db_session):
        self.total_score = sum(r.round_score for r in self.rounds)
        self.is_finished = True

        user = db_session.get(User, self.user_id) if self.user_id else None
        if user:
            user.game_count += 1
            if self.total_score > user.best_score:
                user.best_score = self.total_score

        db_session.commit()


# Раунд
class Round(SqlAlchemyBase):
    __tablename__ = 'rounds'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    game_id = sa.Column(sa.Integer, sa.ForeignKey('games.id'), nullable=False, index=True)
    round_number = sa.Column(sa.Integer, nullable=False)
    correct_country = sa.Column(sa.String(100), nullable=False)
    selected_country = sa.Column(sa.String(100), default='', nullable=False)
    round_score = sa.Column(sa.Integer, default=0, nullable=False)
    match_type = sa.Column(sa.String(20), default='no_answer', nullable=False)

    game = relationship('Game', back_populates='rounds')

    def check_answer(self, selected_country):
        self.selected_country = selected_country
        self.round_score, self.match_type = calculate_score(self.correct_country, selected_country)
        return self.round_score > 0

    def get_result(self):
        return {
            'round': self.round_number,
            'correct_country': self.correct_country,
            'selected_country': self.selected_country,
            'score': self.round_score,
            'match_type': self.match_type,
        }
