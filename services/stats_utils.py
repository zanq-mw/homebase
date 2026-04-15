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
        "group": "hitting" | "pitching",
        "yearByYear": [...splits],
        "projected":  [...splits],
        "career":     [...splits],
      }
    Hitting splits are enriched with SO% and BB%.
    """
    grouped = {}
    primary_group = "hitting"

    for stat_obj in raw_stats:
        type_name = stat_obj.get("type", {}).get("displayName", "")
        group_name = stat_obj.get("group", {}).get("displayName", "hitting")
        splits = stat_obj.get("splits", [])

        # Determine player's primary group (hitting vs pitching)
        if splits:
            primary_group = group_name

        # Enrich hitting splits with SO%/BB%
        if group_name == "hitting":
            for split in splits:
                enrich_hitting_split(split.get("stat", {}))

        # Collect by type — prefer hitting over pitching if both exist
        if type_name in ("yearByYear", "projected", "career"):
            if type_name not in grouped or group_name == "hitting":
                grouped[type_name] = splits

    return {
        "group": primary_group,
        "yearByYear": grouped.get("yearByYear", []),
        "projected": grouped.get("projected", []),
        "career": grouped.get("career", []),
    }


def last_n_games(splits, n=7):
    """
    Returns the last n regular season games from a game log splits list.
    Filters to gameType == "R", enriches hitting stats with SO%/BB%.
    """
    regular = [s for s in splits if s.get("gameType") == "R"]
    recent = regular[:n]
    for split in recent:
        enrich_hitting_split(split.get("stat", {}))
    return recent


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
                player[f"{group_name}_stats"] = flat
    return roster
