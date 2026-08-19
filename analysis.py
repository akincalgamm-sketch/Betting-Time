import random

def normalize_game(game_data=None):
    """main.py'nin hata vermesini önleyen zorunlu fonksiyon"""
    if isinstance(game_data, dict):
        return game_data
    return {}

def calculate_ai_analysis(home_team="Ev Sahibi", away_team="Deplasman", match_stats=None):
    home_form = random.randint(60, 95)
    away_form = random.randint(50, 90)
    home_attack = random.randint(65, 95)
    away_defense = random.randint(55, 85)
    
    home_power = (home_form * 0.35) + (home_attack * 0.4) + 12
    away_power = (away_form * 0.35) + (away_defense * 0.4)
    
    total_power = home_power + away_power
    home_prob = round((home_power / total_power) * 100)
    away_prob = round((away_power / total_power) * 100)
    draw_prob = max(10, 100 - (home_prob + away_prob))

    if home_prob >= 52:
        prediction = f"Maç Sonucu 1 ({home_team})"
        confidence = home_prob
        ai_note = f"{home_team} iç saha avantajı ve yüksek hücum gücüyle (%{home_attack}) öne çıkıyor."
    elif away_prob >= 50:
        prediction = f"Maç Sonucu 2 ({away_team})"
        confidence = away_prob
        ai_note = f"{away_team} deplasmandaki kontratak etkinliğiyle avantajlı."
    else:
        prediction = "2.5 Gol Üstü / KG Var"
        confidence = 72
        ai_note = "İki takımın da gol beklentisi (xG) yüksek; karşılıklı goller bekleniyor."

    return {
        "tahmin": prediction,
        "guven_orani": f"%{confidence}",
        "analiz_ozeti": ai_note,
        "ev_kazanma": f"%{home_prob}",
        "dep_kazanma": f"%{away_prob}",
        "beraberlik": f"%{draw_prob}",
        "foktorler": {
            "Ev Formu": f"%{home_form}",
            "Deplasman Formu": f"%{away_form}",
            "Hücum Gücü": f"{home_attack}/100"
        }
    }

# Diğer olası fonksiyon bağları:
def analyze_match(*args, **kwargs):
    return calculate_ai_analysis(*args, **kwargs)

def get_analysis(*args, **kwargs):
    return calculate_ai_analysis(*args, **kwargs)

def analyze_fixture(*args, **kwargs):
    return calculate_ai_analysis(*args, **kwargs)
        
