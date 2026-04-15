from flask import Blueprint, request, jsonify
from services import mlb_api

search_bp = Blueprint("search", __name__)


def _build_team_lookup():
    """Returns dict of team_id -> {division_name, rank, wins, losses}."""
    lookup = {}
    for division in mlb_api.get_standings():
        div_name = division["division"]["name"]
        for i, tr in enumerate(division["teamRecords"], start=1):
            team_id = tr["team"]["id"]
            lookup[team_id] = {
                "division": div_name,
                "rank": i,
                "wins": tr["wins"],
                "losses": tr["losses"],
            }
    return lookup


@search_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"results": []})

    team_lookup = _build_team_lookup()
    results = []

    # Match teams by name
    q_lower = query.lower()
    for division in mlb_api.get_standings():
        for tr in division["teamRecords"]:
            team = tr["team"]
            if q_lower in team.get("name", "").lower():
                info = team_lookup.get(team["id"], {})
                ordinal = lambda n: f"{n}{'th' if 11<=n<=13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"
                results.append({
                    "type": "team",
                    "id": team["id"],
                    "name": team["name"],
                    "url": f"/teams/{team['id']}",
                    "image": f"https://www.mlbstatic.com/team-logos/{team['id']}.svg",
                    "subtitle": f"{info.get('division','')}\u00a0\u00b7\u00a0{ordinal(info.get('rank',0))}\u00a0\u00b7\u00a0{info.get('wins',0)}-{info.get('losses',0)}",
                })

    # Search players via StatsAPI
    players = mlb_api.search_players(query)
    for p in players[:8]:
        team = p.get("currentTeam", {})
        number = p.get("primaryNumber", "")
        position = p.get("primaryPosition", {}).get("abbreviation", "")
        team_name = team.get("name", "")
        subtitle_parts = []
        if team_name:
            subtitle_parts.append(team_name)
        if number:
            subtitle_parts.append(f"#{number}")
        if position:
            subtitle_parts.append(position)
        results.append({
            "type": "player",
            "id": p["id"],
            "name": p.get("fullName", ""),
            "url": f"/players/{p['id']}",
            "image": f"https://content.mlb.com/images/headshots/current/60x60/{p['id']}@2x.png",
            "subtitle": "\u00a0\u00b7\u00a0".join(subtitle_parts),
        })

    return jsonify({"results": results})
