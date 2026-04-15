from flask import Blueprint, render_template, jsonify
from services import mlb_api, rss_service

home_bp = Blueprint("home", __name__)

LEADER_CATEGORIES = ["homeRuns", "battingAverage", "onBasePlusSlugging", "runsBattedIn"]


@home_bp.route("/")
def index():
    standings = mlb_api.get_standings()
    news = rss_service.get_mlb_news(limit=7)
    leaders = mlb_api.get_stat_leaders(LEADER_CATEGORIES, limit=5)
    todays_games = mlb_api.get_todays_games()
    return render_template(
        "home/index.html",
        standings=standings,
        news=news,
        leaders=leaders,
        leader_categories=LEADER_CATEGORIES,
        todays_games=todays_games,
    )


@home_bp.route("/api/games/today")
def api_games_today():
    return jsonify({"games": mlb_api.get_todays_games()})
