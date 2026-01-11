import base64
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ENGINEERING_API = "https://engineering.atspotify.com/api/entries"
SPOTIFY_ARTIST_ID = "12GqGscKJx3aE4t07u7eVZ"
SPOTIFY_ARTIST_URL = f"https://open.spotify.com/artist/{SPOTIFY_ARTIST_ID}"

REPORTS_DIR = Path("reports")
REPORT_PATH = REPORTS_DIR / "peso_pluma_report.md"


def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(request) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_json(url):
    return json.loads(fetch_text(url))


def extract_initial_state(html):
    match = re.search(
        r'<script id="initialState" type="text/plain">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    encoded = match.group(1).strip()
    decoded = base64.b64decode(encoded + "==", validate=False).decode(
        "utf-8", errors="replace"
    )
    return json.loads(decoded)


def find_stats(data):
    if not data:
        return None
    stack = [data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            stats = current.get("stats")
            if isinstance(stats, dict) and {
                "followers",
                "monthlyListeners",
            }.issubset(stats.keys()):
                return stats
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return None


class TrackRowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_track = False
        self.track_depth = 0
        self.capture_title = False
        self.current = None
        self.tracks = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "div" and attrs_dict.get("data-testid") == "track-row":
            self.in_track = True
            self.track_depth = 1
            self.current = {"title": None, "streams": None}
            return
        if self.in_track:
            self.track_depth += 1
            if (
                tag == "span"
                and "class" in attrs_dict
                and "ListRowTitle__LineClamp" in attrs_dict["class"]
            ):
                self.capture_title = True

    def handle_endtag(self, tag):
        if self.in_track:
            self.track_depth -= 1
            if self.track_depth <= 0:
                if (
                    self.current
                    and self.current["title"]
                    and self.current["streams"]
                ):
                    self.tracks.append(self.current)
                self.in_track = False
                self.track_depth = 0
                self.capture_title = False
                self.current = None

    def handle_data(self, data):
        if not self.in_track or not self.current:
            return
        text = data.strip()
        if not text:
            return
        if self.capture_title:
            self.current["title"] = text
            self.capture_title = False
            return
        if self.current["streams"] is None and re.fullmatch(r"[0-9,]+", text):
            self.current["streams"] = text


def parse_popular_tracks(html):
    parser = TrackRowParser()
    parser.feed(html)
    return parser.tracks


def format_int(value):
    return f"{value:,}" if isinstance(value, int) else value


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    query = "peso pluma"
    engineering_url = (
        f"{ENGINEERING_API}?content_type=blogPost&query={urllib.parse.quote(query)}&limit=1"
    )
    engineering_data = fetch_json(engineering_url)
    engineering_total = engineering_data.get("total", 0)

    artist_html = fetch_text(SPOTIFY_ARTIST_URL)
    initial_state = extract_initial_state(artist_html)
    stats = find_stats(initial_state) if initial_state else None

    monthly_listeners = None
    followers = None
    if stats:
        monthly_listeners = stats.get("monthlyListeners")
        followers = stats.get("followers")

    tracks = parse_popular_tracks(artist_html)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Peso Pluma statistics (public sources)",
        "",
        f"Generated: {timestamp}",
        "",
        "## Sources",
        f"- {engineering_url}",
        f"- {SPOTIFY_ARTIST_URL}",
        "",
        "## Engineering blog mentions",
        f"- Matching blog posts: {engineering_total}",
        "",
        "## Spotify artist stats",
        f"- Monthly listeners: {format_int(monthly_listeners)}",
        f"- Followers: {format_int(followers)}",
        "",
        "## Popular tracks (from artist page)",
    ]

    if tracks:
        for idx, track in enumerate(tracks, start=1):
            lines.append(f"{idx}. {track['title']} - {track['streams']}")
    else:
        lines.append("No track rows detected on the artist page.")

    lines.append("")
    lines.append(
        "Note: Popular track stream counts are parsed from the public artist page HTML."
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
