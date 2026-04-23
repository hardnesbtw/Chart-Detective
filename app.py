from flask import Flask, jsonify

import db
from config import Config
from db_models import Game, Round, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_db(app.config["DATABASE_PATH"])

    @app.route("/")
    def index():
        return jsonify(
            {
                "status": "ok",
                "message": "Chart Detective app is running",
                "database": app.config["DATABASE_PATH"],
                "models": ["User", "Game", "Round"],
            }
        )

    @app.route("/db-status")
    def db_status():
        db_sess = db.create_session()
        try:
            return jsonify(
                {
                    "users": db_sess.query(User).count(),
                    "games": db_sess.query(Game).count(),
                    "rounds": db_sess.query(Round).count(),
                }
            )
        finally:
            db_sess.close()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
