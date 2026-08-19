"""
api-sports.io için ince bir istemci katmanı.
Futbol ve basketbol için aynı yapıyı (fixtures/games, teams/statistics, h2h) kullanır.
"""
import httpx
from datetime import date
from config import SPORT_BASE_URLS, API_SPORTS_KEY

TIMEOUT = 15.0


def _headers():
    return {"x-apisports-key": API_SPORTS_KEY}


async def _get(sport: str, endpoint: str, params: dict) -> dict:
    base_url = SPORT_BASE_URLS[sport]
    url = f"{base_url}/{endpoint}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


async def get_today_fixtures(sport: str) -> list[dict]:
    """Bugünün maçlarını döner. Futbol için sadece popüler liglerle sınırlamıyoruz,
    api tüm ligleri döner; çok kalabalık olabileceği için sonucu çağıran taraf kısaltır."""
    today = date.today().isoformat()
    if sport == "futbol":
        data = await _get(sport, "fixtures", {"date": today})
        return data.get("response", [])
    elif sport == "basketbol":
        data = await _get(sport, "games", {"date": today})
        return data.get("response", [])
    return []


async def get_team_last_games(sport: str, team_id: int, count: int = 5) -> list[dict]:
    if sport == "futbol":
        data = await _get(sport, "fixtures", {"team": team_id, "last": count})
        return data.get("response", [])
    elif sport == "basketbol":
        # basketbol api'sinde "last" parametresi yok; sezon bazlı çekip son N'i alıyoruz
        season = str(date.today().year)
        data = await _get(sport, "games", {"team": team_id, "season": season})
        games = data.get("response", [])
        # tarihe göre sırala, en yeni count kadarını al
        games.sort(key=lambda g: g.get("date", ""), reverse=True)
        return games[:count]
    return []


async def get_h2h(sport: str, team1_id: int, team2_id: int, count: int = 5) -> list[dict]:
    h2h_param = f"{team1_id}-{team2_id}"
    if sport == "futbol":
        data = await _get(sport, "fixtures/headtohead", {"h2h": h2h_param, "last": count})
        return data.get("response", [])
    elif sport == "basketbol":
        data = await _get(sport, "games", {"h2h": h2h_param})
        games = data.get("response", [])
        games.sort(key=lambda g: g.get("date", ""), reverse=True)
        return games[:count]
    return []


async def get_team_venue_games(sport: str, team_id: int, venue: str, count: int = 5) -> list[dict]:
    """venue: 'home' ya da 'away'. Takımın SADECE o sahadaki son maçlarını döner
    (daha fazla veri çekip filtreleyerek, çünkü api'ler doğrudan venue filtresi
    desteklemiyor)."""
    if sport == "futbol":
        data = await _get(sport, "fixtures", {"team": team_id, "last": 20})
        games = data.get("response", [])
    elif sport == "basketbol":
        season = str(date.today().year)
        data = await _get(sport, "games", {"team": team_id, "season": season})
        games = data.get("response", [])
        games.sort(key=lambda g: g.get("date", ""), reverse=True)
    else:
        return []

    filtered = []
    for g in games:
        team_side = g["teams"]["home"] if venue == "home" else g["teams"]["away"]
        if team_side["id"] == team_id:
            filtered.append(g)
        if len(filtered) >= count:
            break
    return filtered


async def get_standings(sport: str, league_id: int, season) -> list[dict]:
    """Lig sıralamasını düzleştirilmiş liste olarak döner: her eleman
    {'team_id', 'rank', 'points'/'win_pct'} içerir."""
    try:
        data = await _get(sport, "standings", {"league": league_id, "season": season})
    except Exception:
        return []

    response = data.get("response", [])
    flat = []

    if sport == "futbol":
        groups = response[0]["league"]["standings"] if response else []
        for group in groups:
            for entry in group:
                flat.append({
                    "team_id": entry["team"]["id"],
                    "rank": entry["rank"],
                    "points": entry.get("points"),
                })
    elif sport == "basketbol":
        # basketbol standings çoğunlukla düz liste ya da grup listesi olabilir
        groups = response if response and isinstance(response[0], list) else [response]
        for group in groups:
            for entry in group:
                games = entry.get("games", {})
                win = (games.get("win") or {}).get("total", 0) or 0
                lose = (games.get("lose") or {}).get("total", 0) or 0
                total = win + lose
                win_pct = round(win / total, 3) if total else None
                flat.append({
                    "team_id": entry["team"]["id"],
                    "rank": entry.get("position"),
                    "win_pct": win_pct,
                })

    total_teams = len(flat)
    for e in flat:
        e["total_teams"] = total_teams
    return flat


async def get_odds(sport: str, fixture_id: int) -> dict | None:
    """Maç kazananı (1X2 / Home-Away) piyasa oranlarını döner, bulunamazsa None."""
    try:
        if sport == "futbol":
            data = await _get(sport, "odds", {"fixture": fixture_id})
        else:
            data = await _get(sport, "odds", {"game": fixture_id})
    except Exception:
        return None

    response = data.get("response", [])
    if not response:
        return None

    for entry in response:
        for bookmaker in entry.get("bookmakers", []):
            for bet in bookmaker.get("bets", []):
                name = (bet.get("name") or "").lower()
                if "winner" in name or "home/away" in name or "match winner" in name:
                    values = {v["value"].lower(): float(v["odd"]) for v in bet.get("values", [])}
                    if values:
                        return values
    return None


async def get_injuries(fixture_id: int) -> list[dict]:
    """Sadece futbol için: bir maçtaki sakat/cezalı oyuncu listesini döner."""
    try:
        data = await _get("futbol", "injuries", {"fixture": fixture_id})
        return data.get("response", [])
    except Exception:
        return []
