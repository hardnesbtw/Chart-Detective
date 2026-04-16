import datetime
import sqlalchemy
from sqlalchemy import orm
from flask_login import UserMixin
from db import SqlAlchemyBase

class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    login = sqlalchemy.Column(sqlalchemy.String(50),
                              unique=True, index=True, nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    nickname = sqlalchemy.Column(sqlalchemy.String(50),
                                 unique=True, index=True, nullable=False)
    wins_count = sqlalchemy.Column(sqlalchemy.Integer,
                                   default=0, nullable=False)
    best_score = sqlalchemy.Column(sqlalchemy.Integer,
                                   default=0, nullable=False)
    registered_at = sqlalchemy.Column(sqlalchemy.DateTime,
                                      default=datetime.datetime.now,
                                      nullable=False)

    games = orm.relationship("Game", back_populates='user')

    def __repr__(self):
        return f"<User> {self.id} {self.login} {self.nickname}"


class Game(SqlAlchemyBase):
    __tablename__ = 'games'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer,
                                sqlalchemy.ForeignKey('users.id'),
                                index=True, nullable=False)
    score = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    played_at = sqlalchemy.Column(sqlalchemy.DateTime,
                                  default=datetime.datetime.now,
                                  nullable=False)

    user = orm.relationship('User', back_populates='games')

    def __repr__(self):
        return f"<Game> {self.id} {self.user_id} {self.score}"