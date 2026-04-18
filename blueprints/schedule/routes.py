from datetime import datetime as datetime_cls, timedelta
from zoneinfo import ZoneInfo
from flask import Blueprint, render_template, request
from services import mlb_api

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")

_ET = ZoneInfo("America/New_York")


@schedule_bp.route("/")
def index():
    available_seasons = mlb_api.get_available_seasons()
    _now_et = datetime_cls.now(_ET)
    current_year = _now_et.year
    today = _now_et.date().isoformat()

    season = request.args.get("season", current_year, type=int)
    if season not in available_seasons:
        season = available_seasons[0] if available_seasons else current_year

    season_start, season_end = mlb_api.get_season_dates(season)

    selected_date = request.args.get("date")
    if not selected_date:
        selected_date = today if season == current_year else season_end

    if selected_date < season_start:
        selected_date = season_start
    if selected_date > season_end:
        selected_date = season_end

    data = mlb_api.get_full_schedule(season=season, date=selected_date)
    games = data["date_groups"][0]["games"] if data["date_groups"] else []

    d = date_cls.fromisoformat(selected_date)
    prev_date = (d - timedelta(days=1)).isoformat()
    next_date = (d + timedelta(days=1)).isoformat()

    # Build dicts for JS consumption
    season_bounds   = {}
    season_present  = {}
    for yr in available_seasons:
        s, e = mlb_api.get_season_dates(yr)
        season_bounds[yr]  = [s, e]
        season_present[yr] = min(today, e) if yr == current_year else e

    # Jump-to-present: today clamped to current season end (handles off-season)
    current_year_end = season_bounds.get(current_year, [None, None])[1]
    jump_today = min(today, current_year_end) if current_year_end else today

    return render_template(
        "schedule/index.html",
        games=games,
        selected_date=selected_date,
        season=season,
        available_seasons=available_seasons,
        prev_date=prev_date if prev_date >= season_start else None,
        next_date=next_date if next_date <= season_end else None,
        season_min=season_start,
        season_max=season_end,
        present_date=today if season == current_year else season_end,
        today=jump_today,
        season_bounds=season_bounds,
        season_present=season_present,
        current_year=current_year,
    )
