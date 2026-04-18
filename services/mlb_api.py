import datetime
import requests
from flask import current_app
from services import stats_utils
from services.cache import cache

DIVISION_NAMES = {
    200: "American League",
    201: "AL East",
    202: "AL Central",
    203: "AL West",
    204: "NL East",
    205: "NL Central",
    206: "NL West",
}


def _get(path, params=None):
    base = current_app.config["MLB_API_BASE"]
    try:
        resp = requests.get(f"{base}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}


@cache.cached(timeout=1800, key_prefix="get_standings")
def get_standings():
    """
    Returns a list of division dicts. Each division has:
      - division (id/name)
      - teamRecords: list of team record dicts, each with:
          wins, losses, winningPercentage, gamesBack, streak,
          team (id, name), splits: {home, away, oneRun, extraInning}
    """
    data = _get("/api/v1/standings", params={"leagueId": "103,104", "hydrate": "team"})
    records = data.get("records", [])

    divisions = []
    for record in records:
        teams = []
        for tr in record.get("teamRecords", []):
            splits = {}
            for sr in tr.get("records", {}).get("splitRecords", []):
                splits[sr["type"]] = {
                    "wins": sr.get("wins", 0),
                    "losses": sr.get("losses", 0),
                    "pct": sr.get("pct", ".000"),
                }
            runs_scored = tr.get("runsScored") or 0
            runs_allowed = tr.get("runsAllowed") or 0
            teams.append({
                "team": tr.get("team", {}),
                "wins": tr.get("wins", 0),
                "losses": tr.get("losses", 0),
                "winningPercentage": tr.get("winningPercentage", ".000"),
                "gamesBack": tr.get("gamesBack", "-"),
                "streak": tr.get("streak", {}).get("streakCode", ""),
                "run_diff": runs_scored - runs_allowed,
                "splits": splits,
            })
        # Division name comes from the hydrated team data
        div = record.get("division", {})
        team_records = record.get("teamRecords", [])
        if team_records:
            div_name = team_records[0].get("team", {}).get("division", {}).get("name", "")
        else:
            div_id = div.get("id")
            div_name = DIVISION_NAMES.get(div_id, f"Division {div_id}")
        divisions.append({
            "division": {**div, "name": div_name},
            "teamRecords": teams,
        })
    return divisions


@cache.cached(timeout=86400, key_prefix="get_all_teams")
def get_all_teams():
    """Returns list of all MLB team dicts."""
    data = _get("/api/v1/teams", params={"sportId": "1"})
    return data.get("teams", [])


@cache.memoize(timeout=86400)
def get_team(team_id):
    """Returns a single team dict or None if not found."""
    data = _get(f"/api/v1/teams/{team_id}")
    teams = data.get("teams", [])
    return teams[0] if teams else None


@cache.memoize(timeout=3600)
def get_roster_with_stats(team_id):
    """
    Returns roster list with season stats flattened onto each player.
    Each entry has: person (bio fields), jerseyNumber, position,
    hitting_stats (dict), pitching_stats (dict).
    """
    data = _get(
        f"/api/v1/teams/{team_id}/roster/Active",
        params={"hydrate": "person(stats(type=season))"},
    )
    roster = data.get("roster", [])
    return stats_utils.attach_season_stats_to_roster(roster)


@cache.memoize(timeout=86400)
def get_player_bio(player_id):
    """Returns bio dict for a player or None if not found."""
    data = _get(f"/api/v1/people/{player_id}", params={"hydrate": "currentTeam"})
    people = data.get("people", [])
    return people[0] if people else None


@cache.memoize(timeout=3600)
def get_player_stats(player_id):
    """
    Returns a dict grouped by stat type:
      {
        "group": "hitting" | "pitching",
        "yearByYear": [...splits],
        "projected":  [...splits],
        "career":     [...splits],
      }
    Hitting splits are enriched with SO%/BB%.
    """
    data = _get(
        f"/api/v1/people/{player_id}",
        params={
            "hydrate": "stats(type=[yearByYear,projected,career],group=[hitting,pitching]),currentTeam"
        },
    )
    people = data.get("people", [])
    if not people:
        return {}
    raw_stats = people[0].get("stats", [])
    return stats_utils.process_player_stats(raw_stats)


@cache.memoize(timeout=3600)
def get_player_game_log(player_id):
    """
    Returns {"hitting": [...splits], "pitching": [...splits]}.
    Either list may be empty. Splits are tagged with a "statGroup" key.
    """
    data = _get(
        f"/api/v1/people/{player_id}",
        params={"hydrate": "stats(type=[gameLog],group=[hitting,pitching])"},
    )
    people = data.get("people", [])
    result = {"hitting": [], "pitching": []}
    if not people:
        return result
    for stat_group in people[0].get("stats", []):
        if stat_group.get("type", {}).get("displayName") != "gameLog":
            continue
        group_name = stat_group.get("group", {}).get("displayName", "")
        if group_name in result:
            for s in stat_group.get("splits", []):
                s["statGroup"] = group_name
            result[group_name] = stat_group.get("splits", [])
    return result


def get_todays_games():
    """
    Returns all MLB games for today as a list of dicts, each with:
    away {id, name, abbreviation, score}, home {id, name, abbreviation, score},
    status (abstractGameState), detailed_state, game_time (ISO UTC string).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    data = _get("/api/v1/schedule", params={"sportId": 1, "date": today, "hydrate": "team,linescore"})
    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            away_data = game["teams"]["away"]
            home_data = game["teams"]["home"]
            detailed = game["status"].get("detailedState", "")
            abstract = game["status"]["abstractGameState"]
            # Only treat as live when actually in progress, not during warmup/pre-game
            _pre_game = {"Warmup", "Pre-Game", "Delayed Start", "Preview"}
            if abstract in ("Final", "Game Over"):
                state = "Final"
            elif abstract == "Live" and detailed not in _pre_game:
                state = "Live"
            else:
                state = "Preview"
            ls = game.get("linescore", {})

            # Batting team: top inning = away batting, bottom inning = home batting
            is_top = ls.get("isTopInning", True)
            batting_abbr = away_data["team"].get("abbreviation", "") if is_top else home_data["team"].get("abbreviation", "")
            pitching_abbr = home_data["team"].get("abbreviation", "") if is_top else away_data["team"].get("abbreviation", "")

            games.append({
                "gamePk": game.get("gamePk"),
                "away": {
                    "id": away_data["team"]["id"],
                    "name": away_data["team"]["name"],
                    "abbreviation": away_data["team"].get("abbreviation", ""),
                    "score": away_data.get("score"),
                },
                "home": {
                    "id": home_data["team"]["id"],
                    "name": home_data["team"]["name"],
                    "abbreviation": home_data["team"].get("abbreviation", ""),
                    "score": home_data.get("score"),
                },
                "status": state,
                "detailed_state": game["status"].get("detailedState", ""),
                "game_time": game.get("gameDate"),
                "inning": ls.get("currentInning"),
                "inning_ordinal": ls.get("currentInningOrdinal"),
                "inning_half": ls.get("inningHalf"),
                "inning_state": ls.get("inningState"),
                "outs": ls.get("outs"),
                "batting_team": batting_abbr,
                "pitching_team": pitching_abbr,
            })
    games.sort(key=lambda g: g.get("game_time") or "")
    return games


def get_team_schedule(team_id, season=None):
    """
    Returns all regular season games as a flat sorted list plus a present_index
    pointing to the first non-Final game (or last game if season is over).
    Each game dict has: date, opponent {id, name}, is_home, score_us, score_them,
    is_win, status, venue.
    """
    if season is None:
        season = datetime.date.today().year
    data = _get(
        "/api/v1/schedule",
        params={"teamId": team_id, "sportId": 1, "season": season, "gameType": "R", "hydrate": "linescore"},
    )

    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            is_home = home["team"]["id"] == team_id
            us = home if is_home else away
            them = away if is_home else home
            detailed = game["status"].get("detailedState", "")
            abstract = game["status"]["abstractGameState"]
            _pre_game = {"Warmup", "Pre-Game", "Delayed Start", "Preview"}
            if abstract in ("Final", "Game Over"):
                state = "Final"
            elif abstract == "Live" and detailed not in _pre_game:
                state = "Live"
            else:
                state = "Preview"
            ls = game.get("linescore", {})

            entry = {
                "gamePk": game.get("gamePk"),
                "date": game.get("officialDate"),
                "opponent": them["team"],
                "is_home": is_home,
                "status": state,
                "venue": game.get("venue", {}).get("name", ""),
                "score_us": None,
                "score_them": None,
                "is_win": None,
                "inning": ls.get("currentInning"),
                "inning_ordinal": ls.get("currentInningOrdinal"),
                "inning_half": ls.get("inningHalf"),
                "outs": ls.get("outs"),
            }

            if state == "Final":
                entry["score_us"] = us.get("score")
                entry["score_them"] = them.get("score")
                entry["is_win"] = us.get("isWinner", False)
            elif state == "Live":
                entry["score_us"] = us.get("score")
                entry["score_them"] = them.get("score")

            games.append(entry)

    # present_index: first non-Final game, or last game if all done
    present_index = len(games) - 1
    for i, g in enumerate(games):
        if g["status"] != "Final":
            present_index = i
            break

    return {"games": games, "present_index": present_index}


@cache.memoize(timeout=3600)
def search_players(query):
    """
    Returns a list of active MLB players matching the query.
    Each entry has: id, fullName, primaryNumber, primaryPosition, currentTeam.
    """
    data = _get(
        "/api/v1/people/search",
        params={"names": query, "sportIds": 1, "hydrate": "currentTeam"},
    )
    return [p for p in data.get("people", []) if p.get("active")]


@cache.memoize(timeout=1800)
def get_stat_leaders(categories, limit=10):
    """
    Returns dict keyed by leaderCategory ->
      list of {rank, value, person: {id, fullName}, team: {id, name}}
    """
    data = _get(
        "/api/v1/stats/leaders",
        params={
            "leaderCategories": ",".join(categories),
            "limit": limit,
            "sportId": 1,
        },
    )
    result = {}
    for leader_group in data.get("leagueLeaders", []):
        category = leader_group.get("leaderCategory")
        leaders = []
        for entry in leader_group.get("leaders", []):
            person = entry.get("person", {})
            team   = entry.get("team", {})
            leaders.append({
                "rank":     entry.get("rank"),
                "value":    entry.get("value"),
                "person":   person,
                "team":     team,
                "position": person.get("primaryPosition", {}).get("abbreviation", ""),
                "team_abbr": team.get("abbreviation", team.get("name", "")),
            })
        result[category] = leaders
    return result


@cache.memoize(timeout=1800)
def get_team_leaders(team_id, categories, limit=1):
    """
    Returns dict keyed by leaderCategory ->
      list of {rank, value, person: {id, fullName}, position, jerseyNumber}
    Uses the team leaders endpoint: /api/v1/teams/{teamId}/leaders
    """
    import datetime
    season = datetime.date.today().year
    data = _get(
        f"/api/v1/teams/{team_id}/leaders",
        params={
            "leaderCategories": ",".join(categories),
            "limit": limit,
            "season": season,
            "sportId": 1,
        },
    )
    result = {}
    for leader_group in data.get("teamLeaders", []):
        category = leader_group.get("leaderCategory")
        leaders = []
        for entry in leader_group.get("leaders", []):
            person = entry.get("person", {})
            leaders.append({
                "rank":          entry.get("rank"),
                "value":         entry.get("value"),
                "person":        person,
                "position":      person.get("primaryPosition", {}).get("abbreviation", ""),
                "jerseyNumber":  entry.get("jerseyNumber", ""),
            })
        result[category] = leaders
    return result


@cache.memoize(timeout=1800)
def get_team_season_stats(team_id, season):
    """
    Returns team season batting and pitching aggregates for use in game previews.
    """
    data = _get(
        f"/api/v1/teams/{team_id}/stats",
        params={"stats": "season", "group": "hitting,pitching", "season": season, "sportId": 1},
    )
    result = {"batting": {}, "pitching": {}}
    for group in data.get("stats", []):
        grp_name = group.get("group", {}).get("displayName", "")
        splits = group.get("splits", [])
        if not splits:
            continue
        stat = splits[0].get("stat", {})
        if grp_name == "hitting":
            result["batting"] = {
                "AVG": stat.get("avg", ""),
                "OBP": stat.get("obp", ""),
                "SLG": stat.get("slg", ""),
                "OPS": stat.get("ops", ""),
                "R":   stat.get("runs", ""),
                "H":   stat.get("hits", ""),
                "HR":  stat.get("homeRuns", ""),
                "RBI": stat.get("rbi", ""),
                "BB":  stat.get("baseOnBalls", ""),
                "SO":  stat.get("strikeOuts", ""),
            }
        elif grp_name == "pitching":
            result["pitching"] = {
                "ERA":  stat.get("era", ""),
                "WHIP": stat.get("whip", ""),
                "H":    stat.get("hits", ""),
                "R":    stat.get("runs", ""),
                "ER":   stat.get("earnedRuns", ""),
                "BB":   stat.get("baseOnBalls", ""),
                "SO":   stat.get("strikeOuts", ""),
                "HR":   stat.get("homeRuns", ""),
            }
    return result


@cache.memoize(timeout=86400)
def get_game_meta(game_pk):
    """
    Returns basic game metadata (venue_id, venue_name, away/home team) from
    the schedule endpoint. Lightweight — used to get venue ID for stadium images.
    """
    data = _get("/api/v1/schedule", params={"gamePk": game_pk, "hydrate": "team,venue"})
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            venue = game.get("venue", {})
            away = game["teams"]["away"]["team"]
            home = game["teams"]["home"]["team"]
            return {
                "venue_id": venue.get("id"),
                "venue_name": venue.get("name", ""),
                "away": {"id": away["id"], "name": away["name"],
                         "abbreviation": away.get("abbreviation", "")},
                "home": {"id": home["id"], "name": home["name"],
                         "abbreviation": home.get("abbreviation", "")},
                "game_date": game.get("officialDate", ""),
                "game_time": game.get("gameDate"),
            }
    return {}


@cache.cached(timeout=86400, key_prefix="get_available_seasons")
def get_available_seasons(sport_id=1):
    """
    Returns a descending list of season years >= 2000 from the MLB StatsAPI.
    Falls back to [current_year, current_year-1, current_year-2] on API failure.
    """
    current_year = datetime.date.today().year
    fallback = [current_year, current_year - 1, current_year - 2]
    data = _get("/api/v1/seasons/all", params={"sportId": sport_id})
    seasons_raw = data.get("seasons", [])
    if not seasons_raw:
        return fallback
    years = sorted(
        {int(s["seasonId"]) for s in seasons_raw if int(s.get("seasonId", 0)) >= 2015},
        reverse=True,
    )
    return years if years else fallback


@cache.memoize(timeout=86400)
def get_season_dates(year):
    """
    Returns (regularSeasonStartDate, postSeasonEndDate) for the given year.
    Upper bound is postSeasonEndDate so playoff games are reachable.
    Falls back to ('{year}-03-28', '{year}-11-01') on API failure.
    """
    data = _get(f"/api/v1/seasons/{year}", params={"sportId": 1})
    seasons = data.get("seasons", [])
    if seasons:
        s = seasons[0]
        start = s.get("regularSeasonStartDate", f"{year}-03-28")
        end   = s.get("postSeasonEndDate") or s.get("seasonEndDate") or f"{year}-11-01"
        return start, end
    return f"{year}-03-28", f"{year}-09-28"


def get_full_schedule(season=None, date=None):
    """
    Returns league-wide schedule grouped by date.
    If date (YYYY-MM-DD) is given, returns only that day.
    Otherwise returns full regular season for the given season year.

    Returns:
      {
        "date_groups": [{"date": "2026-04-12", "games": [...]}, ...],
        "present_date": "2026-04-12",  # today if it has games, else nearest future date
      }
    Each game dict: gamePk, away, home, status, detailed_state, game_time,
                    venue_id, venue_name, inning, inning_half, inning_ordinal, outs
    """
    if season is None:
        season = datetime.date.today().year
    from datetime import date as date_cls
    _pre_game = {"Warmup", "Pre-Game", "Delayed Start", "Preview"}

    # Use playoff game types for October+ dates, regular season otherwise
    if date and date[5:7] >= "10":
        game_types = "R,W,D,L,F"
    else:
        game_types = "R"
    params = {"sportId": 1, "hydrate": "team,linescore", "gameType": game_types, "season": season}
    if date:
        params["date"] = date

    data = _get("/api/v1/schedule", params=params)

    date_groups = []
    today = date_cls.today().isoformat()
    present_date = None

    for date_entry in data.get("dates", []):
        game_date = date_entry.get("date", "")
        games = []
        for game in date_entry.get("games", []):
            away_data = game["teams"]["away"]
            home_data = game["teams"]["home"]
            detailed = game["status"].get("detailedState", "")
            abstract = game["status"]["abstractGameState"]
            if abstract in ("Final", "Game Over"):
                state = "Final"
            elif abstract == "Live" and detailed not in _pre_game:
                state = "Live"
            else:
                state = "Preview"
            ls = game.get("linescore", {})
            venue = game.get("venue", {})
            games.append({
                "gamePk": game.get("gamePk"),
                "away": {
                    "id": away_data["team"]["id"],
                    "name": away_data["team"]["name"],
                    "abbreviation": away_data["team"].get("abbreviation", ""),
                    "score": away_data.get("score"),
                },
                "home": {
                    "id": home_data["team"]["id"],
                    "name": home_data["team"]["name"],
                    "abbreviation": home_data["team"].get("abbreviation", ""),
                    "score": home_data.get("score"),
                },
                "status": state,
                "detailed_state": detailed,
                "game_time": game.get("gameDate"),
                "venue_id": venue.get("id"),
                "venue_name": venue.get("name", ""),
                "inning": ls.get("currentInning"),
                "inning_half": ls.get("inningHalf"),
                "inning_ordinal": ls.get("currentInningOrdinal"),
                "outs": ls.get("outs"),
            })
        if games:
            date_groups.append({"date": game_date, "games": games})

    # present_date: today if it has games, else nearest future date, else last date
    for dg in date_groups:
        if dg["date"] >= today:
            present_date = dg["date"]
            break
    if present_date is None and date_groups:
        present_date = date_groups[-1]["date"]

    return {"date_groups": date_groups, "present_date": present_date or today}


def get_game_linescore(game_pk):
    """
    Returns structured linescore for a game.
    Includes inning-by-inning breakdown, R/H/E totals, game status,
    and both team identities.
    """
    data = _get(f"/api/v1/game/{game_pk}/linescore")
    if not data:
        return {}

    teams = data.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    innings_raw = data.get("innings", [])
    innings = []
    for inn in innings_raw:
        away_inn = inn.get("away", {})
        home_inn = inn.get("home", {})
        innings.append({
            "num": inn.get("num"),
            "ordinal": inn.get("ordinalNum", ""),
            "away_runs": away_inn.get("runs"),
            "away_hits": away_inn.get("hits"),
            "away_errors": away_inn.get("errors"),
            "home_runs": home_inn.get("runs"),
            "home_hits": home_inn.get("hits"),
            "home_errors": home_inn.get("errors"),
        })

    # Get authoritative status from schedule endpoint (linescore inningState
    # can be stale — e.g. stuck on "Top" after a walk-off in the top of the 9th)
    sched = _get("/api/v1/schedule", params={"gamePk": game_pk})
    abstract = ""
    detailed = ""
    for _d in sched.get("dates", []):
        for _g in _d.get("games", []):
            abstract = _g.get("status", {}).get("abstractGameState", "")
            detailed = _g.get("status", {}).get("detailedState", "")

    _pre_game = {"Warmup", "Pre-Game", "Delayed Start", "Preview"}
    inning_state = data.get("inningState", "")
    current_inning = data.get("currentInning")
    if abstract in ("Final", "Game Over"):
        status = "Final"
    elif abstract == "Live" and detailed not in _pre_game:
        status = "Live"
    elif current_inning and inning_state not in ("", "End", "Final") and detailed not in _pre_game:
        status = "Live"
    elif inning_state in ("Final", "Game Over") or (not current_inning and innings):
        status = "Final"
    else:
        status = "Preview"

    return {
        "innings": innings,
        "away_totals": {
            "runs": away.get("runs", 0),
            "hits": away.get("hits", 0),
            "errors": away.get("errors", 0),
        },
        "home_totals": {
            "runs": home.get("runs", 0),
            "hits": home.get("hits", 0),
            "errors": home.get("errors", 0),
        },
        "current_inning": current_inning,
        "inning_ordinal": data.get("currentInningOrdinal", ""),
        "inning_state": inning_state,
        "inning_half": data.get("inningHalf", ""),
        "outs": data.get("outs", 0),
        "balls": data.get("balls", 0),
        "strikes": data.get("strikes", 0),
        "away_team": data.get("defense", {}).get("team") or {},
        "home_team": data.get("offense", {}).get("team") or {},
        "status": status,
    }


def get_game_boxscore(game_pk):
    """
    Returns structured box score for a game with ordered batter/pitcher lists
    for both away and home teams, plus venue info.
    """
    data = _get(f"/api/v1/game/{game_pk}/boxscore")
    if not data:
        return {}

    teams_raw = data.get("teams", {})

    def parse_side(side_data):
        team = side_data.get("team", {})
        players = side_data.get("players", {})
        batter_ids = side_data.get("batters", [])
        pitcher_ids = side_data.get("pitchers", [])

        def get_player(pid):
            return players.get(f"ID{pid}", {})

        batters = []
        for pid in batter_ids:
            p = get_player(pid)
            if not p:
                continue
            person = p.get("person", {})
            stats = p.get("stats", {}).get("batting", {})
            season = p.get("seasonStats", {}).get("batting", {})
            pos = p.get("position", {}).get("abbreviation", "")
            # Skip players who never had a plate appearance
            pa = int(stats.get("plateAppearances") or 0)
            if pa == 0 and int(stats.get("atBats") or 0) == 0:
                continue
            batters.append({
                "id": person.get("id"),
                "name": person.get("fullName", ""),
                "pos": pos,
                "ab": stats.get("atBats", ""),
                "r": stats.get("runs", ""),
                "h": stats.get("hits", ""),
                "rbi": stats.get("rbi", ""),
                "bb": stats.get("baseOnBalls", ""),
                "so": stats.get("strikeOuts", ""),
                "avg": season.get("avg", ""),
            })

        pitchers = []
        for pid in pitcher_ids:
            p = get_player(pid)
            if not p:
                continue
            person = p.get("person", {})
            stats = p.get("stats", {}).get("pitching", {})
            season = p.get("seasonStats", {}).get("pitching", {})
            # Skip pitchers who threw no outs
            ip = stats.get("inningsPitched") or "0"
            if float(ip) == 0:
                continue
            pitchers.append({
                "id": person.get("id"),
                "name": person.get("fullName", ""),
                "ip": stats.get("inningsPitched", ""),
                "h": stats.get("hits", ""),
                "r": stats.get("runs", ""),
                "er": stats.get("earnedRuns", ""),
                "bb": stats.get("baseOnBalls", ""),
                "so": stats.get("strikeOuts", ""),
                "era": season.get("era", ""),
            })

        ts = side_data.get("teamStats", {})
        bat = ts.get("batting", {})
        pit = ts.get("pitching", {})
        team_stats = {
            "batting": {
                "R":   bat.get("runs", ""),
                "H":   bat.get("hits", ""),
                "2B":  bat.get("doubles", ""),
                "3B":  bat.get("triples", ""),
                "HR":  bat.get("homeRuns", ""),
                "RBI": bat.get("rbi", ""),
                "BB":  bat.get("baseOnBalls", ""),
                "SO":  bat.get("strikeOuts", ""),
                "LOB": bat.get("leftOnBase", ""),
                "AVG": bat.get("avg", ""),
                "OBP": bat.get("obp", ""),
                "SLG": bat.get("slg", ""),
                "OPS": bat.get("ops", ""),
            },
            "pitching": {
                "IP":  pit.get("inningsPitched", ""),
                "H":   pit.get("hits", ""),
                "R":   pit.get("runs", ""),
                "ER":  pit.get("earnedRuns", ""),
                "BB":  pit.get("baseOnBalls", ""),
                "SO":  pit.get("strikeOuts", ""),
                "HR":  pit.get("homeRuns", ""),
                "ERA": pit.get("era", ""),
            },
        }
        return {"team": team, "batters": batters, "pitchers": pitchers, "team_stats": team_stats}

    info = data.get("info", [])
    venue_name = ""
    for item in info:
        if item.get("label") == "Venue":
            venue_name = item.get("value", "")
            break

    # venue id comes from the game feed; boxscore doesn't include it directly
    # We embed it via the topLine info or fall back to empty
    return {
        "away": parse_side(teams_raw.get("away", {})),
        "home": parse_side(teams_raw.get("home", {})),
        "venue": {"name": venue_name},
    }
