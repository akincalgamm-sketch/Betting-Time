from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any, List, Tuple

@dataclass
class Game:
    id: int
    home_id: int
    away_id: int
    home_name: str
    away_name: str
    date: str
    status_short: str
    league_id: Optional[int] = None
    season: Optional[int] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None

@dataclass
class TeamForm:
    form_string: str
    wins: int
    draws: int
    losses: int
    avg_scored: float
    avg_conceded: float

@dataclass
class PredictionResult:
    breakdown: List[Tuple[str, Any]]
    model_home: float
    model_draw: float
    model_away: float
    market_home: Optional[float]
    market_draw: Optional[float]
    market_away: Optional[float]
    final_home: float
    final_draw: float
    final_away: float

def normalize_game(sport: str, raw: dict) -> Game:
    if not isinstance(raw, dict):
        return Game(id=0, home_id=0, away_id=0, home_name="Ev", away_name="Dep", date="", status_short="NS")
    
    fixture = raw.get("fixture") or raw.get("game") or {}
    f_id = fixture.get("id") or raw.get("id") or 0
    date_str = fixture.get("date") or raw.get("date") or ""
    status = fixture.get("status", {}).get("short") or raw.get("status") or "NS"
    
    league = raw.get("league") or {}
    league_id = league.get("id")
    season = league.get("season")
    
    teams = raw.get("teams") or {}
    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}
    
    home_id = home_team.get("id") or 1
    away_id = away_team.get("id") or 2
    home_name = home_team.get("name") or "Ev Sahibi"
    away_name = away_team.get("name") or "Deplasman"
    
    goals = raw.get("goals") or raw.get("scores") or {}
    home_score = goals.get("home")
    away_score = goals.get("away")
    
    return Game(
        id=int(f_id),
        home_id=int(home_id),
        away_id=int(away_id),
        home_name=str(home_name),
        away_name=str(away_name),
        date=str(date_str),
        status_short=str(status),
        league_id=league_id,
        season=season,
        home_score=home_score,
        away_score=away_score
    )

def compute_form(sport: str, games: list, team_id: int) -> TeamForm:
    if not games:
        return TeamForm(form_string="G-B-M-G-G", wins=3, draws=1, losses=1, avg_scored=1.6, avg_conceded=1.1)
    
    wins, draws, losses = 0, 0, 0
    scored_total, conceded_total = 0, 0
    form_chars = []
    
    for item in games[:5]:
        g = normalize_game(sport, item)
        if g.home_score is None or g.away_score is None:
            continue
            
        is_home = (g.home_id == team_id)
        my_score = g.home_score if is_home else g.away_score
        opp_score = g.away_score if is_home else g.home_score
        
        scored_total += my_score
        conceded_total += opp_score
        
        if my_score > opp_score:
            wins += 1
            form_chars.append("G")
        elif my_score == opp_score:
            draws += 1
            form_chars.append("B")
        else:
            losses += 1
            form_chars.append("M")
            
    count = max(1, len(form_chars))
    form_str = "-".join(form_chars) if form_chars else "G-B-M-G-G"
    
    return TeamForm(
        form_string=form_str,
        wins=wins,
        draws=draws,
        losses=losses,
        avg_scored=round(scored_total / count, 2) if form_chars else 1.5,
        avg_conceded=round(conceded_total / count, 2) if form_chars else 1.1
    )

def standing_strength(standings_flat: list, team_id: int) -> Optional[float]:
    if not standings_flat:
        return 0.65
    for rank, item in enumerate(standings_flat, 1):
        t_id = item.get("team", {}).get("id") or item.get("id")
        if t_id == team_id:
            total_teams = max(20, len(standings_flat))
            return round(1.0 - (rank / total_teams), 2)
    return 0.50

def most_recent_completed_date(sport: str, games: list) -> Optional[str]:
    if not games:
        return None
    for item in games:
        g = normalize_game(sport, item)
        if g.date:
            return g.date[:10]
    return None

def rest_days(match_date: str, last_date: Optional[str]) -> int:
    if not match_date or not last_date:
        return 4
    try:
        d1 = datetime.strptime(match_date[:10], "%Y-%m-%d")
        d2 = datetime.strptime(last_date[:10], "%Y-%m-%d")
        return max(1, (d1 - d2).days)
    except Exception:
        return 4

def build_prediction(
    sport: str,
    home_form: TeamForm,
    away_form: TeamForm,
    home_venue_form: TeamForm,
    away_venue_form: TeamForm,
    h2h_games: list,
    home_id: int,
    away_id: int,
    home_standing_strength: Optional[float],
    away_standing_strength: Optional[float],
    home_rest: int,
    away_rest: int,
    home_injuries: Optional[int],
    away_injuries: Optional[int],
    odds_values: Any,
    home_name: str,
    away_name: str,
) -> PredictionResult:
    # 1. Form ve Saha Avantajı
    h_form_pts = (home_form.wins * 3 + home_form.draws) * 5
    a_form_pts = (away_form.wins * 3 + away_form.draws) * 5
    
    # 2. Lig Güç Seviyesi
    h_stand_pts = (home_standing_strength or 0.5) * 35
    a_stand_pts = (away_standing_strength or 0.5) * 35
    
    # 3. Yorgunluk ve Sakatlık Faktörleri
    h_rest_bonus = 6 if home_rest >= 4 else -4
    a_rest_bonus = 6 if away_rest >= 4 else -4
    h_inj_penalty = (home_injuries or 0) * 3
    a_inj_penalty = (away_injuries or 0) * 3
    
    # Toplam Algoritma Puanları
    home_score = max(10, h_form_pts + h_stand_pts + 10 + h_rest_bonus - h_inj_penalty)
    away_score = max(10, a_form_pts + a_stand_pts + a_rest_bonus - a_inj_penalty)
    total = home_score + away_score
    
    model_home = round(home_score / total, 2)
    model_away = round(away_score / total, 2)
    model_draw = round(max(0.12, 1.0 - (model_home + model_away)), 2)
    
    # Bahis Şirketi Oran Analizi
    market_home, market_draw, market_away = None, None, None
    if isinstance(odds_values, dict) and "1" in odds_values:
        try:
            o1, ox, o2 = float(odds_values["1"]), float(odds_values["X"]), float(odds_values["2"])
            inv_sum = (1/o1) + (1/ox) + (1/o2)
            market_home, market_draw, market_away = round((1/o1)/inv_sum, 2), round((1/ox)/inv_sum, 2), round((1/o2)/inv_sum, 2)
        except Exception:
            pass

    # Nihai Olasılıklar
    if market_home is not None:
        final_home = round(model_home * 0.6 + market_home * 0.4, 2)
        final_draw = round(model_draw * 0.6 + market_draw * 0.4, 2)
        final_away = round(model_away * 0.6 + market_away * 0.4, 2)
    else:
        final_home, final_draw, final_away = model_home, model_draw, model_away

    # 6 Faktörlü Arayüz Detay Kırılımı
    breakdown = [
        ("Son 5 Maç Formu", f"{home_form.form_string} vs {away_form.form_string}"),
        ("Saha Avantajı (İç/Dış)", f"{home_venue_form.form_string} vs {away_venue_form.form_string}"),
        ("Gol Ortalamaları", f"{home_form.avg_scored} Gol vs {away_form.avg_scored} Gol"),
        ("Lig Derece Gücü", f"%{int((home_standing_strength or 0.5)*100)} vs %{int((away_standing_strength or 0.5)*100)}"),
        ("Dinlenme Süresi", f"{home_rest} Gün vs {away_rest} Gün"),
        ("Sakat / Eksik Sayısı", f"{home_injuries or 0} vs {away_injuries or 0}"),
    ]

    return PredictionResult(
        breakdown=breakdown,
        model_home=model_home,
        model_draw=model_draw,
        model_away=model_away,
        market_home=market_home,
        market_draw=market_draw,
        market_away=market_away,
        final_home=final_home,
        final_draw=final_draw,
        final_away=final_away,
    )
    
