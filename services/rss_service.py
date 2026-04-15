import requests
import xml.etree.ElementTree as ET

MLB_RSS_BASE = "https://www.mlb.com"

# Stable mapping of StatsAPI team ID -> MLB.com URL slug for RSS feeds.
# Slugs are irregular (e.g. "redsox", not "red-sox") and can't be derived
# programmatically from any StatsAPI field.
TEAM_RSS_SLUG = {
    108: "angels",
    109: "dbacks",
    110: "orioles",
    111: "redsox",
    112: "cubs",
    113: "reds",
    114: "guardians",
    115: "rockies",
    116: "tigers",
    117: "astros",
    118: "royals",
    119: "dodgers",
    120: "nationals",
    121: "mets",
    133: "athletics",
    134: "pirates",
    135: "padres",
    137: "giants",
    138: "cardinals",
    139: "rays",
    140: "rangers",
    141: "bluejays",
    142: "twins",
    143: "phillies",
    144: "braves",
    145: "whitesox",
    146: "marlins",
    147: "yankees",
    158: "brewers",
}


def _parse_feed(url, limit):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []

        # Register namespaces to avoid stripping them
        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
        }

        articles = []
        for item in channel.findall("item")[:limit]:
            # <image href="..."/> is a bare tag with no namespace
            image_el = item.find("image")
            image = image_el.get("href") if image_el is not None else None

            # Upgrade MLB image URL to a larger size (default is uncropped)
            if image and "/upload/" in image:
                image = image.replace("t_16x9/t_w1024/", "t_16x9/t_w640/")

            # Try dc:creator first, then standard <author>, then default
            author = (item.findtext("dc:creator", namespaces=ns) or "").strip()
            if not author:
                raw_author = (item.findtext("author") or "").strip()
                # Standard RSS <author> is "email (Name)" — extract just the name
                if "(" in raw_author and raw_author.endswith(")"):
                    author = raw_author[raw_author.index("(") + 1:-1].strip()
                elif raw_author and "@" not in raw_author:
                    author = raw_author
            if not author:
                author = "MLB.com"

            articles.append({
                "title": (item.findtext("title") or "").strip(),
                "link": item.findtext("link") or "",
                "author": author,
                "pub_date": item.findtext("pubDate") or "",
                "image": image,
            })
        return articles
    except Exception:
        return []


def get_mlb_news(limit=6):
    """Returns recent MLB-wide news articles from the RSS feed."""
    url = f"{MLB_RSS_BASE}/feeds/news/rss.xml"
    return _parse_feed(url, limit)


def get_team_news(team_id, limit=10):
    """Returns recent news articles for a specific team by StatsAPI team ID."""
    slug = TEAM_RSS_SLUG.get(team_id)
    if not slug:
        return []
    url = f"{MLB_RSS_BASE}/{slug}/feeds/news/rss.xml"
    return _parse_feed(url, limit)
