from flask import Blueprint, render_template, abort
from services import mlb_api

players_bp = Blueprint("players", __name__, url_prefix="/players")


@players_bp.route("/<int:player_id>")
def show(player_id):
    bio = mlb_api.get_player_bio(player_id)
    if not bio:
        abort(404)
    stats = mlb_api.get_player_stats(player_id)
    game_log_splits = mlb_api.get_player_game_log(player_id)
    from services.stats_utils import last_n_games
    recent_games = last_n_games(game_log_splits, n=7)
    return render_template(
        "players/show.html",
        bio=bio,
        stats=stats,
        recent_games=recent_games,
    )
