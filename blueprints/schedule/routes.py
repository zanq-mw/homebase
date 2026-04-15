from datetime import date as date_cls, timedelta
from flask import Blueprint, render_template, request
from services import mlb_api

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")


def _season_bounds(year):
    return (f"{year}-03-01", f"{year}-11-30")


def _season_present(year):
    today = date_cls.today().isoformat()
    return today if year == date_cls.today().year else f"{year}-10-30"


@schedule_bp.route("/")
def index():
    available_seasons = mlb_api.get_available_seasons()
    current_year = date_cls.today().year
    today = date_cls.today().isoformat()

    season = request.args.get("season", current_year, type=int)
    if season not in available_seasons:
        season = available_seasons[0] if available_seasons else current_year

    bounds = _season_bounds(season)

    selected_date = request.args.get("date")
    if not selected_date:
        selected_date = _season_present(season)

    if selected_date < bounds[0]:
        selected_date = bounds[0]
    if selected_date > bounds[1]:
        selected_date = bounds[1]

    data = mlb_api.get_full_schedule(season=season, date=selected_date)
    games = data["date_groups"][0]["games"] if data["date_groups"] else []

    d = date_cls.fromisoformat(selected_date)
    prev_date = (d - timedelta(days=1)).isoformat()
    next_date = (d + timedelta(days=1)).isoformat()

    present_date = _season_present(season)

    # Build dicts for JS consumption (Jinja tojson)
    season_bounds = {yr: [f"{yr}-03-01", f"{yr}-11-30"] for yr in available_seasons}
    season_present = {yr: _season_present(yr) for yr in available_seasons}

    return render_template(
        "schedule/index.html",
        games=games,
        selected_date=selected_date,
        season=season,
        available_seasons=available_seasons,
        prev_date=prev_date if prev_date >= bounds[0] else None,
        next_date=next_date if next_date <= bounds[1] else None,
        season_min=bounds[0],
        season_max=bounds[1],
        present_date=present_date,
        season_bounds=season_bounds,
        season_present=season_present,
        current_year=current_year,
    )
