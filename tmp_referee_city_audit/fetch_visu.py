import concurrent.futures
import json
import time
from pathlib import Path

import requests

BASE = "https://visu.floorball.fr/api"
PLAYER_URL = f"{BASE}/public_players_get.php"
CLUBS_URL = f"{BASE}/public_clubs_getall.php"
OUT = Path("referee-city-audit-output")
HEADERS = {"Accept": "application/json", "Content-Type": "application/json; charset=UTF-8"}
SEASONS = [
    {"id": 23, "name": "2025-26"},
    {"id": 22, "name": "2024-25"},
    {"id": 21, "name": "2023-24"},
    {"id": 20, "name": "2022-23"},
]


def request_json(method, url, timeout=10, attempts=1, **kwargs):
    last = None
    for attempt in range(attempts):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(2 * (attempt + 1))
    raise last


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


def fetch_roster(task):
    season, club = task
    result = {
        "season_id": season["id"], "season_name": season["name"],
        "club_id": club.get("id"), "club_name": club.get("name"),
        "error": None, "players": [],
    }
    try:
        payload = request_json(
            "POST", PLAYER_URL, timeout=12, attempts=1,
            json={"command": "club", "season": season["id"], "id": club.get("id")},
            headers=HEADERS,
        )
        players = as_list(payload, "players", "data")
        result["players"] = [
            {"id": p.get("id"), "name": p.get("name"),
             "firstname": p.get("firstname"), "lastname": p.get("lastname")}
            for p in players if isinstance(p, dict)
        ]
    except Exception as exc:
        result["error"] = repr(exc)
    return result


def main():
    OUT.mkdir(exist_ok=True)
    clubs_payload = request_json("GET", CLUBS_URL, timeout=35, attempts=5, headers={"Accept": "application/json"})
    clubs = [sanitize_club(x) for x in as_list(clubs_payload, "clubs", "data") if isinstance(x, dict)]
    tasks = [(season, club) for season in SEASONS for club in clubs if club.get("id") is not None]
    rosters = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        futures = [pool.submit(fetch_roster, task) for task in tasks]
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            rosters.append(future.result())
            if n % 50 == 0:
                print(f"Fetched {n}/{len(tasks)} rosters", flush=True)
    rosters.sort(key=lambda x: (-int(x.get("season_id") or -1), int(x.get("club_id") or -1)))
    (OUT / "clubs.json").write_text(json.dumps({"clubs": clubs}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "seasons.json").write_text(json.dumps({"selected": SEASONS}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "rosters.json").write_text(json.dumps({"rosters": rosters}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "clubs": len(clubs), "seasons_selected": len(SEASONS),
        "rosters_requested": len(tasks),
        "rosters_successful": sum(not x.get("error") for x in rosters),
        "roster_errors": sum(bool(x.get("error")) for x in rosters),
        "player_rows": sum(len(x.get("players") or []) for x in rosters),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
