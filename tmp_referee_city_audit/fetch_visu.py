import concurrent.futures
import json
import re
import time
import unicodedata
from pathlib import Path

import requests

IDS = [461,1204,512,1002,732,1817,76,84,169,125,104,301,128,515,571,90,758,112,206,274,190,1269,211,219,183,81,258,1562,2180,113,777,201,781,54,1754,896,144,396,408,335,32,31,1809,2168,525,80,47,1792,852,401,117,186,89,86,145,182,207,476,223,1297,205,475,1459,166,167,216,823,239,370,177,178,1153,398,227,228,604,2178,18,1259,210,74,20,899,328,808,542,165,174,196,2215,342,2226,271,2177,305,953,118,99,573,194,2089,442,1649,1108,1992,843,967,990,845,2051,2119,534,273,995,459,681,687,2010,2053,229,102,199,67,633,2122,96,202,775,2095,457,364,507,2130,1384,866,2199,2213,93,1764,2198,2197,2224,2099,924,21,1898,998,1787,1819,87,2195,755,225,226,213,533,1621,1506,1672,2071,224,188,1805,433,741,1278,391,418,846,621,315,2115,1598,2063,29,159,1967,218,94,2059,1822,2193,2208,692,1808,124,2191,2192,516,1860,1811,1810,2212,2211,52,2148,2080,1646,1675,540,471,2100,715,2052,44,989,388,371,360,214,517,913,1081,374,2014,306,511,526,2151,1208,720,2189,98,34,2142,783,2217,1198,1237,259,929,64,1389,2045,1650,900,56,2032,629,2137,1143,2209,2210,1360,1645,2147,1657,549,1631,2143,2086,2085,628,1132,535,2025,2129,763,2062,105,905,448,2207,2206,1203,614,603,2203,180,1150,1989,1184,2060,518,2134,904,26,116,2058,373,187,407,2065,698,1296,2029,2156,1166,733,2146,2145,1256,38,222,911,1354,2087,2088,122,630,392,323,185,244,2114,857,215,1031,589,1584,197,108,714,1887,657,1885,1211,14,191,184,1888,441,1159,1873,1878,1879,798,204,736,24,1240,690,95,820,107,1774,1773,126,1766,1771,1705,1780,1065,1724,135,139,1723,1857,1854,1850,1851,685,179,688,1539,1075,131,1790,644,641,586,1130,1847,1729,1603,72,97,292,458,455,1543,1169,508,164,1622,1846,1668,673,133,1653,1722,1436,1855,1343,85,114,1602,262,462,910,581,1708,1745,1711,120,1706,1704,40,45,1841,529,817,886,880,814,36,50,811,782,121,243,1720,754,1797,1798,1719,1718,1285,1180,1619,59,484,70,1190,23,1699,1806,1693,612,611,1783,696,1767,1733,1689,1250,587,1732,1731,992,879,874,474,834,1571,425,862,819,1219,613,1597,68,1759,682,651,624,1788,1715,1813,1714,1591,1671,209,889,22,600,1730,1686,1682,1694,1579,832,1553,925,39,25,238,799,221,789,694,639,650,1060,702,721,200,289,257,620,983,346,347,527,729,220,648,649,646,570,65,632,903,79,520,747,748,454,537,467,382,88,27,565,170,564,563,156,712,645,717,716,275,643,260,708,590,596,403,361,181,424,57,562,560,48,559,737,333,502,530,372,597,584,583,592,662,661,660,602,577,1955,553,551,1158,437,368,1334,168,1282,365,311,656,695,640,927,404,1134,594,582,580,572,689,1009,101,341,51,946,935,440,1274,309,43,30,1029,343,192,230,241,240,217,231,212,234,1511,55,189,15,208,110,71,61,42,16,33,46,130,19,152,151,149,146,172,175,195,1177,1151,1178,77,78,1161,83,1014,978,1149,92,109,41,907,1136,1137,193,171,988,1020,1170,1171,103,62,1142,58,917,918,1179,1181,142,141,1168,1157,1514,976,916,1037,75,28,1147,198,1006,1145,1154,1183,115,999,1008,1175,138,137,136,53,134,1185,1160,1440,996,1187,912,1188,1162,1173]

BASE = "https://visu.floorball.fr/api"
PLAYER_URL = f"{BASE}/public_players_get.php"
CLUBS_URL = f"{BASE}/public_clubs_getall.php"
OUT = Path("referee-city-audit-output")
HEADERS = {"Accept": "application/json", "Content-Type": "application/json; charset=UTF-8"}


def request_json(method, url, **kwargs):
    error = None
    for attempt in range(6):
        try:
            response = requests.request(method, url, timeout=35, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            error = repr(exc)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(error)


def season_row(item):
    player = item.get("player") or {}
    return {
        "season_id": item.get("season_id"),
        "season_name": item.get("season_name"),
        "club_id": item.get("club_id"),
        "club_name": item.get("club_name"),
        "agecategory": item.get("agecategory"),
        "games_played": player.get("games_played"),
    }


def fetch_one(referee_id):
    row = {"requested_id": referee_id, "error": None}
    try:
        profile = request_json("POST", PLAYER_URL, json={"id": referee_id, "command": "get"}, headers=HEADERS)
        seasons = request_json("POST", PLAYER_URL, json={"id": referee_id, "command": "season"}, headers=HEADERS)
        row.update({
            "api_id": profile.get("id"),
            "name": profile.get("name"),
            "firstname": profile.get("firstname"),
            "lastname": profile.get("lastname"),
            "club_id": profile.get("clubid"),
            "club_name": profile.get("clubname"),
            "seasons": [season_row(x) for x in (seasons.get("seasons") or [])],
        })
    except Exception as exc:
        row["error"] = repr(exc)
    return row


def sanitize_clubs(payload):
    items = payload.get("clubs") or payload.get("data") or [] if isinstance(payload, dict) else payload
    result = []
    for club in items or []:
        if isinstance(club, dict):
            result.append({k: club.get(k) for k in (
                "id", "name", "shortname", "city", "postcode", "streetaddress",
                "address", "town", "zipcode", "clubid", "clubname"
            ) if k in club})
    return result


def main():
    OUT.mkdir(exist_ok=True)
    try:
        clubs = sanitize_clubs(request_json("GET", CLUBS_URL, headers={"Accept": "application/json"}))
        clubs_error = None
    except Exception as exc:
        clubs, clubs_error = [], repr(exc)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_one, referee_id) for referee_id in IDS]
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            rows.append(future.result())
            if n % 50 == 0:
                print(f"Fetched {n}/{len(IDS)}", flush=True)
    rows.sort(key=lambda x: x["requested_id"])
    (OUT / "players.json").write_text(json.dumps({"players": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "clubs.json").write_text(json.dumps({"error": clubs_error, "clubs": clubs}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "requested": len(IDS),
        "successful": sum(not x.get("error") for x in rows),
        "current_clubs": sum(bool(x.get("club_name")) for x in rows),
        "errors": sum(bool(x.get("error")) for x in rows),
        "clubs": len(clubs),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
