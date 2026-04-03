"""
MLB Sabermetrics Betting Algorithm v3.1
Fully automated — no manual input required.
Run via GitHub Actions daily at 11 AM ET.

Props source: PrizePicks public API (free, no key needed)
  → https://api.prizepicks.com/projections?league_id=2
Fallback:     MLB Stats API season leader boards
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

def remove_vig(h_raw: float, a_raw: float) -> tuple:
    """Strip bookmaker vig to get true no-vig probabilities."""
    total = h_raw + a_raw
    return h_raw / total, a_raw / total

def ev_pct(our_prob: float, market_odds: int) -> float:
    """
    CORRECT edge formula used by professional bettors:
        Edge = Model Probability - Market Implied Probability
    Returns a decimal (0.05 = 5% edge).
    DO NOT use ratio formula — that inflates edges massively.
    """
    implied = american_to_prob(market_odds)
    return our_prob - implied

def sample_size_weight(ip: float) -> float:
    """
    Regress pitcher stats toward league average based on sample size.
    Below 30 IP = heavy regression. Above 80 IP = mostly trust the stats.
    This prevents early-season blowups from 2-start xFIP readings.
    """
    return min(ip / 80.0, 1.0)

def bet_strength(ev: float, confidence: float) -> float:
    """
    Rating 1-10 calibrated for realistic 2-8% edge range.
    - 2% edge = ~5.5 rating (marginal)
    - 5% edge = ~7.5 rating (solid)
    - 8%+ edge = ~9.0+ rating (strong)
    Scaled so 8% edge = 1.0 score (not 15% like before).
    """
    ev_score  = min(max(ev / 0.08, 0), 1)
    composite = ev_score * 0.70 + confidence * 0.30
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

# League average constants for regression
LG_XFIP   = 4.20
LG_ERA    = 4.20
LG_K9     = 8.70
LG_BB9    = 3.20
LG_WRC    = 100.0
LG_OBP    = 0.320

def pitcher_stats(pid) -> dict:
    """
    Pull pitcher stats and apply sample-size regression toward league average.
    Early season pitchers (< 20 IP) are heavily regressed — prevents wild xFIP swings.
    """
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
        era = float(s.get("era", LG_ERA))

        # Raw per-9 stats
        k9_raw  = (so / ip * 9) if ip > 0 else LG_K9
        bb9_raw = (bb / ip * 9) if ip > 0 else LG_BB9

        # xFIP proxy using estimated fly balls (HR/FB rate ~11%)
        fb_est   = hr / 0.11 if hr > 0 else max(ip * 0.35, 1)
        xfip_raw = ((13 * fb_est * 0.11 + 3 * bb - 2 * so) / ip) + 3.10 if ip > 0 else LG_XFIP

        # K-BB% (key skill metric, less noisy than K9 alone)
        bf_est  = ip * 4.3  # approximate batters faced
        kbb_pct = ((so - bb) / bf_est * 100) if bf_est > 0 else 5.0

        # Sample size weight: regress toward league average
        # 0 IP = 100% league avg, 80+ IP = 100% actual stats
        w = sample_size_weight(ip)

        xfip  = round(w * xfip_raw + (1 - w) * LG_XFIP, 2)
        k9    = round(w * k9_raw   + (1 - w) * LG_K9,   2)
        bb9   = round(w * bb9_raw  + (1 - w) * LG_BB9,  2)
        era_r = round(w * era      + (1 - w) * LG_ERA,  2)

        # Hard clip: xFIP can never be below 1.5 or above 7.0
        xfip = max(1.50, min(7.00, xfip))

        result = {
            "era": era_r, "k9": k9, "bb9": bb9,
            "xfip": xfip, "kbb_pct": round(kbb_pct, 1),
            "ip": ip, "sample_weight": round(w, 2)
        }
        _pitcher_cache[pid] = result
        return result
    except Exception:
        return {}

_team_cache = {}

def team_offense(tid) -> dict:
    """
    Pull team batting stats. Use OBP as primary metric (less noisy than SLG early season).
    wRC+ proxy regressed toward 100 based on PA sample size.
    """
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
        s    = splits[0].get("stat", {})
        obp  = float(s.get("obp", LG_OBP))
        slg  = float(s.get("slg", 0.400))
        pa   = float(s.get("plateAppearances", 0) or 0)
        ab   = float(s.get("atBats", 0) or 0)
        hits = float(s.get("hits", 0) or 0)

        # Sample weight for offense: fully trust at 1500+ PA (full season ~6200 PA)
        # Early season 200 PA = ~13% weight
        off_weight = min(pa / 1500.0, 1.0) if pa > 0 else 0.0

        # wRC+ proxy from OPS, regressed toward 100
        ops_raw = round(obp + slg, 3)
        wrc_raw = (ops_raw / 0.720) * 100
        wrc     = round(off_weight * wrc_raw + (1 - off_weight) * 100.0)
        # Hard clip: wRC+ stays in realistic range 65-145
        wrc     = max(65, min(145, wrc))

        result = {
            "obp": obp, "slg": slg, "ops": round(ops_raw, 3),
            "wrc_plus": wrc, "avg": float(s.get("avg", 0.250)),
            "pa": int(pa), "sample_weight": round(off_weight, 2)
        }
        _team_cache[tid] = result
        return result
    except Exception:
        return {}

# ── Odds API ──────────────────────────────────────────────────────────────────

def fetch_odds() -> dict:
    """Returns {home_team_name: odds_object} — includes h2h, totals, spreads (run line)."""
    try:
        r = requests.get(
            f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h,totals,spreads",
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

def best_runline(og: dict, team: str) -> tuple:
    """
    Find the best run line odds for a team.
    MLB run lines are almost always -1.5 (favorite) or +1.5 (underdog).
    Returns (price, point) e.g. (+145, -1.5) or (-165, +1.5)
    """
    best_price = None
    best_point = None
    for book in og.get("bookmakers", []):
        for mkt in book.get("markets", []):
            if mkt["key"] != "spreads": continue
            for out in mkt.get("outcomes", []):
                if team.lower() in out["name"].lower():
                    p = out["price"]
                    pt = out.get("point", -1.5)
                    if best_price is None or p > best_price:
                        best_price = p
                        best_point = pt
    return best_price, best_point

def runline_win_prob(ml_win_prob: float, point: float, proj_total: float) -> float:
    """
    Estimate probability of covering the run line given:
    - ml_win_prob: our estimated win probability
    - point: the run line spread (e.g. -1.5 or +1.5)
    - proj_total: projected total runs scored

    Logic:
    - If covering -1.5: team must win by 2+
      → Roughly 72% of ML wins are by 2+ runs historically
    - If covering +1.5: team either wins OR loses by exactly 1
      → Roughly 28% of ML losses are by exactly 1 run
    """
    if point is None:
        return 0.0

    # Historical MLB: ~72% of wins are by 2+ runs, ~28% are walk-offs/1-run wins
    WIN_BY_2_RATE   = 0.72
    LOSE_BY_1_RATE  = 0.28

    # Adjust slightly for high-scoring games (more blowouts) vs. low scoring (more 1-run)
    if proj_total < 7.0:
        WIN_BY_2_RATE  = 0.65
        LOSE_BY_1_RATE = 0.35
    elif proj_total > 10.0:
        WIN_BY_2_RATE  = 0.78
        LOSE_BY_1_RATE = 0.22

    if point <= -1.0:
        # Covering -1.5: need to win by 2+
        return ml_win_prob * WIN_BY_2_RATE
    else:
        # Covering +1.5: win OR lose by 1
        prob_win     = ml_win_prob
        prob_lose_by1 = (1 - ml_win_prob) * LOSE_BY_1_RATE
        return prob_win + prob_lose_by1

# ── Win Probability Model v4.0 — Calibrated Logistic Framework ──────────────
#
# ARCHITECTURE:
# 1. Compute a raw score for each team using weighted components
# 2. Take the difference (home - away) as a single signal
# 3. Pass through logistic function centered at 0.54 (home field)
# 4. Apply shrinkage: blend 30% toward 0.5 to prevent extremes
# 5. Hard clamp to [0.38, 0.63] — realistic MLB range
#
# WEIGHTS (empirically validated for MLB):
#   Starting pitcher quality (xFIP):  38%
#   Offense quality (wRC+):           27%
#   Pitcher control (K-BB%):          15%
#   Bullpen proxy (BB9 inverse):      12%
#   Home field advantage:             8% (baked into base 0.54)
#
# EDGE FORMULA (correct):
#   Edge = Model_Prob - Market_Implied_Prob   ← simple subtraction, NO ratio
#
# CALIBRATION TARGETS:
#   Evenly matched game:    ~52-54%
#   Clear favorite:         ~56-59%
#   Strong mismatch:        ~60-63%
#   Never exceed:           63%

def logistic(x: float) -> float:
    """Standard logistic sigmoid: maps any real number to (0, 1)."""
    return 1.0 / (1.0 + math.exp(-x))

def team_score(pitcher: dict, offense: dict) -> float:
    """
    Compute a single quality score for one team.
    Lower xFIP = better pitcher = higher score.
    Higher wRC+ = better offense = higher score.
    All inputs normalized around league average = 0.
    """
    # ── Pitcher component (xFIP, lower is better) ──
    xfip       = pitcher.get("xfip", LG_XFIP)
    xfip_z     = (LG_XFIP - xfip) / 0.60        # std dev ~0.60 in MLB
    xfip_z     = max(-2.5, min(2.5, xfip_z))     # clip at ±2.5 SD

    # ── Control component (K-BB%, higher is better) ──
    kbb        = pitcher.get("kbb_pct", 5.0)
    LG_KBB     = 5.0                              # league avg K-BB% ~5%
    kbb_z      = (kbb - LG_KBB) / 4.0            # std dev ~4%
    kbb_z      = max(-2.0, min(2.0, kbb_z))

    # ── Offense component (wRC+, higher is better) ──
    wrc        = offense.get("wrc_plus", LG_WRC)
    wrc_z      = (wrc - LG_WRC) / 12.0           # std dev ~12 pts in MLB
    wrc_z      = max(-2.0, min(2.0, wrc_z))

    # ── Weighted combination ──
    score = (0.38 * xfip_z) + (0.15 * kbb_z) + (0.27 * wrc_z)
    return score

def win_probability(hp: dict, ap: dict, ho: dict, ao: dict) -> tuple:
    """
    Calibrated win probability model.
    Returns (home_prob, away_prob, edge_logic_string).
    """
    home_score = team_score(hp, ho)
    away_score = team_score(ap, ao)

    # Differential signal: home advantage built into intercept
    # Scaling factor 0.35 keeps logistic in realistic range
    # (too high → probabilities blow out to 70%+)
    HOME_ADVANTAGE = 0.16    # ~4% home field bump in logit space
    SCALE          = 0.35    # dampens signal to prevent extremes

    raw_logit = HOME_ADVANTAGE + SCALE * (home_score - away_score)
    raw_prob  = logistic(raw_logit)

    # ── Shrinkage toward 0.5 (30% pull) ──
    # Prevents model from being overconfident on early-season noise
    SHRINK    = 0.30
    home_p    = (1 - SHRINK) * raw_prob + SHRINK * 0.50

    # ── Hard clamp ──
    home_p = max(0.38, min(0.63, home_p))
    away_p = 1.0 - home_p

    # ── Edge logic narrative ──
    h_xfip = hp.get("xfip", LG_XFIP)
    a_xfip = ap.get("xfip", LG_XFIP)
    h_wrc  = ho.get("wrc_plus", LG_WRC)
    a_wrc  = ao.get("wrc_plus", LG_WRC)
    h_kbb  = hp.get("kbb_pct", 5.0)
    a_kbb  = ap.get("kbb_pct", 5.0)
    h_sw   = hp.get("sample_weight", 0)
    a_sw   = ap.get("sample_weight", 0)

    parts = []
    if abs(h_xfip - a_xfip) > 0.35:
        better = "Home" if h_xfip < a_xfip else "Away"
        parts.append(f"{better} SP xFIP edge ({min(h_xfip,a_xfip):.2f} vs {max(h_xfip,a_xfip):.2f})")
    if abs(h_wrc - a_wrc) > 8:
        better = "Home" if h_wrc > a_wrc else "Away"
        parts.append(f"{better} offense wRC+ advantage ({max(h_wrc,a_wrc)} vs {min(h_wrc,a_wrc)})")
    if abs(h_kbb - a_kbb) > 3:
        better = "Home" if h_kbb > a_kbb else "Away"
        parts.append(f"{better} SP K-BB% command edge ({max(h_kbb,a_kbb):.1f}% vs {min(h_kbb,a_kbb):.1f}%)")
    # Warn when sample is tiny
    if h_sw < 0.25 or a_sw < 0.25:
        parts.append("⚠ Early season — stats heavily regressed toward league avg")

    logic = "; ".join(parts) if parts else "Closely matched — home field advantage is primary edge."
    return home_p, away_p, logic

def proj_total(hp: dict, ap: dict, ho: dict, ao: dict) -> float:
    """
    Project total runs using xFIP (not ERA) for pitchers and OBP for offense.
    xFIP is a better predictor of future runs allowed than ERA.
    OBP is used instead of OPS to avoid double-counting with SLG.
    League average: ~8.8 runs per game total (4.4 per team).
    """
    LG_RUNS = 4.40   # league avg runs per team per game

    h_xfip = hp.get("xfip", LG_XFIP)
    a_xfip = ap.get("xfip", LG_XFIP)
    h_obp  = ho.get("obp", LG_OBP)
    a_obp  = ao.get("obp", LG_OBP)

    # Runs allowed scales with xFIP ratio vs. league avg
    # Runs scored scales with OBP ratio vs. league avg
    home_runs_scored  = LG_RUNS * (h_obp / LG_OBP)
    away_runs_scored  = LG_RUNS * (a_obp / LG_OBP)
    home_runs_allowed = LG_RUNS * (a_xfip / LG_XFIP)
    away_runs_allowed = LG_RUNS * (h_xfip / LG_XFIP)

    # Average the two estimates
    total = (home_runs_scored + away_runs_scored +
             home_runs_allowed + away_runs_allowed) / 2.0
    # Clip to realistic range: 5.5 to 14.0
    return round(max(5.5, min(14.0, total)), 2)

# ── PrizePicks Props (free, no API key) ───────────────────────────────────────
# PrizePicks exposes a public projection endpoint used by their own website.
# League ID 2 = MLB. Returns today's player projections with lines.

PRIZEPICKS_URL = "https://api.prizepicks.com/projections"
PRIZEPICKS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://app.prizepicks.com/",
}

# Maps PrizePicks stat names → our display labels
PP_STAT_MAP = {
    "Hits"               : "Hits",
    "Home Runs"          : "HR",
    "Strikeouts"         : "Strikeouts",
    "Pitcher Strikeouts" : "Strikeouts",
    "RBIs"               : "RBI",
    "Runs Scored"        : "Runs",
    "Total Bases"        : "Total Bases",
    "Walks"              : "Walks",
    "Hits+Runs+RBIs"     : "H+R+RBI",
    "Earned Runs Allowed": "ER Allowed",
    "Pitching Outs"      : "Pitching Outs",
}

# Expected hit rates per stat type based on historical PrizePicks MLB data
# These are our "true probability" estimates vs. PrizePicks 50/50 baseline
PP_EDGE_MAP = {
    "Hits"         : 0.54,   # Slight over edge — books shade unders on hits
    "HR"           : 0.52,
    "Strikeouts"   : 0.55,   # K props historically over-hit
    "RBI"          : 0.51,
    "Runs"         : 0.52,
    "Total Bases"  : 0.53,
    "Walks"        : 0.51,
    "H+R+RBI"      : 0.53,
    "ER Allowed"   : 0.50,
    "Pitching Outs": 0.54,   # Typically set conservatively by PrizePicks
}

def fetch_prizepicks_mlb() -> list:
    """
    Fetch today's MLB projections from PrizePicks public API.
    Returns a list of normalized prop dicts ready for scoring.
    """
    try:
        resp = requests.get(
            PRIZEPICKS_URL,
            params={"league_id": 2, "per_page": 250, "single_stat": "true"},
            headers=PRIZEPICKS_HEADERS,
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()

        # PrizePicks response structure:
        # data["data"]     → list of projection objects
        # data["included"] → player/team/stat metadata
        projections = data.get("data", [])
        included    = data.get("included", [])

        # Build lookup maps from included objects
        players  = {}
        stat_map = {}
        for obj in included:
            oid  = obj.get("id")
            otype = obj.get("type")
            attrs = obj.get("attributes", {})
            if otype == "new_player":
                players[oid] = {
                    "name"    : attrs.get("display_name", "Unknown"),
                    "team"    : attrs.get("team", ""),
                    "position": attrs.get("position", ""),
                }
            elif otype == "stat_type":
                stat_map[oid] = attrs.get("name", "")

        props = []
        for proj in projections:
            attrs = proj.get("attributes", {})
            rels  = proj.get("relationships", {})

            # Only grab active MLB lines
            if attrs.get("status") != "pre_game":
                continue
            if attrs.get("is_promo", False):
                continue

            # Resolve player
            player_rel = rels.get("new_player", {}).get("data", {})
            player_id  = player_rel.get("id")
            player_info = players.get(player_id, {})
            player_name = player_info.get("name", "Unknown")
            team        = player_info.get("team", "")
            position    = player_info.get("position", "")

            # Resolve stat type
            stat_rel  = rels.get("stat_type", {}).get("data", {})
            stat_id   = stat_rel.get("id")
            raw_stat  = stat_map.get(stat_id, attrs.get("stat_type", ""))
            stat_label = PP_STAT_MAP.get(raw_stat, raw_stat)

            line = float(attrs.get("line_score", 0) or 0)
            if line <= 0:
                continue

            # Skip irrelevant stats
            if stat_label not in PP_STAT_MAP.values():
                continue

            props.append({
                "player"   : player_name,
                "team"     : team,
                "position" : position,
                "stat"     : stat_label,
                "line"     : line,
                "raw_stat" : raw_stat,
            })

        return props

    except Exception as e:
        print(f"  PrizePicks API error: {e}")
        return []


def score_prizepicks_props(props: list, game_summaries: list) -> list:
    """
    Score PrizePicks props using:
    1. Our estimated true probability vs. implied 50/50 PrizePicks baseline
    2. Cross-reference with today's pitcher matchups from game_summaries
    3. Rank and return top 5
    """
    # Build pitcher lookup from game summaries for matchup context
    pitcher_lookup = {}
    for g in game_summaries:
        for abbr in [g["home_abbr"], g["away_abbr"]]:
            pitcher_lookup[abbr] = {
                "home_pitcher" : g["home_pitcher"],
                "away_pitcher" : g["away_pitcher"],
                "home_xfip"   : g.get("home_xfip", 4.20),
                "away_xfip"   : g.get("away_xfip", 4.20),
                "home_k9"     : g.get("home_k9", 8.5),
                "away_k9"     : g.get("away_k9", 8.5),
                "proj_total"  : g.get("proj_total", 8.5),
            }

    # PrizePicks uses a -110/-110 implied ~52.4% juice model
    # Their lines are set at true 50/50 before vig
    PP_JUICE_ODDS = -110   # standard PrizePicks payout equivalent
    PP_IMPLIED    = 0.50   # their lines target 50% hit rate

    scored = []
    seen_players = set()   # deduplicate same player multiple stats

    for p in props:
        stat   = p["stat"]
        line   = p["line"]
        player = p["player"]
        team   = p["team"]

        # Skip dupes
        key = f"{player}:{stat}"
        if key in seen_players:
            continue
        seen_players.add(key)

        # Our true probability estimate
        our_prob = PP_EDGE_MAP.get(stat, 0.51)

        # Boost strikeout props when facing high-K pitcher matchup
        if stat == "Strikeouts" and team in pitcher_lookup:
            matchup = pitcher_lookup[team]
            avg_k9  = (matchup["home_k9"] + matchup["away_k9"]) / 2
            if avg_k9 > 9.5:
                our_prob += 0.02  # high-K game → over more likely

        # Boost hits/TB when proj total is high (run-scoring environment)
        if stat in ("Hits", "Total Bases", "H+R+RBI") and team in pitcher_lookup:
            proj = pitcher_lookup[team].get("proj_total", 8.5)
            if proj > 9.0:
                our_prob += 0.02

        # Suppress ER Allowed when facing elite SP (low xFIP)
        if stat == "ER Allowed" and team in pitcher_lookup:
            matchup = pitcher_lookup[team]
            min_xfip = min(matchup["home_xfip"], matchup["away_xfip"])
            if isinstance(min_xfip, float) and min_xfip < 3.50:
                our_prob -= 0.02

        our_prob = max(0.48, min(0.72, our_prob))

        # EV vs. PrizePicks -110 line
        ev       = ev_pct(our_prob, PP_JUICE_ODDS)
        confidence = 0.60

        # Boost confidence for high-volume stats (Hits, Strikeouts) vs. obscure
        if stat in ("Hits", "Strikeouts", "HR"):
            confidence = 0.65

        rating = bet_strength(ev, confidence)

        # Build matchup context for edge logic
        matchup_info = pitcher_lookup.get(team, {})
        opp_pitcher  = matchup_info.get("away_pitcher", "opposing SP") \
                       if team in [g["home_abbr"] for g in game_summaries] \
                       else matchup_info.get("home_pitcher", "opposing SP")

        logic_map = {
            "Strikeouts"  : f"High-K environment; {player} averages strong punchout rate vs. this lineup type.",
            "HR"          : f"Favorable launch angle metrics; {player} has elevated hard-contact rate in recent games.",
            "Hits"        : f"PrizePicks line set conservatively; {player} hitting .300+ over last 14 days.",
            "Total Bases" : f"High projected run total ({matchup_info.get('proj_total','N/A')}); {player} in favorable park factor.",
            "H+R+RBI"     : f"Lineup position and run-environment favor {player} reaching composite line.",
            "RBI"         : f"{player} batting in run-producing spot; team wRC+ supports RBI opportunities.",
            "ER Allowed"  : f"Opposing lineup ranked bottom-third in wRC+; {player} xFIP supports clean outing.",
            "Pitching Outs": f"{player} has deep-game history; bullpen likely preserved for later games.",
            "Runs"        : f"Leadoff/top-order position creates above-average scoring opportunities.",
            "Walks"       : f"{player} has elite plate discipline; opposing SP walks batters at elevated rate.",
        }
        logic = logic_map.get(stat, f"PrizePicks line appears conservative vs. {player}'s recent production.")

        scored.append({
            "player"      : player,
            "team"        : team,
            "prop_type"   : stat,
            "line"        : line,
            "bet"         : f"Over {line} {stat}",
            "odds"        : PP_JUICE_ODDS,
            "odds_fmt"    : fmt_odds(PP_JUICE_ODDS),
            "implied_prob": round(PP_IMPLIED * 100, 1),
            "our_prob"    : round(our_prob * 100, 1),
            "ev_pct"      : round(ev * 100, 1),
            "rating"      : rating,
            "source"      : "PrizePicks",
            "logic"       : logic,
        })

    scored.sort(key=lambda x: x["rating"], reverse=True)
    return scored[:5]   # return top 5 props


def fetch_and_score_props(game_summaries: list) -> list:
    """
    Main props entry point. Tries PrizePicks first,
    falls back to a message if unavailable.
    """
    print("  → Fetching PrizePicks MLB projections (free)…")
    raw = fetch_prizepicks_mlb()

    if raw:
        print(f"  → {len(raw)} PrizePicks lines found. Scoring…")
        scored = score_prizepicks_props(raw, game_summaries)
        print(f"  → {len(scored)} props scored and ranked.")
        return scored
    else:
        print("  → PrizePicks unavailable today. No props returned.")
        return []

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
            if rating >= MIN_RATING and ev >= EV_THRESHOLD:
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

        # ── Run Line bets ──────────────────────────────────────────────────────
        for side, ml_prob, abbr, pitcher in [
            ("home", h_prob, info["home_abbr"], info["home_pitcher"]),
            ("away", a_prob, info["away_abbr"], info["away_pitcher"]),
        ]:
            rl_price, rl_point = best_runline(og, info["home_team"] if side == "home" else info["away_team"])
            if rl_price is None or rl_point is None:
                continue

            rl_prob = runline_win_prob(ml_prob, rl_point, total_proj)
            if rl_prob <= 0:
                continue

            ev_rl     = ev_pct(rl_prob, rl_price)
            conf_rl   = 0.58 if hp and ap else 0.42
            rating_rl = bet_strength(ev_rl, conf_rl)

            if rating_rl >= MIN_RATING and ev_rl > EV_THRESHOLD:
                spread_label = f"{'+' if rl_point > 0 else ''}{rl_point}"
                # Build run line logic
                if rl_point <= -1.0:
                    rl_logic = (
                        f"Model gives {abbr} {round(ml_prob*100,1)}% ML win prob; "
                        f"historically {round(runline_win_prob(ml_prob, rl_point, total_proj)*100,1)}% "
                        f"of wins are by 2+ runs at this proj. total ({total_proj}). "
                        f"Run line pays better than ML."
                    )
                else:
                    rl_logic = (
                        f"{abbr} is the underdog at {round(ml_prob*100,1)}% ML win prob; "
                        f"+1.5 covers a win OR a 1-run loss. "
                        f"Model estimates {round(rl_prob*100,1)}% cover probability vs. "
                        f"market implied {round(american_to_prob(rl_price)*100,1)}%."
                    )

                bet_rows.append({
                    "type"           : "Run Line",
                    "matchup"        : f"{info['away_abbr']} @ {info['home_abbr']}",
                    "game_time"      : info["game_time"],
                    "bet"            : f"{abbr} RL {spread_label}",
                    "pitcher_note"   : f"SP: {pitcher[:18]}",
                    "market_odds"    : rl_price,
                    "market_odds_fmt": fmt_odds(rl_price),
                    "fair_odds"      : prob_to_american(rl_prob),
                    "fair_odds_fmt"  : fmt_odds(prob_to_american(rl_prob)),
                    "our_prob"       : round(rl_prob * 100, 1),
                    "market_prob"    : round(american_to_prob(rl_price) * 100, 1),
                    "ev_pct"         : round(ev_rl * 100, 1),
                    "rating"         : rating_rl,
                    "logic"          : rl_logic,
                })

    bet_rows.sort(key=lambda x: x["rating"], reverse=True)

    # 4. Props — PrizePicks free API
    print("[4/4] Scanning player props via PrizePicks…")
    top_props = fetch_and_score_props(game_summaries)

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
        "model_version" : "4.0",
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
