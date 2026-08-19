"""
Futbol ve basketbol verisini ortak bir formata indirger ve 7 faktöre dayanan
şeffaf, ağırlıklı bir "model tahmini" üretir. Bahis oranı verisi bulunursa
piyasa ima edilen olasılığıyla harmanlayıp nihai bir tahmin de sunar.

Faktörler (ağırlıkları): genel form, ev/deplasman özel form, head-to-head,
lig sıralaması, gol/sayı averaj farkı, dinlenme günü farkı, sakatlık/eksik
oyuncu (sadece futbol). Bir faktör için veri yoksa o faktör atlanır ve
ağırlığı kalan faktörlere otomatik dağıtılır — yani eksik veri "varmış gibi"
davranılmaz.

NOT: Bu, gerçek bir makine öğrenmesi modeli değildir. Şeffaf, elle
tanımlanmış ağırlıklarla çalışan istatistiksel bir tahmindir; kesinlik
taşımaz.
"""
from dataclasses import dataclass
from datetime import datetime


# ---------------------------------------------------------------------------
# Ortak veri modeli
# ---------------------------------------------------------------------------

@dataclass
class NormalizedGame:
    id: int
    date: str
    home_id: int
    home_name: str
    away_id: int
    away_name: str
    home_score: int | None
    away_score: int | None
    status_short: str
    league_id: int | None = None
    season: object = None


def normalize_game(sport: str, game: dict) -> NormalizedGame:
    if sport == "futbol":
        teams = game["teams"]
        goals = game.get("goals", {})
        fixture = game["fixture"]
        league = game.get("league", {})
        return NormalizedGame(
            id=fixture["id"],
            date=fixture["date"],
            home_id=teams["home"]["id"],
            home_name=teams["home"]["name"],
            away_id=teams["away"]["id"],
            away_name=teams["away"]["name"],
            home_score=goals.get("home"),
            away_score=goals.get("away"),
            status_short=fixture["status"]["short"],
            league_id=league.get("id"),
            season=league.get("season"),
        )
    elif sport == "basketbol":
        teams = game["teams"]
        scores = game.get("scores", {})
        league = game.get("league", {})
        return NormalizedGame(
            id=game["id"],
            date=game["date"],
            home_id=teams["home"]["id"],
            home_name=teams["home"]["name"],
            away_id=teams["away"]["id"],
            away_name=teams["away"]["name"],
            home_score=(scores.get("home") or {}).get("total"),
            away_score=(scores.get("away") or {}).get("total"),
            status_short=game["status"]["short"],
            league_id=league.get("id"),
            season=league.get("season"),
        )
    raise ValueError(f"Bilinmeyen spor: {sport}")


# ---------------------------------------------------------------------------
# Form hesaplama
# ---------------------------------------------------------------------------

@dataclass
class TeamForm:
    wins: int = 0
    draws: int = 0
    losses: int = 0
    scored_total: int = 0
    conceded_total: int = 0
    games_counted: int = 0
    form_string: str = ""  # "GBMGG" -> G=galibiyet, B=beraberlik, M=mağlubiyet, en yeni solda

    @property
    def avg_scored(self) -> float:
        return round(self.scored_total / self.games_counted, 1) if self.games_counted else 0.0

    @property
    def avg_conceded(self) -> float:
        return round(self.conceded_total / self.games_counted, 1) if self.games_counted else 0.0

    @property
    def points(self) -> int:
        return self.wins * 3 + self.draws  # galibiyet 3, beraberlik 1


def compute_form(sport: str, games: list[dict], team_id: int) -> TeamForm:
    form = TeamForm()
    for raw in games:
        g = normalize_game(sport, raw)
        if g.status_short not in ("FT", "AOT", "AET", "PEN"):
            continue
        if g.home_score is None or g.away_score is None:
            continue

        is_home = g.home_id == team_id
        team_score = g.home_score if is_home else g.away_score
        opp_score = g.away_score if is_home else g.home_score

        form.scored_total += team_score
        form.conceded_total += opp_score
        form.games_counted += 1

        if team_score > opp_score:
            form.wins += 1
            form.form_string += "G"
        elif team_score == opp_score:
            form.draws += 1
            form.form_string += "B"
        else:
            form.losses += 1
            form.form_string += "M"

    return form


def most_recent_completed_date(sport: str, games: list[dict]) -> str | None:
    for raw in games:
        g = normalize_game(sport, raw)
        if g.status_short in ("FT", "AOT", "AET", "PEN"):
            return g.date
    return None


# ---------------------------------------------------------------------------
# Yardımcı: sıralama gücü, dinlenme günü, oran, sakatlık -> [-1, 1] faktör
# ---------------------------------------------------------------------------

def _clip(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def standing_strength(standings_flat: list[dict], team_id: int) -> float | None:
    entry = next((e for e in standings_flat if e["team_id"] == team_id), None)
    if not entry or not entry.get("rank") or not entry.get("total_teams") or entry["total_teams"] < 2:
        return None
    rank = entry["rank"]
    total = entry["total_teams"]
    return 1 - (rank - 1) / (total - 1)  # 1 = en iyi, 0 = en kötü


def rest_days(fixture_date_iso: str, last_game_date_iso: str | None) -> int | None:
    if not last_game_date_iso:
        return None
    try:
        fixture_dt = datetime.fromisoformat(fixture_date_iso.replace("Z", "+00:00"))
        last_dt = datetime.fromisoformat(last_game_date_iso.replace("Z", "+00:00"))
        return max(0, (fixture_dt - last_dt).days)
    except Exception:
        return None


def odds_implied_probs(odds_values: dict | None) -> dict | None:
    """odds_values örn: {'home': 1.8, 'draw': 3.4, 'away': 4.2} (decimal oran).
    Bookmaker kâr payını (overround) normalize ederek gerçek olasılığa çevirir."""
    if not odds_values:
        return None
    keys = [k for k in ("home", "draw", "away") if k in odds_values and odds_values[k] > 0]
    if "home" not in keys or "away" not in keys:
        return None
    inv = {k: 1.0 / odds_values[k] for k in keys}
    total_inv = sum(inv.values())
    if total_inv <= 0:
        return None
    return {k: round((v / total_inv) * 100) for k, v in inv.items()}


# ---------------------------------------------------------------------------
# Ana model: faktörleri topla, ağırlıklandır, tahmin üret
# ---------------------------------------------------------------------------

FACTOR_WEIGHTS = {
    "form": 0.15,
    "venue_form": 0.20,
    "h2h": 0.10,
    "standing": 0.20,
    "goal_diff": 0.20,
    "rest": 0.05,
    "injuries": 0.10,
}

HOME_ADVANTAGE_BONUS = 0.05  # ayrı, sabit küçük bir ev sahibi avantajı


@dataclass
class PredictionResult:
    model_home: int
    model_draw: int
    model_away: int
    market_home: int | None
    market_draw: int | None
    market_away: int | None
    final_home: int
    final_draw: int
    final_away: int
    breakdown: list[tuple[str, float | None]]  # (faktör adı, [-1,1] değer ya da None)


def _factor_label(name: str, value: float | None, home_name: str, away_name: str) -> str:
    if value is None:
        return f"• {name}: veri yok (atlandı)"
    if value > 0.15:
        return f"• {name}: {home_name} lehine"
    if value < -0.15:
        return f"• {name}: {away_name} lehine"
    return f"• {name}: dengeli"


def build_prediction(
    sport: str,
    home_form: TeamForm,
    away_form: TeamForm,
    home_venue_form: TeamForm,
    away_venue_form: TeamForm,
    h2h_games: list[dict],
    home_id: int,
    away_id: int,
    home_standing_strength: float | None,
    away_standing_strength: float | None,
    home_rest: int | None,
    away_rest: int | None,
    home_injuries: int | None,
    away_injuries: int | None,
    odds_values: dict | None,
    home_name: str,
    away_name: str,
) -> PredictionResult:
    factors: dict[str, float | None] = {}

    # 1) genel form
    factors["form"] = _clip((home_form.points - away_form.points) / 15) if (
        home_form.games_counted and away_form.games_counted
    ) else None

    # 2) ev/deplasman özel form
    factors["venue_form"] = _clip((home_venue_form.points - away_venue_form.points) / 15) if (
        home_venue_form.games_counted and away_venue_form.games_counted
    ) else None

    # 3) head-to-head
    h2h_home_wins = h2h_away_wins = h2h_total = 0
    for raw in h2h_games:
        g = normalize_game(sport, raw)
        if g.home_score is None or g.away_score is None:
            continue
        h2h_total += 1
        winner_id = g.home_id if g.home_score > g.away_score else (g.away_id if g.away_score > g.home_score else None)
        if winner_id == home_id:
            h2h_home_wins += 1
        elif winner_id == away_id:
            h2h_away_wins += 1
    factors["h2h"] = _clip((h2h_home_wins - h2h_away_wins) / h2h_total) if h2h_total else None

    # 4) lig sıralaması
    if home_standing_strength is not None and away_standing_strength is not None:
        factors["standing"] = _clip((home_standing_strength - away_standing_strength) * 2)
    else:
        factors["standing"] = None

    # 5) gol/sayı averaj farkı
    if home_form.games_counted and away_form.games_counted:
        home_gd = home_form.avg_scored - home_form.avg_conceded
        away_gd = away_form.avg_scored - away_form.avg_conceded
        factors["goal_diff"] = _clip((home_gd - away_gd) / 4)
    else:
        factors["goal_diff"] = None

    # 6) dinlenme günü farkı
    if home_rest is not None and away_rest is not None:
        factors["rest"] = _clip((home_rest - away_rest) / 10, -0.3, 0.3)
    else:
        factors["rest"] = None

    # 7) sakatlık/eksik oyuncu (sadece futbol, veri varsa)
    if home_injuries is not None and away_injuries is not None:
        factors["injuries"] = _clip((away_injuries - home_injuries) / 6)
    else:
        factors["injuries"] = None

    # ağırlıklı ortalama (eksik faktörler otomatik dışlanır, ağırlık kalanlara dağılır)
    weighted_sum = 0.0
    weight_total = 0.0
    for name, value in factors.items():
        if value is None:
            continue
        w = FACTOR_WEIGHTS[name]
        weighted_sum += w * value
        weight_total += w

    final_diff = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    final_diff = _clip(final_diff + HOME_ADVANTAGE_BONUS, -0.9, 0.9)

    if sport == "futbol":
        base_draw = _clip(24 - abs(final_diff) * 15, 8, 30)
        remaining = 100 - base_draw
        model_home = round(remaining * (0.5 + final_diff / 2))
        model_away = round(remaining - model_home)
        model_draw = round(100 - model_home - model_away)
    else:
        model_home = round(50 + final_diff * 45)
        model_home = max(5, min(95, model_home))
        model_away = 100 - model_home
        model_draw = 0

    # piyasa oranlarıyla harmanlama
    market = odds_implied_probs(odds_values)
    if market:
        market_home = market.get("home")
        market_away = market.get("away")
        market_draw = market.get("draw", 0) if sport == "futbol" else None

        final_home = round(model_home * 0.5 + market_home * 0.5)
        final_away = round(model_away * 0.5 + market_away * 0.5)
        if sport == "futbol":
            final_draw = 100 - final_home - final_away
        else:
            final_draw = 0
            diff = 100 - final_home - final_away
            final_home += diff
    else:
        market_home = market_draw = market_away = None
        final_home, final_draw, final_away = model_home, model_draw, model_away

    breakdown = [
        ("Genel form (son 5 maç)", factors["form"]),
        ("Ev/deplasman özel form", factors["venue_form"]),
        ("Head-to-head geçmişi", factors["h2h"]),
        ("Lig sıralaması", factors["standing"]),
        ("Gol/sayı averaj farkı", factors["goal_diff"]),
        ("Dinlenme günü farkı", factors["rest"]),
        ("Sakatlık/eksik oyuncu", factors["injuries"]),
    ]

    return PredictionResult(
        model_home=model_home, model_draw=model_draw, model_away=model_away,
        market_home=market_home, market_draw=market_draw, market_away=market_away,
        final_home=final_home, final_draw=final_draw, final_away=final_away,
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Mesaj formatlama
# ---------------------------------------------------------------------------

def format_analysis_message(
    sport: str,
    home_name: str,
    away_name: str,
    home_form: TeamForm,
    away_form: TeamForm,
    h2h_games: list[dict],
    result: PredictionResult,
) -> str:
    lines = []
    lines.append(f"⚽️🏀 <b>{home_name} vs {away_name}</b>")
    lines.append(f"<i>Spor: {sport.capitalize()}</i>\n")

    lines.append("📊 <b>Son Form</b> (en yeni → en eski)")
    lines.append(
        f"🏠 {home_name}: {home_form.form_string or '—'} "
        f"({home_form.wins}G {home_form.draws}B {home_form.losses}M) "
        f"| Ort. attığı: {home_form.avg_scored} — yediği: {home_form.avg_conceded}"
    )
    lines.append(
        f"🚗 {away_name}: {away_form.form_string or '—'} "
        f"({away_form.wins}G {away_form.draws}B {away_form.losses}M) "
        f"| Ort. attığı: {away_form.avg_scored} — yediği: {away_form.avg_conceded}"
    )

    lines.append("\n🤝 <b>Head-to-Head (son karşılaşmalar)</b>")
    if h2h_games:
        shown = 0
        for raw in h2h_games:
            g = normalize_game(sport, raw)
            if g.home_score is None:
                continue
            d = g.date[:10]
            lines.append(f"• {d}: {g.home_name} {g.home_score}-{g.away_score} {g.away_name}")
            shown += 1
            if shown >= 5:
                break
        if shown == 0:
            lines.append("• Geçmiş karşılaşma verisi bulunamadı.")
    else:
        lines.append("• Geçmiş karşılaşma verisi bulunamadı.")

    lines.append("\n🧩 <b>Faktör Analizi</b>")
    for name, value in result.breakdown:
        lines.append(_factor_label(name, value, home_name, away_name))

    lines.append("\n🔮 <b>Model Tahmini</b> (yukarıdaki faktörlerden)")
    if sport == "futbol":
        lines.append(
            f"🏠 {home_name}: %{result.model_home}  🤝 Beraberlik: %{result.model_draw}  🚗 {away_name}: %{result.model_away}"
        )
    else:
        lines.append(f"🏠 {home_name}: %{result.model_home}  🚗 {away_name}: %{result.model_away}")

    if result.market_home is not None:
        lines.append("\n💰 <b>Piyasa Oranı İma Ettiği Olasılık</b>")
        if sport == "futbol":
            lines.append(
                f"🏠 {home_name}: %{result.market_home}  🤝 Beraberlik: %{result.market_draw}  🚗 {away_name}: %{result.market_away}"
            )
        else:
            lines.append(f"🏠 {home_name}: %{result.market_home}  🚗 {away_name}: %{result.market_away}")

        lines.append("\n✅ <b>Nihai Tahmin</b> (model + piyasa harmanlanmış)")
        if sport == "futbol":
            lines.append(
                f"🏠 {home_name}: %{result.final_home}  🤝 Beraberlik: %{result.final_draw}  🚗 {away_name}: %{result.final_away}"
            )
        else:
            lines.append(f"🏠 {home_name}: %{result.final_home}  🚗 {away_name}: %{result.final_away}")
    else:
        lines.append("\n<i>💰 Bu maç için bahis oranı verisi bulunamadı, nihai tahmin = model tahmini.</i>")

    lines.append(
        "\n<i>⚠️ Bu tahmin; form, sıralama, averaj, dinlenme ve (varsa) sakatlık/oran "
        "verilerine dayanan şeffaf bir istatistiksel değerlendirmedir. Kesin sonuç "
        "garantisi taşımaz, bahis tavsiyesi değildir.</i>"
    )
    return "\n".join(lines)
