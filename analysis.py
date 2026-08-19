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
    has_data: bool = True

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
    teams = raw.get("teams") or {}
    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}
    goals = raw.get("goals") or raw.get("scores") or {}
    
    return Game(
        id=int(f_id),
        home_id=int(home_team.get("id") or 1),
        away_id=int(away_team.get("id") or 2),
        home_name=str(home_team.get("name") or "Ev Sahibi"),
        away_name=str(away_team.get("name") or "Deplasman"),
        date=str(date_str),
        status_short=str(status),
        league_id=league.get("id"),
        season=league.get("season"),
        home_score=goals.get("home"),
        away_score=goals.get("away")
    )

def compute_form(sport: str, games: list, team_id: int) -> TeamForm:
    if not games:
        return TeamForm(form_string="Veri Yok", wins=0, draws=0, losses=0, avg_scored=0.0, avg_conceded=0.0, has_data=False)
    
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
            
    count = len(form_chars)
    if count == 0:
        return TeamForm(form_string="Veri Yok", wins=0, draws=0, losses=0, avg_scored=0.0, avg_conceded=0.0, has_data=False)
        
    return TeamForm(
        form_string="-".join(form_chars),
        wins=wins,
        draws=draws,
        losses=losses,
        avg_scored=round(scored_total / count, 2),
        avg_conceded=round(conceded_total / count, 2),
        has_data=True
    )

def standing_strength(standings_flat: list, team_id: int) -> Optional[float]:
    if not standings_flat:
        return None
    for rank, item in enumerate(standings_flat, 1):
        t_id = item.get("team", {}).get("id") or item.get("id")
        if t_id == team_id:
            total_teams = max(20, len(standings_flat))
            return round(1.0 - (rank / total_teams), 2)
    return None

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
    
    # 1. Bahis Oranı Algılanmış mı?
    market_home, market_draw, market_away = None, None, None
    if isinstance(odds_values, dict) and "1" in odds_values:
        try:
            o1, ox, o2 = float(odds_values["1"]), float(odds_values["X"]), float(odds_values["2"])
            inv_sum = (1/o1) + (1/ox) + (1/o2)
            market_home = round((1/o1)/inv_sum, 2)
            market_draw = round((1/ox)/inv_sum, 2)
            market_away = round((1/o2)/inv_sum, 2)
        except Exception:
            pass

    # 2. Gerçek Veri Var mı Kontrolü
    has_real_data = home_form.has_data or away_form.has_data or (home_standing_strength is not None)

    if not has_real_data:
        # Veri yoksa orana bak, oran da yoksa dengeli ver
        if market_home is not None:
            m_h, m_d, m_a = market_home, market_draw, market_away
        else:
            m_h, m_d, m_a = 0.40, 0.28, 0.32
            
        breakdown = [
            ("Analiz Durumu", "Yetersiz API Verisi"),
            ("Son 5 Maç Formu", "Veri Bulunamadı"),
            ("Saha Avantajı", "Veri Bulunamadı"),
            ("Gol Ortalaması", "Veri Bulunamadı"),
            ("Lig Sıralaması", "Veri Bulunamadı"),
            ("Sakatlık / Eksik", "Veri Bulunamadı")
        ]
        return PredictionResult(
            breakdown=breakdown,
            model_home=m_h, model_draw=m_d, model_away=m_a,
            market_home=market_home, market_draw=market_draw, market_away=market_away,
            final_home=m_h, final_draw=m_d, final_away=m_a
        )

    # 3. Gerçek Verilerle Hesaplama
    h_score = (home_form.wins * 3 + home_form.draws) * 6 + ((home_standing_strength or 0.5) * 30) + 8
    a_score = (away_form.wins * 3 + away_form.draws) * 6 + ((away_standing_strength or 0.5) * 30)
    d_score = max(5, (h_score + a_score) * 0.25)

    tot = h_score + a_score + d_score
    m_h, m_d, m_a = round(h_score/tot, 2), round(d_score/tot, 2), round(a_score/tot, 2)

    if market_home is not None:
        f_h = round(m_h * 0.6 + market_home * 0.4, 2)
        f_d = round(m_d * 0.6 + market_draw * 0.4, 2)
        f_a = round(1.0 - (f_h + f_d), 2)
    else:
        f_h, f_d, f_a = m_h, m_d, m_a

    breakdown = [
        ("Son 5 Maç Formu", f"{home_form.form_string} vs {away_form.form_string}"),
        ("Saha Avantajı", f"{home_venue_form.form_string} vs {away_venue_form.form_string}"),
        ("Gol Ortalamaları", f"{home_form.avg_scored} vs {away_form.avg_scored}"),
        ("Lig Derece Gücü", f"%{int((home_standing_strength or 0.5)*100)} vs %{int((away_standing_strength or 0.5)*100)}"),
        ("Dinlenme Süresi", f"{home_rest} Gün vs {away_rest} Gün"),
        ("Sakat Sayısı", f"{home_injuries or 0} vs {away_injuries or 0}")
    ]

    return PredictionResult(
        breakdown=breakdown,
        model_home=m_h, model_draw=m_d, model_away=m_a,
        market_home=market_home, market_draw=market_draw, market_away=market_away,
        final_home=f_h, final_draw=f_d, final_away=f_a
    )
    
