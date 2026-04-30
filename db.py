import logging

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Базовый класс моделей
SqlAlchemyBase = declarative_base()

Session = None


# Подключение базы
def init_db(db_file):
    global Session
    engine = sa.create_engine(f"sqlite:///{db_file}?check_same_thread=False")
    Session = sessionmaker(bind=engine)

    # Модели для создания таблиц
    import db_models
    SqlAlchemyBase.metadata.create_all(engine)
    logger.info("База данных подключена: %s", db_file)


# Новая сессия базы
def create_session():
    return Session()
