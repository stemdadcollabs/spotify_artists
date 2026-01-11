import base64
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SPOTIFY_ARTIST_URL = "https://open.spotify.com/artist/{}"
BASE_ARTIST_ID = "12GqGscKJx3aE4t07u7eVZ"

REPORTS_DIR = Path("reports")
REPORT_PATH = REPORTS_DIR / "artist_group_benchmark.md"


def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_initial_state(html):
    marker = '<script id="initialState" type="text/plain">'
    start = html.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = html.find("</script>", start)
    if end == -1:
        return None
    encoded = html[start:end].strip()
    decoded = base64.b64decode(encoded + "==", validate=False).decode(
        "utf-8", errors="replace"
    )
    return json.loads(decoded)


def parse_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
    return None


def format_int(value):
    return f"{value:,}" if isinstance(value, int) else "n/a"


def format_percent(value):
    return f"{value * 100:.1f}%" if isinstance(value, float) else "n/a"


def extract_related_artists(state, artist_id):
    artist_key = f"spotify:artist:{artist_id}"
    artist = (
        state.get("entities", {})
        .get("items", {})
        .get(artist_key, {})
    )
    related = (
        artist.get("relatedContent", {})
        .get("relatedArtists", {})
        .get("items", [])
    )
    results = []
    for item in related:
        uri = item.get("uri")
        if not uri:
            continue
        artist_id = uri.split(":")[-1]
        name = (item.get("profile") or {}).get("name")
        results.append({"id": artist_id, "name": name})
    return results


def extract_artist_metrics(state, artist_id):
    artist_key = f"spotify:artist:{artist_id}"
    artist = (
        state.get("entities", {})
        .get("items", {})
        .get(artist_key, {})
    )
    profile = artist.get("profile") or {}
    stats = artist.get("stats") or {}
    top_tracks = []
    top_track_items = (
        artist.get("discography", {})
        .get("topTracks", {})
        .get("items", [])
    )
    for item in top_track_items[:5]:
        track = item.get("track") or {}
        top_tracks.append(
            {
                "name": track.get("name"),
                "playcount": parse_int(track.get("playcount")),
            }
        )
    return {
        "name": profile.get("name") or artist_id,
        "artist_id": artist_id,
        "monthly_listeners": parse_int(stats.get("monthlyListeners")),
        "followers": parse_int(stats.get("followers")),
        "top_tracks": top_tracks,
    }


def assign_ranks(rows, key):
    sorted_rows = sorted(
        [row for row in rows if row.get(key) is not None],
        key=lambda row: row[key],
        reverse=True,
    )
    for idx, row in enumerate(sorted_rows, start=1):
        row[f"{key}_rank"] = idx


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    base_html = fetch_text(SPOTIFY_ARTIST_URL.format(BASE_ARTIST_ID))
    base_state = extract_initial_state(base_html)
    if not base_state:
        raise RuntimeError("Unable to parse initialState for base artist.")

    related_artists = extract_related_artists(base_state, BASE_ARTIST_ID)
    artist_ids = [BASE_ARTIST_ID] + [
        artist["id"] for artist in related_artists
    ]

    rows = []
    for artist_id in artist_ids:
        html = base_html if artist_id == BASE_ARTIST_ID else fetch_text(
            SPOTIFY_ARTIST_URL.format(artist_id)
        )
        state = base_state if artist_id == BASE_ARTIST_ID else extract_initial_state(html)
        if not state:
            rows.append(
                {
                    "name": artist_id,
                    "artist_id": artist_id,
                    "monthly_listeners": None,
                    "followers": None,
                    "top_tracks": [],
                }
            )
            continue
        rows.append(extract_artist_metrics(state, artist_id))

    total_monthly = sum(
        row["monthly_listeners"]
        for row in rows
        if isinstance(row.get("monthly_listeners"), int)
    )
    total_followers = sum(
        row["followers"]
        for row in rows
        if isinstance(row.get("followers"), int)
    )

    for row in rows:
        monthly = row.get("monthly_listeners")
        followers = row.get("followers")
        row["monthly_share"] = (
            monthly / total_monthly
            if isinstance(monthly, int) and total_monthly
            else None
        )
        row["followers_share"] = (
            followers / total_followers
            if isinstance(followers, int) and total_followers
            else None
        )
        top_total = sum(
            track["playcount"]
            for track in row.get("top_tracks", [])
            if isinstance(track.get("playcount"), int)
        )
        row["top_tracks_total"] = top_total if top_total else None

    assign_ranks(rows, "monthly_listeners")
    assign_ranks(rows, "followers")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Artist group benchmark",
        "",
        f"Generated: {timestamp}",
        "",
        "## Sources",
        "- https://open.spotify.com/ (public artist pages)",
        "",
        "## Group summary table",
        "",
        "| Artist | Monthly listeners | Followers | Top 5 streams total | ML rank | ML share | Follower rank | Follower share |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        lines.append(
            "| {artist} | {monthly} | {followers} | {top_total} | {ml_rank} | {ml_share} | {f_rank} | {f_share} |".format(
                artist=row["name"],
                monthly=format_int(row.get("monthly_listeners")),
                followers=format_int(row.get("followers")),
                top_total=format_int(row.get("top_tracks_total")),
                ml_rank=row.get("monthly_listeners_rank", "n/a"),
                ml_share=format_percent(row.get("monthly_share")),
                f_rank=row.get("followers_rank", "n/a"),
                f_share=format_percent(row.get("followers_share")),
            )
        )

    lines.append(
        "| TOTAL (group) | {monthly} | {followers} | {top_total} | - | 100.0% | - | 100.0% |".format(
            monthly=format_int(total_monthly) if total_monthly else "n/a",
            followers=format_int(total_followers) if total_followers else "n/a",
            top_total=format_int(
                sum(
                    row["top_tracks_total"]
                    for row in rows
                    if isinstance(row.get("top_tracks_total"), int)
                )
            ),
        )
    )

    lines.extend(
        [
            "",
            "## Top tracks (top 5)",
        ]
    )

    for row in rows:
        lines.append("")
        lines.append(f"### {row['name']}")
        if row["top_tracks"]:
            for idx, track in enumerate(row["top_tracks"], start=1):
                lines.append(
                    f"{idx}. {track['name']} - {format_int(track.get('playcount'))}"
                )
        else:
            lines.append("No top tracks detected on the artist page.")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
