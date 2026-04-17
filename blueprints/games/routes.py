import datetime
from flask import Blueprint, render_template, abort, jsonify
from services import mlb_api

games_bp = Blueprint("games", __name__, url_prefix="/games")

# Primary brand colors per team ID
_TEAM_COLORS = {
    108: "#BA0021",  # Angels
    109: "#A71930",  # Diamondbacks
    110: "#DF4601",  # Orioles
    111: "#BD3039",  # Red Sox
    112: "#0E3386",  # Cubs
    113: "#C6011F",  # Reds
    114: "#00385D",  # Guardians
    115: "#333366",  # Rockies
    116: "#0C2340",  # Tigers
    117: "#002D62",  # Astros
    118: "#004687",  # Royals
    119: "#005A9C",  # Dodgers
    120: "#AB0003",  # Nationals
    121: "#002D72",  # Mets
    133: "#003831",  # Athletics
    134: "#27251F",  # Pirates
    135: "#2F241D",  # Padres
    136: "#0C2C56",  # Mariners
    137: "#FD5A1E",  # Giants
    138: "#C41E3A",  # Cardinals
    139: "#092C5C",  # Rays
    140: "#003278",  # Rangers
    141: "#134A8E",  # Blue Jays
    142: "#002B5C",  # Twins
    143: "#E81828",  # Phillies
    144: "#CE1141",  # Braves
    145: "#27251F",  # White Sox
    146: "#00A3E0",  # Marlins
    147: "#003087",  # Yankees
    158: "#12284B",  # Brewers
}
_DEFAULT_COLOR = "#1a2d4a"


@games_bp.route("/<int:game_pk>")
def show(game_pk):
    linescore = mlb_api.get_game_linescore(game_pk)
    boxscore = mlb_api.get_game_boxscore(game_pk)
    meta = mlb_api.get_game_meta(game_pk)
    if not boxscore or not meta:
        abort(404)

    away_color = _TEAM_COLORS.get(meta["away"]["id"], _DEFAULT_COLOR)
    home_color = _TEAM_COLORS.get(meta["home"]["id"], _DEFAULT_COLOR)

    is_preview = linescore.get("status") not in ("Live", "Final")
    season_stats = None
    if is_preview:
        season = int(meta.get("game_date", "")[:4] or datetime.date.today().year)
        away_season = mlb_api.get_team_season_stats(meta["away"]["id"], season)
        home_season = mlb_api.get_team_season_stats(meta["home"]["id"], season)
        season_stats = {"away": away_season, "home": home_season}

    today = datetime.date.today()
    game_date = meta.get("game_date", "")
    _date_labels = {
        today.isoformat(): "Today",
        (today - datetime.timedelta(days=1)).isoformat(): "Yesterday",
        (today + datetime.timedelta(days=1)).isoformat(): "Tomorrow",
    }
    date_label = _date_labels.get(game_date, game_date)

    return render_template(
        "games/show.html",
        game_pk=game_pk,
        linescore=linescore,
        boxscore=boxscore,
        meta=meta,
        away_color=away_color,
        home_color=home_color,
        is_preview=is_preview,
        season_stats=season_stats,
        date_label=date_label,
    )


@games_bp.route("/<int:game_pk>/live")
def api_game_live(game_pk):
    return jsonify({
        "linescore": mlb_api.get_game_linescore(game_pk),
        "boxscore": mlb_api.get_game_boxscore(game_pk),
    })
