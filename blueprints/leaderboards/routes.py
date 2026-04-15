from flask import Blueprint, render_template
from services import mlb_api

leaderboards_bp = Blueprint("leaderboards", __name__)

HITTING_CATEGORIES = ["homeRuns", "battingAverage", "onBasePlusSlugging", "runsBattedIn"]
PITCHING_CATEGORIES = ["earnedRunAverage", "strikeouts", "walksAndHitsPerInningPitched", "wins"]

CATEGORY_LABELS = {
    "homeRuns": "Home Runs",
    "battingAverage": "Batting Average",
    "onBasePlusSlugging": "OPS",
    "runsBattedIn": "RBI",
    "earnedRunAverage": "ERA",
    "strikeouts": "Strikeouts",
    "walksAndHitsPerInningPitched": "WHIP",
    "wins": "Wins",
}


@leaderboards_bp.route("/leaderboards")
def index():
    hitting = mlb_api.get_stat_leaders(HITTING_CATEGORIES, limit=10)
    pitching = mlb_api.get_stat_leaders(PITCHING_CATEGORIES, limit=10)
    return render_template(
        "leaderboards/index.html",
        hitting=hitting,
        pitching=pitching,
        hitting_categories=HITTING_CATEGORIES,
        pitching_categories=PITCHING_CATEGORIES,
        category_labels=CATEGORY_LABELS,
    )
