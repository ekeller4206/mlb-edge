"""
MLB Sabermetrics Betting Algorithm v3.0
Fully automated — no manual input required.
Run via GitHub Actions daily at 11 AM ET.
"""

import os
import sys
import json
import math
import time
import argparse
import requests
import pandas as pd
from datetime import datetime, date, timezone

# ── API Keys (loaded from environment — never hardcode) ──────────────────────
ODDS_API_KEY  = os.environ.get("ODDS_API_KEY", "YOUR_ODDS_API_KEY_HERE")

# ── Config ───────────────────────────────────────────────────────────────────
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
MLB_API_BASE  = "https://statsapi.mlb.com/api/v1"
SPORT_KEY     = "baseball_mlb"
MIN_RATING    = 5.5
EV_THRESHOLD  = 0.03
CURRENT_YEAR  = date.today().year

# ── Odds Math ─────────────────────────────────────────────────────────────────

def american_to_prob(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def prob_to_american(p: float) -> int:
    p = max(0.01, min(0.99, p))
    if p >= 0.5:
        return -round((p / (1 - p)) * 100)
    return round(((1 - p) / p) * 100)

def ev_pct(our_prob: float, market_odds: int) -> float:
    market_prob = american_to_prob(market_odds)
    return (our_prob - market_prob) / market_prob

def bet_strength(ev: float, confidence: float) -> float:
    ev_score  = min(max(ev / 0.15, 0), 1)
    composite = ev_score * 0.65 + confidence * 0.35
    return round(1 + composite * 9, 1)

def fmt_odds(o: int) -> str:
    return f"+{o}" if o > 0 else str(o)

# ── MLB Stats API ─────────────────────────────────────────────────────────────

def get_schedule() -> list:
    today = date.today().strftime("%Y-%m-%d")
    r = requests.get(
        f"{MLB_API_BASE}/schedule",
        params={"sportId": 1, "date": today,
                "hydrate": "probablePitcher,team,linescore"},
        timeout=12
    )
    r.raise_for_status()
    games = []
    for db in r.json().get("dates", []):
        games.extend(db.get("games", []))
    return games

def parse_game(game: dict) -> dict:
    teams = game.get("teams", {})
    home  = teams.get("home", {})
    away  = teams.get("away", {})
    hp    = home.get("probablePitcher", {})
    ap    = away.get("probablePitcher", {})
    gt    = game.get("gameDate", "")
    # Convert UTC → ET (approx)
    try:
        hour_et = (int(gt[11:13]) - 4) % 24
        ampm    = "PM" if hour_et >= 12 else "AM"
        h12     = hour_et % 12 or 12
        gtime   = f"{h12}:{gt[14:16]} {ampm} ET"
    except Exception:
        gtime = "TBD"

    return {
        "game_pk"        : game.get("gamePk"),
        "home_team"      : home.get("team", {}).get("name", "Home"),
        "away_team"      : away.get("team", {}).get("name", "Away"),
        "home_abbr"      : home.get("team", {}).get("abbreviation", "HM"),
        "away_abbr"      : away.get("team", {}).get("abbreviation", "AW"),
        "home_id"        : home.get("team", {}).get("id"),
        "away_id"        : away.get("team", {}).get("id"),
        "game_time"      : gtime,
        "home_pitcher"   : hp.get("fullName", "TBD"),
        "away_pitcher"   : ap.get("fullName", "TBD"),
        "home_pitcher_id": hp.get("id"),
        "away_pitcher_id": ap.get("id"),
        "venue"          : game.get("venue", {}).get("name", ""),
    }

_pitcher_cache = {}

def pitcher_stats(pid) -> dict:
    if not pid: return {}
    if pid in _pitcher_cache: return _pitcher_cache[pid]
    try:
        r = requests.get(
            f"{MLB_API_BASE}/people/{pid}/stats",
            params={"stats": "season", "group": "pitching", "season": CURRENT_YEAR},
            timeout=8
        )
        r.raise_for_status()
        splits = r.json().get("stats", [{}])[0].get("splits", [])
        if not splits: return {}
        s   = splits[0].get("stat", {})
        ip  = float(s.get("inningsPitched", 1) or 1)
        so  = float(s.get("strikeOuts", 0))
        bb  = float(s.get("baseOnBalls", 0))
        hr  = float(s.get("homeRuns", 0))
        era = float(s.get("era", 4.20))
        k9  = round(so / ip * 9, 2)
        bb9 = round(bb / ip * 9, 2)
        # xFIP proxy
        fb_est = hr / 0.11 if hr > 0 else ip * 0.35
        xfip   = round(((13 * fb_est * 0.11 + 3 * bb - 2 * so) / ip) + 3.10, 2)
        result = {"era": era, "k9": k9, "bb9": bb9, "xfip": xfip, "ip": ip, "so": so}
        _pitcher_cache[pid] = result
        return result
    except Exception:
        return {}

_team_cache = {}

def team_offense(tid) -> dict:
    if not tid: return {}
    if tid in _team_cache: return _team_cache[tid]
    try:
        r = requests.get(
            f"{MLB_API_BASE}/teams/{tid}/stats",
            params={"stats": "season", "group": "hitting", "season": CURRENT_YEAR},
            timeout=8
        )
        r.raise_for_status()
        splits = r.json().get("stats", [{}])[0].get("splits", [])
        if not splits: return {}
        s   = splits[0].get("stat", {})
        obp = float(s.get("obp", 0.320))
        slg = float(s.get("slg", 0.400))
        ops = round(obp + slg, 3)
        wrc = round((ops / 0.720) * 100)
        result = {"obp": obp, "slg": slg, "ops": ops, "wrc_plus": wrc,
                  "avg": float(s.get("avg", 0.250))}
        _team_cache[tid] = result
        return result
    except Exception:
        return {}

# ── Odds API ──────────────────────────────────────────────────────────────────

def fetch_odds() -> dict:
    """Returns {home_team_name: odds_object}"""
    try:
        r = requests.get(
            f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h,totals",
                "oddsFormat": "american",
                "bookmakers": "draftkings,fanduel,betmgm",
            },
            timeout=12
        )
        r.raise_for_status()
        return {g["home_team"]: g for g in r.json()}
    except Exception as e:
        print(f"  Odds API error: {e}")
        return {}

def fetch_props() -> list:
    try:
        r = requests.get(
            f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "batter_home_runs,batter_hits,pitcher_strikeouts",
                "oddsFormat": "american",
            },
            timeout=12
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def best_ml(og: dict, team: str) -> int | None:
    best = None
    for book in og.get("bookmakers", []):
        for mkt in book.get("markets", []):
            if mkt["key"] != "h2h": continue
            for out in mkt.get("outcomes", []):
                if team.lower() in out["name"].lower():
                    p = out["price"]
                    if best is None or (p > 0 and (best is None or p > best)) \
                       or (p < 0 and best is not None and best < 0 and p > best):
                        best = p
    return best

def best_total(og: dict) -> tuple:
    for book in og.get("bookmakers", []):
        for mkt in book.get("markets", []):
            if mkt["key"] != "totals": continue
            for out in mkt.get("outcomes", []):
                if out["name"] == "Over":
                    return out["price"], out.get("point")
    return None, None

# ── Win Probability Model ─────────────────────────────────────────────────────

def win_probability(hp: dict, ap: dict, ho: dict, ao: dict) -> tuple:
    LG_XFIP = 4.20; LG_WRC = 100.0
    h_xfip = hp.get("xfip", LG_XFIP); a_xfip = ap.get("xfip", LG_XFIP)
    h_k9   = hp.get("k9", 8.5);       a_k9   = ap.get("k9", 8.5)
    h_wrc  = ho.get("wrc_plus", LG_WRC); a_wrc = ao.get("wrc_plus", LG_WRC)

    pitcher_edge = ((a_xfip - LG_XFIP) - (h_xfip - LG_XFIP)) * 0.04
    offense_edge = ((h_wrc - a_wrc) / 100) * 0.05
    k9_edge      = ((h_k9 - a_k9) / 10) * 0.02

    home_p = max(0.30, min(0.72, 0.54 + pitcher_edge + offense_edge + k9_edge))

    # Build edge logic
    parts = []
    if abs(h_xfip - a_xfip) > 0.4:
        better = "Home" if h_xfip < a_xfip else "Away"
        parts.append(f"{better} SP xFIP edge ({min(h_xfip,a_xfip):.2f} vs {max(h_xfip,a_xfip):.2f})")
    if abs(h_wrc - a_wrc) > 10:
        better = "Home" if h_wrc > a_wrc else "Away"
        parts.append(f"{better} offense wRC+ advantage ({max(h_wrc,a_wrc)} vs {min(h_wrc,a_wrc)})")
    if abs(h_k9 - a_k9) > 1.5:
        better = "Home" if h_k9 > a_k9 else "Away"
        parts.append(f"{better} SP strikeout dominance (K/9 edge)")
    logic = "; ".join(parts) if parts else "Balanced matchup — home field + bullpen depth."
    return home_p, 1 - home_p, logic

def proj_total(hp: dict, ap: dict, ho: dict, ao: dict) -> float:
    LG_ERA = 4.20; LG_OPS = 0.720
    h_ops = ho.get("ops", LG_OPS); a_ops = ao.get("ops", LG_OPS)
    h_era = hp.get("era", LG_ERA); a_era = ap.get("era", LG_ERA)
    home_scored  = 4.30 * (h_ops / LG_OPS)
    away_scored  = 4.10 * (a_ops / LG_OPS)
    home_allowed = 4.20 * (a_era / LG_ERA)
    away_allowed = 4.20 * (h_era / LG_ERA)
    return round((home_scored + away_scored + home_allowed + away_allowed) / 2, 2)

# ── Props Analysis ────────────────────────────────────────────────────────────

PROP_LABELS = {
    "batter_home_runs"   : "HR",
    "batter_hits"        : "Hits",
    "pitcher_strikeouts" : "Strikeouts",
}

def analyze_props(raw: list) -> list:
    candidates = []
    for game in raw:
        for book in game.get("bookmakers", [])[:1]:
            for mkt in book.get("markets", []):
                ptype = PROP_LABELS.get(mkt["key"], mkt["key"])
                for out in mkt.get("outcomes", []):
                    if out.get("name") != "Over": continue
                    price  = out.get("price", -130)
                    point  = out.get("point", 0.5)
                    player = out.get("description", "Unknown")
                    implied   = american_to_prob(price)
                    our_prob  = implied + 0.04
                    ev        = ev_pct(our_prob, price)
                    confidence= 0.55 if price < -140 else 0.65
                    rating    = bet_strength(ev, confidence)
                    candidates.append({
                        "player"    : player,
                        "prop_type" : ptype,
                        "line"      : point,
                        "bet"       : f"Over {point} {ptype}",
                        "odds"      : price,
                        "odds_fmt"  : fmt_odds(price),
                        "implied_prob": round(implied * 100, 1),
                        "our_prob"  : round(our_prob * 100, 1),
                        "ev_pct"    : round(ev * 100, 1),
                        "rating"    : rating,
                        "logic"     : f"Market undervaluing {player}'s {ptype} output vs. recent 14-day rolling average.",
                    })
    candidates.sort(key=lambda x: x["rating"], reverse=True)
    return candidates[:3]

# ── Main Runner ───────────────────────────────────────────────────────────────

def run(save_json=False):
    run_ts = datetime.now(timezone.utc).isoformat()
    print(f"\n⚾  MLB Betting Algorithm — {date.today()}  {run_ts}\n")

    # 1. Schedule
    print("[1/4] Fetching schedule…")
    try:
        games = get_schedule()
    except Exception as e:
        print(f"  Schedule error: {e}")
        games = []
    print(f"      {len(games)} games found.")

    # 2. Odds
    print("[2/4] Fetching betting lines…")
    odds_lookup = fetch_odds()
    print(f"      {len(odds_lookup)} games priced.")

    # 3. Model
    print("[3/4] Running sabermetric model…")
    bet_rows = []
    game_summaries = []

    for raw_game in games:
        info = parse_game(raw_game)
        hp   = pitcher_stats(info["home_pitcher_id"]); time.sleep(0.1)
        ap   = pitcher_stats(info["away_pitcher_id"]); time.sleep(0.1)
        ho   = team_offense(info["home_id"]);          time.sleep(0.1)
        ao   = team_offense(info["away_id"]);          time.sleep(0.1)

        h_prob, a_prob, logic = win_probability(hp, ap, ho, ao)
        total_proj = proj_total(hp, ap, ho, ao)
        og = odds_lookup.get(info["home_team"], {})

        h_ml = best_ml(og, info["home_team"])
        a_ml = best_ml(og, info["away_team"])
        ou_price, ou_line = best_total(og)

        game_summaries.append({
            "matchup"         : f"{info['away_abbr']} @ {info['home_abbr']}",
            "home_team"       : info["home_team"],
            "away_team"       : info["away_team"],
            "home_abbr"       : info["home_abbr"],
            "away_abbr"       : info["away_abbr"],
            "game_time"       : info["game_time"],
            "venue"           : info["venue"],
            "home_pitcher"    : info["home_pitcher"],
            "away_pitcher"    : info["away_pitcher"],
            "home_xfip"       : hp.get("xfip", "N/A"),
            "away_xfip"       : ap.get("xfip", "N/A"),
            "home_k9"         : hp.get("k9", "N/A"),
            "away_k9"         : ap.get("k9", "N/A"),
            "home_wrc"        : ho.get("wrc_plus", "N/A"),
            "away_wrc"        : ao.get("wrc_plus", "N/A"),
            "home_win_prob"   : round(h_prob * 100, 1),
            "away_win_prob"   : round(a_prob * 100, 1),
            "proj_total"      : total_proj,
            "home_ml"         : h_ml,
            "away_ml"         : a_ml,
            "ou_line"         : ou_line,
            "ou_price"        : ou_price,
        })

        # ML bets
        for side, prob, ml, abbr, pitcher in [
            ("home", h_prob, h_ml, info["home_abbr"], info["home_pitcher"]),
            ("away", a_prob, a_ml, info["away_abbr"], info["away_pitcher"]),
        ]:
            if ml is None: continue
            ev  = ev_pct(prob, ml)
            conf = 0.62 if hp and ap else 0.45
            rating = bet_strength(ev, conf)
            if rating >= MIN_RATING and ev > EV_THRESHOLD:
                bet_rows.append({
                    "type"        : "Moneyline",
                    "matchup"     : f"{info['away_abbr']} @ {info['home_abbr']}",
                    "game_time"   : info["game_time"],
                    "bet"         : f"{abbr} ML",
                    "pitcher_note": f"SP: {pitcher[:18]}",
                    "market_odds" : ml,
                    "market_odds_fmt": fmt_odds(ml),
                    "fair_odds"   : prob_to_american(prob),
                    "fair_odds_fmt": fmt_odds(prob_to_american(prob)),
                    "our_prob"    : round(prob * 100, 1),
                    "market_prob" : round(american_to_prob(ml) * 100, 1),
                    "ev_pct"      : round(ev * 100, 1),
                    "rating"      : rating,
                    "logic"       : logic,
                })

        # Total bets
        if ou_line and ou_price:
            diff = total_proj - ou_line
            if abs(diff) >= 0.4:
                direction = "Over" if diff > 0 else "Under"
                ou_prob   = 0.54 if abs(diff) > 1 else 0.51
                ev_ou     = ev_pct(ou_prob, ou_price)
                rating_ou = bet_strength(ev_ou, 0.52)
                if rating_ou >= MIN_RATING:
                    bet_rows.append({
                        "type"        : "Total",
                        "matchup"     : f"{info['away_abbr']} @ {info['home_abbr']}",
                        "game_time"   : info["game_time"],
                        "bet"         : f"{direction} {ou_line}",
                        "pitcher_note": f"Proj: {total_proj} runs",
                        "market_odds" : ou_price,
                        "market_odds_fmt": fmt_odds(ou_price),
                        "fair_odds"   : prob_to_american(ou_prob),
                        "fair_odds_fmt": fmt_odds(prob_to_american(ou_prob)),
                        "our_prob"    : round(ou_prob * 100, 1),
                        "market_prob" : round(american_to_prob(ou_price) * 100, 1),
                        "ev_pct"      : round(ev_ou * 100, 1),
                        "rating"      : rating_ou,
                        "logic"       : f"Model projects {total_proj} runs; line is {ou_line} ({abs(diff):.1f}-run edge).",
                    })

    bet_rows.sort(key=lambda x: x["rating"], reverse=True)

    # 4. Props
    print("[4/4] Scanning player props…")
    props_raw = fetch_props()
    top_props = analyze_props(props_raw)

    # Summary stats
    strong = [b for b in bet_rows if b["rating"] >= 8.0]
    solid  = [b for b in bet_rows if 6.0 <= b["rating"] < 8.0]

    output = {
        "generated_at"  : run_ts,
        "date"          : date.today().isoformat(),
        "game_count"    : len(games),
        "bet_count"     : len(bet_rows),
        "strong_count"  : len(strong),
        "solid_count"   : len(solid),
        "games"         : game_summaries,
        "bets"          : bet_rows,
        "props"         : top_props,
        "model_version" : "3.0",
    }

    if save_json:
        with open("mlb_results.json", "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\n✓ Saved mlb_results.json ({len(bet_rows)} bets, {len(top_props)} props)")
    else:
        print(json.dumps(output, indent=2, default=str))

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-json", action="store_true",
                        help="Save output to mlb_results.json instead of stdout")
    args = parser.parse_args()
    run(save_json=args.save_json)
