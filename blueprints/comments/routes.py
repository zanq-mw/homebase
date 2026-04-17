import hashlib
import random
import re
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from .db import get_db

comments_bp = Blueprint("comments", __name__, url_prefix="/api/comments")

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

_URL_RE   = re.compile(r'https?://', re.IGNORECASE)
_SPAM_RE  = re.compile(
    r'(buy now|click here|free money|earn \$|casino|viagra|cialis'
    r'|make money fast|work from home)',
    re.IGNORECASE,
)

_VALID_PAGE_TYPES = {"game", "team", "player"}

# In-process rate-limit cache  {ip_hash: monotonic_timestamp}
_rate_cache: dict[str, float] = {}
_RATE_LIMIT_SECONDS = 5


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _check_rate_limit(ip_hash: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    if now - _rate_cache.get(ip_hash, 0) < _RATE_LIMIT_SECONDS:
        return False
    _rate_cache[ip_hash] = now
    return True


def _validate(body: str) -> tuple[bool, str]:
    if len(body) < 3:
        return False, "Comment is too short (minimum 3 characters)."
    if len(body) > 500:
        return False, "Comment is too long (maximum 500 characters)."
    if len(_URL_RE.findall(body)) > 2:
        return False, "Too many links in comment."
    if _SPAM_RE.search(body):
        return False, "Comment flagged as spam."
    return True, ""


def _anon_name() -> str:
    return f"Anonymous{random.randint(1000, 9999)}"


def _client_ip() -> str:
    return (
        request.headers.get("X-Forwarded-For", request.remote_addr or "")
        .split(",")[0]
        .strip()
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@comments_bp.route("", methods=["GET"])
def list_comments():
    page_type = request.args.get("page_type")
    page_id   = request.args.get("page_id", type=int)
    sort      = request.args.get("sort", "newest")

    if page_type not in _VALID_PAGE_TYPES or page_id is None:
        return jsonify({"error": "Invalid parameters"}), 400

    order = "created_at DESC" if sort != "top" else "likes DESC, created_at DESC"
    rows = get_db().execute(
        f"SELECT id, name, body, created_at, likes FROM comments "
        f"WHERE page_type=? AND page_id=? ORDER BY {order}",
        (page_type, page_id),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@comments_bp.route("", methods=["POST"])
def post_comment():
    data      = request.get_json(force=True, silent=True) or {}
    page_type = data.get("page_type")
    page_id   = data.get("page_id")
    name          = (data.get("name") or "").strip()
    body          = (data.get("body") or "").strip()
    session_token = (data.get("session_token") or "").strip()

    if page_type not in _VALID_PAGE_TYPES or not isinstance(page_id, int):
        return jsonify({"error": "Invalid parameters"}), 400

    ok, err = _validate(body)
    if not ok:
        return jsonify({"error": err}), 400

    if not name:
        name = _anon_name()

    ip_hash = _hash_ip(_client_ip() or "unknown")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db  = get_db()
    cur = db.execute(
        "INSERT INTO comments (page_type, page_id, name, body, ip_hash, created_at, likes, session_token) "
        "VALUES (?,?,?,?,?,?,0,?)",
        (page_type, page_id, name, body, ip_hash, now, session_token or None),
    )
    db.commit()
    return jsonify({
        "id":         cur.lastrowid,
        "name":       name,
        "body":       body,
        "created_at": now,
        "likes":      0,
    }), 201


@comments_bp.route("/<int:comment_id>/like", methods=["POST"])
def like_comment(comment_id):
    db = get_db()
    db.execute("UPDATE comments SET likes = likes + 1 WHERE id = ?", (comment_id,))
    db.commit()
    row = db.execute("SELECT likes FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"likes": row["likes"]})


@comments_bp.route("/<int:comment_id>/unlike", methods=["POST"])
def unlike_comment(comment_id):
    db = get_db()
    db.execute("UPDATE comments SET likes = MAX(0, likes - 1) WHERE id = ?", (comment_id,))
    db.commit()
    row = db.execute("SELECT likes FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"likes": row["likes"]})


@comments_bp.route("/<int:comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
    data  = request.get_json(force=True, silent=True) or {}
    token = (data.get("session_token") or "").strip()
    if not token:
        return jsonify({"error": "Unauthorized"}), 403
    db  = get_db()
    row = db.execute("SELECT session_token FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    if row["session_token"] != token:
        return jsonify({"error": "Unauthorized"}), 403
    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.commit()
    return jsonify({"ok": True})
