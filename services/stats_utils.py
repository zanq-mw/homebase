def enrich_hitting_split(stat):
    """
    Adds strikeOutPct (SO%) and walkPct (BB%) to a hitting stat dict in-place.
    Both are None when plateAppearances is 0 or missing.
    """
    pa = stat.get("plateAppearances") or 0
    if pa > 0:
        stat["strikeOutPct"] = round(stat.get("strikeOuts", 0) / pa, 3)
        stat["walkPct"] = round(stat.get("baseOnBalls", 0) / pa, 3)
    else:
        stat["strikeOutPct"] = None
        stat["walkPct"] = None
    return stat


def process_player_stats(raw_stats):
    """
    Groups the raw stats array from the StatsAPI people endpoint by stat type.
    Returns:
      {
        "group": "hitting" | "pitching" | "two-way",
        "hitting": {"yearByYear", "projected", "career"} or None,
        "pitching": {"yearByYear", "projected", "career"} or None,
        # Legacy keys (primary group) kept for backwards compat:
        "yearByYear", "projected", "career"
      }
    """
    hitting = {}
    pitching = {}

    for stat_obj in raw_stats:
        type_name = stat_obj.get("type", {}).get("displayName", "")
        group_name = stat_obj.get("group", {}).get("displayName", "")
        splits = stat_obj.get("splits", [])

        if type_name not in ("yearByYear", "projected", "career"):
            continue

        if group_name == "hitting":
            for split in splits:
                enrich_hitting_split(split.get("stat", {}))
            hitting[type_name] = splits
        elif group_name == "pitching":
            for split in splits:
                enrich_pitching_split(split.get("stat", {}))
            pitching[type_name] = splits

    # Require at least one season with 150+ PA to count as a genuine hitter.
    # Pitchers who batted (pre-DH era) never exceed ~70 PA in a season.
    hitting_seasons = hitting.get("yearByYear", [])
    has_hitting = any(
        s.get("stat", {}).get("plateAppearances") or 0 >= 150
        for s in hitting_seasons
    )
    has_pitching = bool(pitching.get("yearByYear") or pitching.get("career"))

    if has_hitting and has_pitching:
        group = "two-way"
    elif has_pitching:
        group = "pitching"
    else:
        group = "hitting"

    hitting_out = {
        "yearByYear": _annotate_multi_team(hitting.get("yearByYear", [])),
        "projected":  hitting.get("projected", []),
        "career":     hitting.get("career", []),
    } if has_hitting else None

    pitching_out = {
        "yearByYear": _annotate_multi_team(pitching.get("yearByYear", [])),
        "projected":  pitching.get("projected", []),
        "career":     pitching.get("career", []),
    } if has_pitching else None

    # Legacy flat keys point to the primary group
    primary = hitting_out if has_hitting else pitching_out
    return {
        "group":    group,
        "hitting":  hitting_out,
        "pitching": pitching_out,
        "yearByYear": primary["yearByYear"] if primary else [],
        "projected":  primary["projected"]  if primary else [],
        "career":     primary["career"]     if primary else [],
    }


def _annotate_multi_team(splits):
    """
    For seasons where a player appeared on multiple teams, inserts (or annotates)
    a combined row with num_teams set so the template can display '→ N Teams'.

    Combined rows are placed FIRST within each season group so that after the
    template's `| reverse`, they appear LAST (after the individual team rows).
    """
    from collections import defaultdict, OrderedDict

    # Group splits by season preserving order
    by_season = OrderedDict()
    for s in splits:
        season = s.get("season", "")
        by_season.setdefault(season, []).append(s)

    result = []
    for season, group in by_season.items():
        team_rows = [s for s in group if s.get("team")]
        no_team_rows = [s for s in group if not s.get("team")]
        n = len(team_rows)

        if n > 1:
            # Build combined row: use API's no-team row if present, else synthesize
            if no_team_rows:
                combined = dict(no_team_rows[0])
            else:
                combined = {"season": season, "stat": _aggregate_splits(team_rows)}
            combined["num_teams"] = n
            # Put combined FIRST so it ends up LAST after template's `| reverse`
            result.append(combined)
            result.extend(team_rows)
        else:
            result.extend(team_rows)
            result.extend(no_team_rows)

    return result


def _aggregate_splits(splits):
    """Sum counting stats across splits; leave rate stats as None."""
    agg = {}
    count_keys = [
        "gamesPlayed", "gamesStarted", "plateAppearances", "atBats",
        "hits", "runs", "doubles", "triples", "homeRuns", "rbi",
        "strikeOuts", "baseOnBalls", "stolenBases", "caughtStealing",
        "battersFaced", "earnedRuns", "outs",
    ]
    for key in count_keys:
        vals = [s.get("stat", {}).get(key) for s in splits if s.get("stat", {}).get(key) is not None]
        agg[key] = sum(vals) if vals else None

    # Recompute SO%/BB% from aggregated counts
    pa = agg.get("plateAppearances") or 0
    bf = agg.get("battersFaced") or 0
    if pa > 0:
        agg["strikeOutPct"] = round((agg.get("strikeOuts") or 0) / pa, 3)
        agg["walkPct"] = round((agg.get("baseOnBalls") or 0) / pa, 3)
    elif bf > 0:
        agg["strikeOutPct"] = round((agg.get("strikeOuts") or 0) / bf, 3)
        agg["walkPct"] = round((agg.get("baseOnBalls") or 0) / bf, 3)

    return agg


def last_n_games(game_log, n=7):
    """
    Accepts the dict {"hitting": [...], "pitching": [...]} from get_player_game_log.
    Merges both groups, filters to regular season, sorts by date descending,
    deduplicates by game_pk (two-way players appear in both groups per game),
    enriches stats, and returns the last n games.
    Each split has a "statGroup" key ("hitting" or "pitching").
    """
    hitting = game_log.get("hitting", []) if isinstance(game_log, dict) else game_log
    pitching = game_log.get("pitching", []) if isinstance(game_log, dict) else []

    all_splits = [s for s in hitting + pitching if s.get("gameType") == "R"]
    all_splits.sort(key=lambda s: s.get("date", ""), reverse=True)

    seen_pks = set()
    recent = []
    for s in all_splits:
        pk = s.get("game", {}).get("gamePk")
        if pk and pk in seen_pks:
            continue
        if pk:
            seen_pks.add(pk)
        group = s.get("statGroup", "hitting")
        if group == "hitting":
            enrich_hitting_split(s.get("stat", {}))
        else:
            enrich_pitching_split(s.get("stat", {}))
        recent.append(s)
        if len(recent) >= n:
            break

    return recent


def enrich_pitching_split(stat):
    """
    Adds strikeOutPct (K%) and walkPct (BB%) to a pitching stat dict in-place.
    Both based on battersFaced.
    """
    bf = stat.get("battersFaced") or 0
    if bf > 0:
        stat["strikeOutPct"] = round(stat.get("strikeOuts", 0) / bf, 3)
        stat["walkPct"] = round(stat.get("baseOnBalls", 0) / bf, 3)
    else:
        stat["strikeOutPct"] = None
        stat["walkPct"] = None
    return stat


def attach_season_stats_to_roster(roster):
    """
    Flattens nested person.stats onto each roster entry as
    hitting_stats and pitching_stats dicts.
    """
    for player in roster:
        person = player.get("person", {})
        for stat_group in person.get("stats", []):
            group_name = stat_group.get("group", {}).get("displayName", "")
            splits = stat_group.get("splits", [])
            if splits:
                flat = splits[0].get("stat", {})
                if group_name == "hitting":
                    enrich_hitting_split(flat)
                elif group_name == "pitching":
                    enrich_pitching_split(flat)
                player[f"{group_name}_stats"] = flat
    return roster
