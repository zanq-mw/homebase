from flask import Flask
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from services.cache import cache
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})

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

    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")

    @app.template_filter("game_time_et")
    def game_time_et(iso_str):
        """Convert ISO UTC game time to '7:10 PM ET' format."""
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            et = dt.astimezone(_ET)
            return et.strftime("%-I:%M %p") + " ET"
        except Exception:
            return iso_str

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
