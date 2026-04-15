from datetime import date as date_cls, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from services import mlb_api

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")

AVAILABLE_SEASONS = [2026, 2025, 2024]

# Approximate season bounds (min, max date) used to constrain the date picker
SEASON_BOUNDS = {
    2026: ("2026-03-01", "2026-11-30"),
    2025: ("2025-03-01", "2025-11-30"),
    2024: ("2024-03-01", "2024-11-30"),
}

# Default "present" date for past seasons
SEASON_PRESENT = {
    2025: "2025-10-30",
    2024: "2024-10-30",
}


@schedule_bp.route("/")
def index():
    season = request.args.get("season", 2026, type=int)
    if season not in AVAILABLE_SEASONS:
        season = 2026

    today = date_cls.today().isoformat()
    current_year = date_cls.today().year

    # Determine selected date
    selected_date = request.args.get("date")
    if not selected_date:
        if season == current_year:
            selected_date = today
        else:
            selected_date = SEASON_PRESENT.get(season, f"{season}-10-01")

    # Clamp to season bounds
    bounds = SEASON_BOUNDS.get(season, (f"{season}-03-01", f"{season}-11-30"))
    if selected_date < bounds[0]:
        selected_date = bounds[0]
    if selected_date > bounds[1]:
        selected_date = bounds[1]

    # Fetch games for selected date
    data = mlb_api.get_full_schedule(season=season, date=selected_date)
    games = data["date_groups"][0]["games"] if data["date_groups"] else []

    # Prev / next dates (day-by-day navigation)
    d = date_cls.fromisoformat(selected_date)
    prev_date = (d - timedelta(days=1)).isoformat()
    next_date = (d + timedelta(days=1)).isoformat()

    # Present date for this season
    if season == current_year:
        present_date = today
    else:
        present_date = SEASON_PRESENT.get(season, f"{season}-10-01")

    return render_template(
        "schedule/index.html",
        games=games,
        selected_date=selected_date,
        season=season,
        available_seasons=AVAILABLE_SEASONS,
        prev_date=prev_date if prev_date >= bounds[0] else None,
        next_date=next_date if next_date <= bounds[1] else None,
        season_min=bounds[0],
        season_max=bounds[1],
        present_date=present_date,
    )
