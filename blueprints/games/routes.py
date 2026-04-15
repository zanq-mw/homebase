from flask import Blueprint, render_template, abort, jsonify
from services import mlb_api

games_bp = Blueprint("games", __name__, url_prefix="/games")


@games_bp.route("/<int:game_pk>")
def show(game_pk):
    linescore = mlb_api.get_game_linescore(game_pk)
    boxscore = mlb_api.get_game_boxscore(game_pk)
    meta = mlb_api.get_game_meta(game_pk)
    if not boxscore or not meta:
        abort(404)
    return render_template(
        "games/show.html",
        game_pk=game_pk,
        linescore=linescore,
        boxscore=boxscore,
        meta=meta,
    )


@games_bp.route("/<int:game_pk>/live")
def api_game_live(game_pk):
    return jsonify({
        "linescore": mlb_api.get_game_linescore(game_pk),
        "boxscore": mlb_api.get_game_boxscore(game_pk),
    })
