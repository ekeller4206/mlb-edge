"""
MLB Betting Dashboard — Streamlit App
State-of-the-art UI. Zero manual input. Auto-refreshes daily.
"""

import json
import os
import time
import math
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, date, timezone
from pathlib import Path

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚾ MLB Edge",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@300;400;500&family=Instrument+Serif:ital@0;1&display=swap');

/* ── Root & Background ── */
:root {
    --green:   #00ff87;
    --red:     #ff3b3b;
    --amber:   #ffb347;
    --blue:    #4fc3f7;
    --dark:    #080c0f;
    --surface: #0d1318;
    --card:    #111820;
    --border:  rgba(255,255,255,0.07);
    --text:    #e8edf2;
    --muted:   #5a6a7a;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--dark) !important;
    color: var(--text) !important;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 80% 60% at 10% -10%, rgba(0,255,135,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 90% 110%, rgba(79,195,247,0.05) 0%, transparent 55%),
        var(--dark) !important;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { background: var(--surface) !important; }
.block-container { padding: 1.5rem 2.5rem 4rem !important; max-width: 1600px !important; }

/* ── Typography ── */
* { font-family: 'DM Mono', monospace !important; }
h1, h2, h3 { font-family: 'Bebas Neue', cursive !important; letter-spacing: 0.08em !important; }

/* ── Metric overrides ── */
[data-testid="metric-container"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
}
[data-testid="metric-container"] label { color: var(--muted) !important; font-size: 0.72rem !important; letter-spacing: 0.12em !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family: 'Bebas Neue', cursive !important; font-size: 2.4rem !important; }

/* ── Divider ── */
hr { border-color: var(--border) !important; }

/* ── Tab styling ── */
[data-baseweb="tab-list"] { background: var(--surface) !important; border-radius: 10px !important; padding: 4px !important; gap: 4px !important; border: 1px solid var(--border) !important; }
[data-baseweb="tab"] { border-radius: 8px !important; color: var(--muted) !important; font-size: 0.8rem !important; letter-spacing: 0.08em !important; }
[aria-selected="true"] { background: var(--card) !important; color: var(--green) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--dark); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Bet Cards ── */
.bet-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}
.bet-card:hover { border-color: rgba(255,255,255,0.15); }
.bet-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
}
.bet-card.strong::before { background: linear-gradient(90deg, var(--green), #00d4ff); }
.bet-card.solid::before  { background: linear-gradient(90deg, var(--amber), #ff8c00); }
.bet-card.marginal::before { background: var(--blue); }

.bet-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem; }
.bet-matchup { font-family: 'Bebas Neue', cursive !important; font-size: 1.35rem; letter-spacing: 0.06em; color: var(--text); }
.bet-time { font-size: 0.72rem; color: var(--muted); letter-spacing: 0.1em; }
.bet-label { font-size: 0.68rem; color: var(--muted); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.2rem; }
.bet-value { font-family: 'Bebas Neue', cursive !important; font-size: 1.6rem; letter-spacing: 0.04em; }
.bet-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr; gap: 1rem; margin-bottom: 0.9rem; }
.bet-logic { font-size: 0.74rem; color: var(--muted); line-height: 1.6; border-top: 1px solid var(--border); padding-top: 0.7rem; margin-top: 0.2rem; }
.logic-icon { margin-right: 0.3rem; }

/* ── Rating Badge ── */
.rating-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 52px; height: 52px;
    border-radius: 50%;
    font-family: 'Bebas Neue', cursive !important;
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: 0;
    flex-shrink: 0;
}
.rating-strong  { background: rgba(0,255,135,0.12); color: var(--green); border: 2px solid rgba(0,255,135,0.4); }
.rating-solid   { background: rgba(255,179,71,0.12); color: var(--amber); border: 2px solid rgba(255,179,71,0.4); }
.rating-marginal{ background: rgba(79,195,247,0.10); color: var(--blue);  border: 2px solid rgba(79,195,247,0.3); }

/* ── EV Badge ── */
.ev-positive { color: var(--green); font-size: 1.1rem; font-family: 'Bebas Neue', cursive !important; }
.ev-medium   { color: var(--amber); font-size: 1.1rem; font-family: 'Bebas Neue', cursive !important; }
.ev-low      { color: var(--blue);  font-size: 1.1rem; font-family: 'Bebas Neue', cursive !important; }

/* ── Odds Pill ── */
.odds-pill {
    display: inline-block;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.15rem 0.5rem;
    font-size: 0.95rem;
    letter-spacing: 0.04em;
}
.odds-pill.fair { border-color: rgba(0,255,135,0.3); color: var(--green); background: rgba(0,255,135,0.06); }

/* ── Prop Cards ── */
.prop-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--blue);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}
.prop-grid { display: grid; grid-template-columns: 3fr 1fr 1fr 1fr 1fr; gap: 0.8rem; align-items: center; }
.prop-player { font-size: 1rem; font-weight: 500; }
.prop-type   { font-size: 0.7rem; color: var(--blue); letter-spacing: 0.12em; text-transform: uppercase; }

/* ── Game Summary Cards ── */
.game-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.8rem;
}
.game-teams { font-family: 'Bebas Neue', cursive !important; font-size: 1.2rem; letter-spacing: 0.06em; }
.game-meta  { font-size: 0.7rem; color: var(--muted); margin-top: 0.3rem; }
.prob-bar-wrap { background: rgba(255,255,255,0.05); border-radius: 4px; height: 6px; margin: 0.6rem 0; overflow: hidden; }
.prob-bar-fill { height: 100%; background: linear-gradient(90deg, var(--green), #00d4ff); border-radius: 4px; }
.stat-chip {
    display: inline-block;
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    padding: 0.15rem 0.5rem;
    font-size: 0.68rem;
    color: var(--muted);
    margin-right: 0.3rem;
    margin-top: 0.3rem;
}
.stat-chip span { color: var(--text); }

/* ── Header ── */
.dashboard-header {
    display: flex; align-items: flex-start; justify-content: space-between;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
}
.header-logo { font-family: 'Bebas Neue', cursive !important; font-size: 3.5rem; letter-spacing: 0.1em; line-height: 1; }
.header-logo span { color: var(--green); }
.header-sub { font-size: 0.72rem; color: var(--muted); letter-spacing: 0.15em; text-transform: uppercase; margin-top: 0.3rem; }
.header-ts  { font-size: 0.7rem; color: var(--muted); text-align: right; line-height: 2; }
.header-ts strong { color: var(--text); display: block; font-size: 0.85rem; }

/* ── Status Pill ── */
.status-live {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: rgba(0,255,135,0.1);
    border: 1px solid rgba(0,255,135,0.3);
    border-radius: 20px;
    padding: 0.25rem 0.7rem;
    font-size: 0.7rem;
    color: var(--green);
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.pulse {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--green);
    animation: pulse 1.8s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.4; transform: scale(0.7); }
}

/* ── Section Headers ── */
.section-header {
    display: flex; align-items: center; gap: 0.7rem;
    margin: 2rem 0 1.2rem;
}
.section-title { font-family: 'Bebas Neue', cursive !important; font-size: 1.6rem; letter-spacing: 0.08em; }
.section-count {
    background: rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 0.1rem 0.6rem;
    font-size: 0.72rem;
    color: var(--muted);
}

/* ── No-data state ── */
.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: var(--muted);
}
.empty-icon { font-size: 3rem; margin-bottom: 1rem; }

/* ── Disclaimer ── */
.disclaimer {
    margin-top: 3rem;
    padding: 1rem 1.5rem;
    background: rgba(255,59,59,0.06);
    border: 1px solid rgba(255,59,59,0.2);
    border-radius: 10px;
    font-size: 0.7rem;
    color: var(--muted);
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)


# ── Data Loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_data() -> dict | None:
    """Load mlb_results.json from repo root or GitHub raw URL."""
    # Try local file first (works on Streamlit Cloud after GH Actions pushes)
    local = Path("mlb_results.json")
    if local.exists():
        try:
            with open(local) as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback: try to pull from GitHub raw (set GITHUB_RAW_URL in secrets)
    raw_url = os.environ.get("GITHUB_RAW_URL")
    if raw_url:
        try:
            r = requests.get(raw_url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            pass

    return None


def rating_class(r: float) -> str:
    if r >= 8.0: return "strong"
    if r >= 6.0: return "solid"
    return "marginal"

def rating_badge_class(r: float) -> str:
    if r >= 8.0: return "rating-strong"
    if r >= 6.0: return "rating-solid"
    return "rating-marginal"

def ev_class(ev: float) -> str:
    if ev >= 8: return "ev-positive"
    if ev >= 4: return "ev-medium"
    return "ev-low"

def odds_color(market: str, fair: str) -> str:
    """Return green if fair odds are better than market."""
    try:
        m = int(market.replace("+", ""))
        f = int(fair.replace("+", ""))
        return "fair" if f > m else ""
    except Exception:
        return ""

def render_bet_card(bet: dict):
    rc  = rating_class(bet["rating"])
    rbc = rating_badge_class(bet["rating"])
    evc = ev_class(bet["ev_pct"])
    mo  = bet.get("market_odds_fmt", str(bet.get("market_odds", "N/A")))
    fo  = bet.get("fair_odds_fmt",   str(bet.get("fair_odds",   "N/A")))
    oc  = odds_color(mo, fo)
    btype_icon = "📈" if bet["type"] == "Moneyline" else "🎯"

    st.markdown(f"""
    <div class="bet-card {rc}">
      <div class="bet-header">
        <div>
          <div class="bet-matchup">{bet['matchup']}</div>
          <div class="bet-time">{btype_icon} {bet['type']}  ·  {bet['game_time']}</div>
        </div>
        <div class="rating-badge {rbc}">{bet['rating']}</div>
      </div>
      <div class="bet-grid">
        <div>
          <div class="bet-label">Suggested Bet</div>
          <div class="bet-value">{bet['bet']}</div>
          <div style="font-size:0.7rem;color:var(--muted);margin-top:0.2rem">{bet.get('pitcher_note','')}</div>
        </div>
        <div>
          <div class="bet-label">Market Odds</div>
          <div><span class="odds-pill">{mo}</span></div>
        </div>
        <div>
          <div class="bet-label">Fair Odds</div>
          <div><span class="odds-pill {oc}">{fo}</span></div>
        </div>
        <div>
          <div class="bet-label">+EV Edge</div>
          <div class="{evc}">+{bet['ev_pct']}%</div>
        </div>
        <div>
          <div class="bet-label">Win Prob</div>
          <div style="font-size:1.1rem;font-family:'Bebas Neue',cursive">{bet.get('our_prob','--')}%</div>
        </div>
      </div>
      <div class="bet-logic"><span class="logic-icon">🔬</span>{bet['logic']}</div>
    </div>
    """, unsafe_allow_html=True)

def render_prop_card(prop: dict, rank: int):
    medals = ["🥇", "🥈", "🥉"]
    medal  = medals[rank] if rank < 3 else "⭐"
    rbc    = rating_badge_class(prop["rating"])

    st.markdown(f"""
    <div class="prop-card">
      <div class="prop-grid">
        <div>
          <div style="display:flex;align-items:center;gap:0.5rem">
            <span style="font-size:1.3rem">{medal}</span>
            <div>
              <div class="prop-player">{prop['player']}</div>
              <div class="prop-type">{prop['prop_type']}</div>
            </div>
          </div>
        </div>
        <div>
          <div class="bet-label">Bet</div>
          <div style="font-size:0.9rem">{prop['bet']}</div>
        </div>
        <div>
          <div class="bet-label">Odds</div>
          <div><span class="odds-pill">{prop.get('odds_fmt', prop['odds'])}</span></div>
        </div>
        <div>
          <div class="bet-label">+EV</div>
          <div class="{ev_class(prop['ev_pct'])}">+{prop['ev_pct']}%</div>
        </div>
        <div>
          <div class="rating-badge {rbc}" style="width:44px;height:44px;font-size:1.2rem">{prop['rating']}</div>
        </div>
      </div>
      <div style="font-size:0.72rem;color:var(--muted);margin-top:0.6rem;padding-top:0.5rem;border-top:1px solid var(--border)">
        🔬 {prop['logic']}
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_game_card(game: dict):
    hp = game.get("home_win_prob", 50)
    ap = game.get("away_win_prob", 50)
    st.markdown(f"""
    <div class="game-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div class="game-teams">{game['away_abbr']} <span style="color:var(--muted)">@</span> {game['home_abbr']}</div>
          <div class="game-meta">🕐 {game['game_time']}  ·  📍 {game.get('venue','')}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:0.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em">Win Prob</div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.1rem">
            {game['away_abbr']} <span style="color:var(--green)">{ap}%</span>
            &nbsp;·&nbsp;
            {game['home_abbr']} <span style="color:var(--green)">{hp}%</span>
          </div>
        </div>
      </div>
      <div class="prob-bar-wrap">
        <div class="prob-bar-fill" style="width:{hp}%"></div>
      </div>
      <div>
        <span class="stat-chip">SP(H): <span>{game['home_pitcher'][:16]}</span></span>
        <span class="stat-chip">SP(A): <span>{game['away_pitcher'][:16]}</span></span>
        <span class="stat-chip">xFIP(H): <span>{game.get('home_xfip','--')}</span></span>
        <span class="stat-chip">xFIP(A): <span>{game.get('away_xfip','--')}</span></span>
        <span class="stat-chip">wRC+(H): <span>{game.get('home_wrc','--')}</span></span>
        <span class="stat-chip">wRC+(A): <span>{game.get('away_wrc','--')}</span></span>
        <span class="stat-chip">Proj O/U: <span>{game.get('proj_total','--')}</span></span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Main App ──────────────────────────────────────────────────────────────────

def main():
    data = load_data()

    # ── Header ────────────────────────────────────────────────────────────────
    today_str = date.today().strftime("%A, %B %d, %Y")
    if data:
        gen_raw = data.get("generated_at", "")
        try:
            gen_dt  = datetime.fromisoformat(gen_raw.replace("Z", "+00:00"))
            gen_str = gen_dt.strftime("%I:%M %p UTC")
        except Exception:
            gen_str = gen_raw[:16]
    else:
        gen_str = "—"

    st.markdown(f"""
    <div class="dashboard-header">
      <div>
        <div class="header-logo">MLB<span>EDGE</span></div>
        <div class="header-sub">Sabermetric Betting Intelligence · Daily Auto-Update</div>
      </div>
      <div style="text-align:right">
        <div class="status-live"><div class="pulse"></div>LIVE DATA</div>
        <div class="header-ts">
          <strong>{today_str}</strong>
          Model run: {gen_str}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── No Data State ──────────────────────────────────────────────────────────
    if not data:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-icon">⚾</div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.8rem;letter-spacing:0.08em">Awaiting Today's Data</div>
          <div style="margin-top:0.5rem;font-size:0.8rem">
            The algorithm runs daily at 11:00 AM ET via GitHub Actions.<br>
            Check back after 11 AM or trigger a manual run in your repo.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    bets  = data.get("bets", [])
    props = data.get("props", [])
    games = data.get("games", [])

    # ── KPI Row ───────────────────────────────────────────────────────────────
    strong = [b for b in bets if b["rating"] >= 8.0]
    solid  = [b for b in bets if 6.0 <= b["rating"] < 8.0]
    best_ev = max((b["ev_pct"] for b in bets), default=0)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Games Today",    data.get("game_count", 0))
    k2.metric("Total Bets",     len(bets))
    k3.metric("🔥 Strong Plays", len(strong), help="Rating ≥ 8.0")
    k4.metric("✅ Solid Plays",  len(solid),  help="Rating 6.0–7.9")
    k5.metric("Best +EV Edge",  f"+{best_ev:.1f}%")

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_bets, tab_props, tab_games = st.tabs([
        f"  📊  TODAY'S BETS ({len(bets)})  ",
        f"  🎯  PLAYER PROPS ({len(props)})  ",
        f"  🗓  ALL GAMES ({len(games)})  ",
    ])

    # ──────────────────── BETS TAB ────────────────────────────────────────────
    with tab_bets:
        if not bets:
            st.markdown('<div class="empty-state"><div class="empty-icon">🔍</div><div>No plays meet the minimum threshold today.</div></div>', unsafe_allow_html=True)
        else:
            # Filter controls
            fc1, fc2, fc3 = st.columns([1, 1, 2])
            with fc1:
                bet_type_filter = st.selectbox("Bet Type", ["All", "Moneyline", "Total"], key="bt")
            with fc2:
                min_rating = st.selectbox("Min Rating", [5.5, 6.0, 7.0, 8.0], index=0, key="mr")
            with fc3:
                st.markdown("&nbsp;", unsafe_allow_html=True)

            filtered = [b for b in bets
                        if b["rating"] >= min_rating
                        and (bet_type_filter == "All" or b["type"] == bet_type_filter)]
            filtered.sort(key=lambda x: x["rating"], reverse=True)

            if strong and min_rating <= 8.0:
                st.markdown("""
                <div class="section-header">
                  <div class="section-title">🔥 Strong Plays</div>
                  <div class="section-count">Rating ≥ 8.0</div>
                </div>""", unsafe_allow_html=True)
                for b in [x for x in filtered if x["rating"] >= 8.0]:
                    render_bet_card(b)

            mid = [x for x in filtered if 6.0 <= x["rating"] < 8.0]
            if mid:
                st.markdown("""
                <div class="section-header">
                  <div class="section-title">✅ Solid Value</div>
                  <div class="section-count">Rating 6.0–7.9</div>
                </div>""", unsafe_allow_html=True)
                for b in mid:
                    render_bet_card(b)

            low = [x for x in filtered if x["rating"] < 6.0]
            if low:
                st.markdown("""
                <div class="section-header">
                  <div class="section-title">🔵 Marginal Plays</div>
                  <div class="section-count">Rating 5.5–5.9</div>
                </div>""", unsafe_allow_html=True)
                for b in low:
                    render_bet_card(b)

            if not filtered:
                st.info("No bets match the current filter.")

            # EV Distribution Chart
            if len(bets) > 1:
                st.markdown("---")
                st.markdown('<div class="section-title" style="font-family:\'Bebas Neue\',cursive;font-size:1.4rem;letter-spacing:0.08em;margin-bottom:1rem">📈 EV Distribution</div>', unsafe_allow_html=True)
                df = pd.DataFrame(bets)[["bet", "ev_pct", "rating", "type"]].copy()
                df.columns = ["Bet", "EV%", "Rating", "Type"]
                df = df.sort_values("Rating", ascending=False)
                st.bar_chart(df.set_index("Bet")["EV%"])

    # ─────────────────── PROPS TAB ────────────────────────────────────────────
    with tab_props:
        if not props:
            st.markdown('<div class="empty-state"><div class="empty-icon">🎯</div><div>No prop data available today.</div></div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="section-header">
              <div class="section-title">⭐ Top Player Props</div>
              <div class="section-count">Ranked by +EV Edge</div>
            </div>""", unsafe_allow_html=True)
            for i, prop in enumerate(props):
                render_prop_card(prop, i)

            st.markdown("""
            <div style="margin-top:1.5rem;padding:1rem 1.2rem;background:rgba(79,195,247,0.06);
                        border:1px solid rgba(79,195,247,0.2);border-radius:10px;
                        font-size:0.74rem;color:var(--muted);line-height:1.9">
              <strong style="color:var(--blue)">⚡ How Props Are Scored</strong><br>
              Each prop is scored using implied probability vs. our adjusted probability (market implied + 4% edge correction for book overpricing).
              The +EV% represents the mathematical edge over the posted line. Props ranked by composite Bet Strength Rating.
            </div>
            """, unsafe_allow_html=True)

    # ─────────────────── GAMES TAB ────────────────────────────────────────────
    with tab_games:
        if not games:
            st.markdown('<div class="empty-state"><div class="empty-icon">🗓</div><div>No game data available.</div></div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="section-header">
              <div class="section-title">🗓 Full Slate</div>
              <div class="section-count">Sabermetric Breakdown</div>
            </div>""", unsafe_allow_html=True)

            search = st.text_input("Filter by team", placeholder="e.g. Yankees, LAD, NYM…", key="gs")
            shown = [g for g in games
                     if not search or search.lower() in g["home_team"].lower()
                     or search.lower() in g["away_team"].lower()
                     or search.lower() in g["home_abbr"].lower()
                     or search.lower() in g["away_abbr"].lower()]
            for g in shown:
                render_game_card(g)

            if not shown:
                st.info("No games match that search.")

    # ── Methodology Expander ──────────────────────────────────────────────────
    with st.expander("🔬 Model Methodology & Rating Guide"):
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("""
**📐 Win Probability Model**
- Base home win rate: **54%** (MLB historical average)
- Pitcher quality: xFIP vs. league avg (4.20 ERA)
- Offense quality: wRC+ proxy scaled from team OPS
- K/9 edge factor for strikeout dominance
- Logistic clamp: probabilities kept in [30%, 72%]

**📊 Bet Strength Rating (1.0–10.0)**
- `Rating = 1 + (EV_score × 0.65 + Confidence × 0.35) × 9`
- 15% +EV = perfect 10.0 score
- Minimum threshold: **5.5** to appear in dashboard
            """)
        with mc2:
            st.markdown("""
**⚾ Key Sabermetrics Used**
| Stat | Meaning |
|---|---|
| xFIP | Pitcher skill, strips defense/luck |
| K/9 | Strikeouts per 9 innings |
| wRC+ | Weighted Runs Created (offense, park-adj) |
| OPS | On-base + Slugging (offense proxy) |
| +EV% | Edge vs. sportsbook implied probability |

**🎯 Rating Key**
- 🔥 **8.0–10.0** → Strong — full unit bet
- ✅ **6.0–7.9** → Solid — half unit
- 🔵 **5.5–5.9** → Marginal — monitor only
- ❌ **< 5.5** → No play — not shown
            """)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="disclaimer">
      ⚠️ <strong>DISCLAIMER:</strong> This dashboard is for educational and informational purposes only.
      No content constitutes financial or betting advice. Past model performance does not guarantee future results.
      Bet responsibly. If you or someone you know has a gambling problem, call 1-800-522-4700.
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
