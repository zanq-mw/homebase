import datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, render_template, abort, jsonify
from services import mlb_api, rss_service

teams_bp = Blueprint("teams", __name__, url_prefix="/teams")

LEADER_CATEGORIES = {
    "homeRuns":             "Home Runs",
    "onBasePlusSlugging":   "OPS",
    "strikeouts":           "Strikeouts",
    "earnedRunAverage":     "ERA",
}

def build_team_leaders(team_id):
    raw = mlb_api.get_team_leaders(team_id, list(LEADER_CATEGORIES.keys()), limit=1)
    leaders = []
    for cat, label in LEADER_CATEGORIES.items():
        entries = raw.get(cat, [])
        player = entries[0] if entries else None
        leaders.append({
            "label":  label,
            "player": player,
            "value":  player["value"] if player else None,
        })
    return leaders


@teams_bp.route("/")
def index():
    divisions = mlb_api.get_standings()
    return render_template("teams/index.html", divisions=divisions)


@teams_bp.route("/<int:team_id>")
def show(team_id):
    team = mlb_api.get_team(team_id)
    if not team:
        abort(404)
    roster = mlb_api.get_roster_with_stats(team_id)
    news = rss_service.get_team_news(team_id, limit=10)
    schedule = mlb_api.get_team_schedule(team_id)
    standings = mlb_api.get_standings()
    team_record = None
    for div_data in standings:
        for i, tr in enumerate(div_data["teamRecords"]):
            if tr["team"]["id"] == team_id:
                team_record = {
                    "rank": i + 1,
                    "wins": tr["wins"],
                    "losses": tr["losses"],
                    "pct": tr["winningPercentage"],
                    "gb": tr["gamesBack"],
                    "division": div_data["division"]["name"],
                }
                break
        if team_record:
            break
    return render_template(
        "teams/show.html",
        team=team,
        roster=roster,
        news=news,
        schedule=schedule,
        team_record=team_record,
        current_year=datetime.date.today().year,
        today_et=datetime.datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
        team_leaders=build_team_leaders(team_id),
    )


@teams_bp.route("/<int:team_id>/live")
def api_team_live(team_id):
    return jsonify(mlb_api.get_team_schedule(team_id))
