from flask import Blueprint, render_template
from services import mlb_api

standings_bp = Blueprint("standings", __name__)


@standings_bp.route("/standings")
def index():
    standings = mlb_api.get_standings()
    return render_template("standings/index.html", standings=standings)
