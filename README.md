# HomeBase

A Flask-based MLB stats web app that pulls live data from the [MLB StatsAPI](https://statsapi.mlb.com). Live data is fetched from the API and cached in-memory. Comments are stored in a local SQLite database (`homebase.db`).

**Live:** [https://homebase-gx8y.onrender.com](https://homebase-gx8y.onrender.com)

> Hosted on Render's free tier — the instance spins down after 15 minutes of inactivity. Initial load may take a few seconds while it wakes up.

## Features

- Live scorecards and today's games
- AL/NL standings
- MLB-wide stat leaderboards (hitting & pitching)
- Team pages with rosters and stats
- Player pages with career stats, projections, and last 7 games
- Full schedule with season/date filtering
- Individual game detail (linescore, boxscore)
- Player/team search
- Anonymous comments on player, team, and game pages (shared across all visitors)

## Running Locally

```bash
git clone https://github.com/zanqureshi/homebase.git
cd homebase
pip install -r requirements.txt
python3 app.py
```

The app runs at [http://localhost:5000](http://localhost:5000) in debug mode.

> Cache is in-memory (SimpleCache). Restart the server to clear it.

## Tech Stack

- **Backend:** Python / Flask
- **Data:** MLB StatsAPI (`statsapi.mlb.com`)
- **Frontend:** Bootstrap 5.3, custom CSS
- **Caching:** Flask-Caching (SimpleCache)
- **Comments:** SQLite (`homebase.db`), anonymous, rate-limited
- **Deployment:** Render
