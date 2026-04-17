# HomeBase

A Flask-based MLB stats web app that pulls live data from the [MLB StatsAPI](https://statsapi.mlb.com). No database — all data is fetched from the API and cached in-memory.

**Live:** [https://homebase-gx8y.onrender.com](https://homebase-gx8y.onrender.com)

## Features

- Live scorecards and today's games
- AL/NL standings
- MLB-wide stat leaderboards (hitting & pitching)
- Team pages with rosters and stats
- Player pages with career stats, projections, and last 7 games
- Full schedule with season/date filtering
- Individual game detail (linescore, boxscore)
- Player/team search

## Running Locally

```bash
# Clone the repo
git clone https://github.com/zanqureshi/homebase.git
cd homebase

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the app
python app.py
```

The app runs at [http://localhost:5000](http://localhost:5000) in debug mode.

> Cache is in-memory (SimpleCache). Restart the server to clear it.

## Tech Stack

- **Backend:** Python / Flask
- **Data:** MLB StatsAPI (`statsapi.mlb.com`)
- **Frontend:** Bootstrap 5.3, custom CSS
- **Caching:** Flask-Caching (SimpleCache)
- **Deployment:** Render
