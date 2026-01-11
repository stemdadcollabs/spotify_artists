# Spotify artist reports

Small, reproducible scripts that scrape public Spotify artist pages to generate Markdown reports.

## What this repo contains
- `scripts/artist_group_benchmark.py`: starting from a base artist (currently Peso Pluma), pulls the related-artist network, gathers monthly listeners, followers, and top tracks, and writes `reports/artist_group_benchmark.md`.
- `scripts/peso_pluma_report.py`: pulls basic stats and popular tracks for Peso Pluma from public pages and writes `reports/peso_pluma_report.md`.
- `reports/`: generated Markdown reports ready to view on GitHub.

## How to run
1) Use Python 3.10+ (standard library only; no external deps).  
2) From the repo root, run the script you need, e.g.:
   - `python scripts/artist_group_benchmark.py`
   - `python scripts/peso_pluma_report.py`
3) Open the matching file in `reports/` to view results.

## Notes
- Data comes from public Spotify web pages (no private API access).
- Update `BASE_ARTIST_ID`/`SPOTIFY_ARTIST_ID` in the scripts if you want a different anchor artist.
- Licensed under MIT (see `LICENSE`).
