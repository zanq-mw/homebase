from flask import Flask
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from blueprints.home.routes import home_bp
    from blueprints.standings.routes import standings_bp
    from blueprints.teams.routes import teams_bp
    from blueprints.players.routes import players_bp
    from blueprints.leaderboards.routes import leaderboards_bp
    from blueprints.search.routes import search_bp
    from blueprints.schedule.routes import schedule_bp
    from blueprints.games.routes import games_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(standings_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(players_bp)
    app.register_blueprint(leaderboards_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(games_bp)

    @app.context_processor
    def inject_nav_divisions():
        from services.mlb_api import get_standings
        try:
            standings = get_standings()
        except Exception:
            standings = []
        return {"nav_divisions": standings}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
