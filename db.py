import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker

SqlAlchemyBase = declarative_base()

Session = None


def init_db(db_file):
    global Session
    engine = sa.create_engine(f"sqlite:///{db_file}?check_same_thread=False")
    Session = sessionmaker(bind=engine)

    import db_models  # noqa: F401
    SqlAlchemyBase.metadata.create_all(engine)
    print(f"База данных подключена: {db_file}")


def create_session():
    return Session()