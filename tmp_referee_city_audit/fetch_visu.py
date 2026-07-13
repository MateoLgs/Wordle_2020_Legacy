import concurrent.futures
import json
import re
import time
from pathlib import Path

import requests

BASE = "https://visu.floorball.fr/api"
PLAYER_URL = f"{BASE}/public_players_get.php"
CLUBS_URL = f"{BASE}/public_clubs_getall.php"
SEASONS_URL = f"{BASE}/public_season_getall.php"
OUT = Path("referee-city-audit-output")
HEADERS = {"Accept": "application/json", "Content-Type": "application/json; charset=UTF-8"}


def request_json(method, url, **kwargs):
    error = None
    for attempt in range(4):
        try:
            response = requests.request(method, url, timeout=25, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            error = repr(exc)
            time.sleep(1.25 * (attempt + 1))
    raise RuntimeError(error)


def as_list(payload, *keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def sanitize_club(club):
    return {k: club.get(k) for k in (
        "id", "name", "shortname", "city", "postcode", "streetaddress",
        "address", "town", "zipcode", "clubid", "clubname"
    ) if k in club}


def sanitize_season(season):
    return {
        "id": season.get("id"),
        "name": season.get("name"),
        "iscurrent": season.get("iscurrent"),
    }


def season_start_year(season):
    match = re.search(r"(20\d{2})", str(season.get("name") or ""))
    return int(match.group(1)) if match else None


def fetch_roster(task):
    season, club = task
    result = {
        "season_id": season["id"],
        "season_name": season["name"],
        "club_id": club.get("id"),
        "club_name": club.get("name"),
        "error": None,
        "players": [],
    }
    try:
        payload = request_json(
            "POST",
            PLAYER_URL,
            json={"command": "club", "season": season["id"], "id": club.get("id")},
            headers=HEADERS,
        )
        players = as_list(payload, "players", "data")
        result["players"] = [
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "firstname": player.get("firstname"),
                "lastname": player.get("lastname"),
            }
            for player in players
            if isinstance(player, dict)
        ]
    except Exception as exc:
        result["error"] = repr(exc)
    return result


def main():
    OUT.mkdir(exist_ok=True)
    clubs_payload = request_json("GET", CLUBS_URL, headers={"Accept": "application/json"})
    seasons_payload = request_json("GET", SEASONS_URL, headers={"Accept": "application/json"})
    clubs = [sanitize_club(x) for x in as_list(clubs_payload, "clubs", "data") if isinstance(x, dict)]
    seasons_all = [sanitize_season(x) for x in as_list(seasons_payload, "seasons", "data") if isinstance(x, dict)]
    seasons = [x for x in seasons_all if season_start_year(x) is not None and season_start_year(x) >= 2022]
    if not seasons:
        seasons = sorted(seasons_all, key=lambda x: int(x.get("id") or -1), reverse=True)[:4]
    seasons.sort(key=lambda x: int(x.get("id") or -1), reverse=True)

    tasks = [(season, club) for season in seasons for club in clubs if club.get("id") is not None]
    rosters = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_roster, task) for task in tasks]
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            rosters.append(future.result())
            if n % 50 == 0:
                print(f"Fetched {n}/{len(tasks)} rosters", flush=True)

    rosters.sort(key=lambda x: (-int(x.get("season_id") or -1), int(x.get("club_id") or -1)))
    (OUT / "clubs.json").write_text(json.dumps({"clubs": clubs}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "seasons.json").write_text(json.dumps({"all": seasons_all, "selected": seasons}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "rosters.json").write_text(json.dumps({"rosters": rosters}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "clubs": len(clubs),
        "seasons_selected": len(seasons),
        "rosters_requested": len(tasks),
        "rosters_successful": sum(not x.get("error") for x in rosters),
        "roster_errors": sum(bool(x.get("error")) for x in rosters),
        "player_rows": sum(len(x.get("players") or []) for x in rosters),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
