import os, json, requests
from datetime import datetime, timedelta
from pathlib import Path
from itertools import combinations
from bs4 import BeautifulSoup

# ---------------- Config ----------------
start_year, end_year = 2013, 2025
replacement_values = {0: 5, 1: 9, 2: 8, 3: 7, 4: 6, 5: 0, 6: 4, 7: 3, 8: 2, 9: 1}

state_games = {
    "Florida": "florida",
    "Chicago": "illinois",
}

BASE_URL = "https://www.lottery.net"
IL_DATA_FILE = Path("illinois_draws.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# ---------------- Alerts ----------------
alerts = []

def display_alerts(play_date, game_name, candidate, result=None, action="play"):
    """Collect alerts for backend + GitHub Actions + Firebase."""
    if action == "win":
        msg = f"🏆 WIN ALERT — Date: {play_date}, Game: {game_name}, Candidate: {candidate}"
    elif action == "stop":
        msg = f"⛔ STOP PLAY — Date: {play_date}, Game: {game_name}, Candidate: {candidate}"
    else:
        msg = f"🎯 PLAY TRIGGERED — Date: {play_date}, Game: {game_name}, Candidate: {candidate}"
        if result:
            msg += f", Result: {result}"

    print(msg)
    alerts.append(msg)

# ---------------- Helpers ----------------
def toggle_state(state: str) -> str:
    return "off" if state == "on" else "on"

def parse_base_date(month: str, day: str, year: str) -> tuple[str, datetime]:
    base_str = f"{month} {day}, {year}"
    dt = datetime.strptime(base_str, "%B %d, %Y")
    return base_str, dt

# ---------------- Illinois JSON Helpers ----------------
def clean_il_data(data: dict) -> dict:
    cleaned = {}
    for game, dates in (data or {}).items():
        pick = 3 if "3" in game else 4
        cleaned[game] = {}
        for date, draws in (dates or {}).items():
            valid_draws = {}
            if not isinstance(draws, dict):
                continue
            for draw_type, numbers in draws.items():
                if isinstance(numbers, list):
                    nums = [n for n in numbers if isinstance(n, int)]
                    if len(nums) == pick:
                        valid_draws[draw_type] = nums
            if valid_draws:
                cleaned[game][date] = valid_draws
        cleaned[game] = dict(sorted(cleaned[game].items()))
    return cleaned

def load_il_data() -> dict:
    if os.path.exists(IL_DATA_FILE):
        with open(IL_DATA_FILE, "r") as f:
            try:
                data = json.load(f)
            except:
                data = {}
    else:
        data = {}
    return clean_il_data(data)

def save_il_data(data: dict):
    cleaned = clean_il_data(data)
    with open(IL_DATA_FILE, "w") as f:
        json.dump(cleaned, f, indent=2)

# ---------------- Illinois Fetching ----------------
def fetch_il_draw(date: str, draw_type: str, pick: int):
    url = f"{BASE_URL}/illinois/pick-{pick}-{draw_type}/numbers/{date}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 404:
            return None
        res.raise_for_status()

        soup = BeautifulSoup(res.text, "html.parser")
        balls = soup.select(f"ul.illinois.results.pick-{pick}-{draw_type} li.ball")
        numbers = [int(n.text.strip()) for n in balls if n.text.strip().isdigit()]

        if len(numbers) == pick:
            return numbers
        return None

    except Exception:
        return None

def update_il_data_to_current():
    data = load_il_data()
    today = datetime.today()
    date = datetime(2022, 10, 9)

    while date <= today:
        date_str = date.strftime("%m-%d-%Y")
        for pick in (3, 4):
            game_key = f"pick{pick}"
            data.setdefault(game_key, {})
            data[game_key].setdefault(date_str, {})

            for draw_type in ("midday", "evening"):
                if draw_type not in data[game_key][date_str]:
                    numbers = fetch_il_draw(date_str, draw_type, pick)
                    if numbers:
                        data[game_key][date_str][draw_type] = numbers
                        save_il_data(data)
        date += timedelta(days=1)

    save_il_data(data)
    return data

def fetch_draws_il(draw_type="evening", pick=3):
    data = update_il_data_to_current()
    draws = []
    game_key = f"pick{pick}"

    if game_key not in data:
        return []

    for date_str, draws_dict in sorted(data[game_key].items()):
        if draw_type not in draws_dict:
            continue
        dt = datetime.strptime(date_str, "%m-%d-%Y")

        numbers = draws_dict[draw_type]
        if len(numbers) != pick:
            continue

        draws.append({
            "dt": dt,
            "date_str": f"{dt.strftime('%B %d, %Y')} ({draw_type})",
            "slot": draw_type,
            "numbers": numbers
        })
    return draws

# ---------------- Generic Fetch ----------------
def fetch_draws(state: str, draw_type: str, pick: int = 3) -> list[dict]:
    if state == "Chicago":
        return fetch_draws_il(draw_type, pick)

    out = []
    state_url = state_games[state]

    for yr in range(start_year, end_year + 1):
        url = f"{BASE_URL}/{state_url}/pick-{pick}-{draw_type}/numbers/{yr}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")

        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 2:
                continue

            parts = tds[0].text.strip().split()
            if len(parts) < 4:
                continue

            month, day, year = parts[1], parts[2].rstrip(","), parts[3]
            base_date_str, dt = parse_base_date(month, day, year)

            raw = tds[1].get_text(separator=" ").strip()
            digits = [int(x) for x in raw.split() if x.isdigit()]
            if len(digits) < pick:
                continue

            numbers = digits[:pick]
            out.append({
                "dt": dt,
                "date_str": f"{base_date_str} ({draw_type})",
                "slot": draw_type,
                "numbers": numbers
            })

    out.sort(key=lambda r: r["dt"])
    return out

# ---------------- Analysis ----------------
def run_lotto_analysis():
    """
    Main function called by GitHub Actions → generate_alerts.py → Firebase.
    Must return a simple list of strings.
    """
    global alerts
    alerts = []

    for state in state_games.keys():
        alerts.append(f"================= {state.upper()} =================")

        midday_draws = fetch_draws(state, "midday", pick=3)
        evening_draws = fetch_draws(state, "evening", pick=3)
        merged_history = sorted(midday_draws + evening_draws, key=lambda r: r["dt"])

        pick4_mid = fetch_draws(state, "midday", pick=4)
        pick4_eve = fetch_draws(state, "evening", pick=4)
        pick4_history = sorted(pick4_mid + pick4_eve, key=lambda r: r["dt"])

        # Simple placeholder analysis
        if merged_history:
            latest = merged_history[-1]
            candidate = latest["numbers"][-1]
            display_alerts(latest["date_str"], state, candidate, action="play")

    return alerts
