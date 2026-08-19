"""
Maç Analiz Web Uygulaması
=========================
FastAPI tabanlı, mobil tarayıcıdan kullanılacak maç analiz servisi.
Telegram gerekmez — telefonun tarayıcısından siteyi açıp kullanırsın.

Uç noktalar:
  GET /api/fixtures?sport=futbol      -> bugünün maçları
  GET /api/analyze?sport=futbol&fixture_id=123 -> tam analiz (JSON)
  GET /                                -> mobil arayüz (static/index.html)
"""
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import sports_api
from analysis import (
    normalize_game,
    compute_form,
    most_recent_completed_date,
    standing_strength,
    rest_days,
    build_prediction,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Maç Analiz API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_SPORTS = ("futbol", "basketbol")


@app.get("/api/fixtures")
async def api_fixtures(sport: str = Query(...)):
    if sport not in VALID_SPORTS:
        raise HTTPException(400, "Geçersiz spor. futbol ya da basketbol olmalı.")

    try:
        fixtures = await sports_api.get_today_fixtures(sport)
    except Exception as e:
        logger.exception("Fixtures alınamadı")
        raise HTTPException(502, f"Maçlar alınırken hata: {e}")

    out = []
    for raw in fixtures[:40]:
        g = normalize_game(sport, raw)
        out.append({
            "fixture_id": g.id,
            "home_name": g.home_name,
            "away_name": g.away_name,
            "date": g.date,
            "status": g.status_short,
        })
    return {"sport": sport, "count": len(out), "fixtures": out}


@app.get("/api/analyze")
async def api_analyze(sport: str = Query(...), fixture_id: int = Query(...)):
    if sport not in VALID_SPORTS:
        raise HTTPException(400, "Geçersiz spor. futbol ya da basketbol olmalı.")

    # önce bugünün fixture listesinden ilgili maçı buluyoruz (id -> takım eşlemesi için)
    try:
        fixtures = await sports_api.get_today_fixtures(sport)
    except Exception as e:
        raise HTTPException(502, f"Maç bulunamadı: {e}")

    raw_game = None
    for raw in fixtures:
        g_tmp = normalize_game(sport, raw)
        if g_tmp.id == fixture_id:
            raw_game = raw
            break

    if raw_game is None:
        raise HTTPException(404, "Maç bulunamadı (bugünün listesinde yok).")

    g = normalize_game(sport, raw_game)

    try:
        home_games = await sports_api.get_team_last_games(sport, g.home_id, count=5)
        away_games = await sports_api.get_team_last_games(sport, g.away_id, count=5)
        h2h_games = await sports_api.get_h2h(sport, g.home_id, g.away_id, count=5)
        home_venue_games = await sports_api.get_team_venue_games(sport, g.home_id, "home", count=5)
        away_venue_games = await sports_api.get_team_venue_games(sport, g.away_id, "away", count=5)

        standings_flat = []
        if g.league_id and g.season:
            standings_flat = await sports_api.get_standings(sport, g.league_id, g.season)

        odds_values = await sports_api.get_odds(sport, g.id)

        home_injuries_count = away_injuries_count = None
        if sport == "futbol":
            injuries = await sports_api.get_injuries(g.id)
            if injuries:
                home_injuries_count = sum(1 for i in injuries if i.get("team", {}).get("id") == g.home_id)
                away_injuries_count = sum(1 for i in injuries if i.get("team", {}).get("id") == g.away_id)
    except Exception as e:
        logger.exception("Analiz verisi alınamadı")
        raise HTTPException(502, f"Analiz verisi alınırken hata: {e}")

    home_form = compute_form(sport, home_games, g.home_id)
    away_form = compute_form(sport, away_games, g.away_id)
    home_venue_form = compute_form(sport, home_venue_games, g.home_id)
    away_venue_form = compute_form(sport, away_venue_games, g.away_id)

    home_standing = standing_strength(standings_flat, g.home_id) if standings_flat else None
    away_standing = standing_strength(standings_flat, g.away_id) if standings_flat else None

    home_last_date = most_recent_completed_date(sport, home_games)
    away_last_date = most_recent_completed_date(sport, away_games)
    home_rest = rest_days(g.date, home_last_date)
    away_rest = rest_days(g.date, away_last_date)

    result = build_prediction(
        sport=sport,
        home_form=home_form,
        away_form=away_form,
        home_venue_form=home_venue_form,
        away_venue_form=away_venue_form,
        h2h_games=h2h_games,
        home_id=g.home_id,
        away_id=g.away_id,
        home_standing_strength=home_standing,
        away_standing_strength=away_standing,
        home_rest=home_rest,
        away_rest=away_rest,
        home_injuries=home_injuries_count,
        away_injuries=away_injuries_count,
        odds_values=odds_values,
        home_name=g.home_name,
        away_name=g.away_name,
    )

    h2h_out = []
    for raw in h2h_games[:5]:
        hg = normalize_game(sport, raw)
        if hg.home_score is None:
            continue
        h2h_out.append({
            "date": hg.date[:10],
            "home_name": hg.home_name,
            "home_score": hg.home_score,
            "away_score": hg.away_score,
            "away_name": hg.away_name,
        })

    return {
        "sport": sport,
        "home_name": g.home_name,
        "away_name": g.away_name,
        "home_form": {
            "form_string": home_form.form_string,
            "wins": home_form.wins,
            "draws": home_form.draws,
            "losses": home_form.losses,
            "avg_scored": home_form.avg_scored,
            "avg_conceded": home_form.avg_conceded,
        },
        "away_form": {
            "form_string": away_form.form_string,
            "wins": away_form.wins,
            "draws": away_form.draws,
            "losses": away_form.losses,
            "avg_scored": away_form.avg_scored,
            "avg_conceded": away_form.avg_conceded,
        },
        "h2h": h2h_out,
        "breakdown": [{"name": name, "value": value} for name, value in result.breakdown],
        "model": {"home": result.model_home, "draw": result.model_draw, "away": result.model_away},
        "market": (
            {"home": result.market_home, "draw": result.market_draw, "away": result.market_away}
            if result.market_home is not None else None
        ),
        "final": {"home": result.final_home, "draw": result.final_draw, "away": result.final_away},
    }


# Statik dosyaları (index.html, manifest.json, ikon) sun
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/manifest.json")
async def manifest():
    return FileResponse("static/manifest.json")
