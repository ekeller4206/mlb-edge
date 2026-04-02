import json
import os
import requests
import streamlit as st
from datetime import datetime, date
from pathlib import Path

st.set_page_config(
    page_title="MLB Edge",
    page_icon="⚾",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&display=swap');
html, body, [data-testid="stAppViewContainer"] { background-color: #080c0f !important; color: #e8edf2 !important; }
[data-testid="stAppViewContainer"] { background: radial-gradient(ellipse 80% 60% at 10% -10%, rgba(0,255,135,0.06) 0%, transparent 60%), #080c0f !important; }
[data-testid="stHeader"] { background: transparent !important; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }
* { font-family: 'DM Mono', monospace !important; }
h1, h2, h3 { font-family: 'Bebas Neue', cursive !important; letter-spacing: 0.08em !important; }
[data-testid="metric-container"] { background: #111820 !important; border: 1px solid rgba(255,255,255,0.07) !important; border-radius: 12px !important; padding: 1rem !important; }
[data-testid="metric-container"] label { color: #5a6a7a !important; font-size: 0.72rem !important; letter-spacing: 0.12em !important; text-transform: uppercase !important; }
[data-testid="stMetricValue"] { font-family: 'Bebas Neue', cursive !important; font-size: 2.2rem !important; color: #e8edf2 !important; }
[data-baseweb="tab-list"] { background: #0d1318 !important; border-radius: 10px !important; padding: 4px !important; border: 1px solid rgba(255,255,255,0.07) !important; }
[data-baseweb="tab"] { color: #5a6a7a !important; font-size: 0.8rem !important; }
[aria-selected="true"] { background: #111820 !important; color: #00ff87 !important; }
hr { border-color: rgba(255,255,255,0.07) !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_data():
    local = Path("mlb_results.json")
    if local.exists():
        try:
            with open(local) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def rating_color(r):
    if r >= 8.0: return "#00ff87"
    if r >= 6.0: return "#ffb347"
    return "#4fc3f7"

def ev_color(ev):
    if ev >= 8: return "#00ff87"
    if ev >= 4: return "#ffb347"
    return "#4fc3f7"

def render_bet(bet):
    rc = rating_color(bet["rating"])
    ec = ev_color(bet["ev_pct"])
    mo = bet.get("market_odds_fmt", str(bet.get("market_odds", "")))
    fo = bet.get("fair_odds_fmt", str(bet.get("fair_odds", "")))
    st.markdown(f"""
    <div style="background:#111820;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:1.2rem 1.4rem;margin-bottom:1rem;border-top:3px solid {rc};">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.8rem">
        <div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.3rem;letter-spacing:0.06em">{bet['matchup']}</div>
          <div style="font-size:0.7rem;color:#5a6a7a;margin-top:0.2rem">{bet['type']} · {bet['game_time']}</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border:2px solid {rc};border-radius:50%;width:50px;height:50px;display:flex;align-items:center;justify-content:center;font-family:'Bebas Neue',cursive;font-size:1.3rem;color:{rc}">{bet['rating']}</div>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr;gap:1rem;margin-bottom:0.8rem">
        <div>
          <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase;letter-spacing:0.1em">Suggested Bet</div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.4rem;letter-spacing:0.04em">{bet['bet']}</div>
          <div style="font-size:0.68rem;color:#5a6a7a">{bet.get('pitcher_note','')}</div>
        </div>
        <div>
          <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase;letter-spacing:0.1em">Market Odds</div>
          <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:0.2rem 0.5rem;display:inline-block;margin-top:0.3rem">{mo}</div>
        </div>
        <div>
          <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase;letter-spacing:0.1em">Fair Odds</div>
          <div style="background:rgba(0,255,135,0.06);border:1px solid rgba(0,255,135,0.3);color:#00ff87;border-radius:6px;padding:0.2rem 0.5rem;display:inline-block;margin-top:0.3rem">{fo}</div>
        </div>
        <div>
          <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase;letter-spacing:0.1em">+EV Edge</div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.2rem;color:{ec};margin-top:0.3rem">+{bet['ev_pct']}%</div>
        </div>
        <div>
          <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase;letter-spacing:0.1em">Win Prob</div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.2rem;margin-top:0.3rem">{bet.get('our_prob','--')}%</div>
        </div>
      </div>
      <div style="font-size:0.72rem;color:#5a6a7a;border-top:1px solid rgba(255,255,255,0.07);padding-top:0.6rem;line-height:1.6">🔬 {bet['logic']}</div>
    </div>
    """, unsafe_allow_html=True)

def render_prop(prop, rank):
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    rc = rating_color(prop["rating"])
    ec = ev_color(prop["ev_pct"])
    st.markdown(f"""
    <div style="background:#111820;border:1px solid rgba(255,255,255,0.07);border-left:3px solid #4fc3f7;border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.8rem">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div style="display:flex;align-items:center;gap:0.7rem">
          <span style="font-size:1.4rem">{medals[rank] if rank < 5 else "⭐"}</span>
          <div>
            <div style="font-size:1rem">{prop['player']} <span style="color:#5a6a7a;font-size:0.8rem">({prop.get('team','')})</span></div>
            <div style="font-size:0.68rem;color:#4fc3f7;text-transform:uppercase;letter-spacing:0.1em">{prop['prop_type']}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:1.5rem">
          <div style="text-align:center">
            <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase">Bet</div>
            <div style="font-size:0.85rem">{prop['bet']}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase">Odds</div>
            <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:0.15rem 0.5rem">{prop.get('odds_fmt', prop['odds'])}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase">+EV</div>
            <div style="font-family:'Bebas Neue',cursive;font-size:1.1rem;color:{ec}">+{prop['ev_pct']}%</div>
          </div>
          <div style="background:rgba(255,255,255,0.05);border:2px solid {rc};border-radius:50%;width:42px;height:42px;display:flex;align-items:center;justify-content:center;font-family:'Bebas Neue',cursive;font-size:1.1rem;color:{rc}">{prop['rating']}</div>
        </div>
      </div>
      <div style="font-size:0.7rem;color:#5a6a7a;margin-top:0.6rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.05)">🔬 {prop['logic']}</div>
    </div>
    """, unsafe_allow_html=True)

def render_game(game):
    hp = game.get("home_win_prob", 50)
    st.markdown(f"""
    <div style="background:#111820;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.8rem">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1.2rem;letter-spacing:0.06em">{game['away_abbr']} <span style="color:#5a6a7a">@</span> {game['home_abbr']}</div>
          <div style="font-size:0.68rem;color:#5a6a7a;margin-top:0.2rem">🕐 {game['game_time']} · 📍 {game.get('venue','')}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:0.65rem;color:#5a6a7a;text-transform:uppercase">Win Prob</div>
          <div style="font-family:'Bebas Neue',cursive;font-size:1rem">{game['away_abbr']} <span style="color:#00ff87">{game.get('away_win_prob',50)}%</span> · {game['home_abbr']} <span style="color:#00ff87">{hp}%</span></div>
        </div>
      </div>
      <div style="background:rgba(255,255,255,0.05);border-radius:4px;height:5px;margin:0.6rem 0;overflow:hidden">
        <div style="width:{hp}%;height:100%;background:linear-gradient(90deg,#00ff87,#00d4ff);border-radius:4px"></div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:0.4rem">
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">SP(H): <span style="color:#e8edf2">{game['home_pitcher'][:18]}</span></span>
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">SP(A): <span style="color:#e8edf2">{game['away_pitcher'][:18]}</span></span>
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">xFIP(H): <span style="color:#e8edf2">{game.get('home_xfip','--')}</span></span>
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">xFIP(A): <span style="color:#e8edf2">{game.get('away_xfip','--')}</span></span>
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">wRC+(H): <span style="color:#e8edf2">{game.get('home_wrc','--')}</span></span>
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">wRC+(A): <span style="color:#e8edf2">{game.get('away_wrc','--')}</span></span>
        <span style="background:rgba(255,255,255,0.05);border-radius:6px;padding:0.15rem 0.5rem;font-size:0.67rem;color:#5a6a7a">Proj O/U: <span style="color:#e8edf2">{game.get('proj_total','--')}</span></span>
      </div>
    </div>
    """, unsafe_allow_html=True)


data = load_data()
today_str = date.today().strftime("%A, %B %d, %Y")
gen_str = "—"
if data:
    try:
        gen_dt = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
        gen_str = gen_dt.strftime("%I:%M %p UTC")
    except Exception:
        gen_str = data.get("generated_at", "")[:16]

st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:1px solid rgba(255,255,255,0.07)">
  <div>
    <div style="font-family:'Bebas Neue',cursive;font-size:3.2rem;letter-spacing:0.1em;line-height:1">MLB<span style="color:#00ff87">EDGE</span></div>
    <div style="font-size:0.7rem;color:#5a6a7a;letter-spacing:0.15em;text-transform:uppercase;margin-top:0.3rem">Sabermetric Betting Intelligence · Daily Auto-Update</div>
  </div>
  <div style="text-align:right">
    <div style="display:inline-flex;align-items:center;gap:0.4rem;background:rgba(0,255,135,0.1);border:1px solid rgba(0,255,135,0.3);border-radius:20px;padding:0.25rem 0.7rem;font-size:0.68rem;color:#00ff87;letter-spacing:0.1em;text-transform:uppercase">● LIVE DATA</div>
    <div style="font-size:0.75rem;color:#e8edf2;margin-top:0.5rem">{today_str}</div>
    <div style="font-size:0.68rem;color:#5a6a7a">Model run: {gen_str}</div>
  </div>
</div>
""", unsafe_allow_html=True)

if not data:
    st.markdown('<div style="text-align:center;padding:4rem;color:#5a6a7a"><div style="font-size:3rem">⚾</div><div style="font-family:\'Bebas Neue\',cursive;font-size:1.8rem;margin-top:1rem">Awaiting Today\'s Data</div><div style="margin-top:0.5rem;font-size:0.8rem">Algorithm runs daily at 11:00 AM ET.</div></div>', unsafe_allow_html=True)
    st.stop()

bets  = data.get("bets", [])
props = data.get("props", [])
games = data.get("games", [])

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Games Today",     data.get("game_count", 0))
k2.metric("Total Bets",      len(bets))
k3.metric("🔥 Strong Plays", len([b for b in bets if b["rating"] >= 8.0]))
k4.metric("✅ Solid Plays",  len([b for b in bets if 6.0 <= b["rating"] < 8.0]))
k5.metric("Best +EV",        f"+{max((b['ev_pct'] for b in bets), default=0):.1f}%")

st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    f"  📊  TODAY'S BETS ({len(bets)})  ",
    f"  🎯  PLAYER PROPS ({len(props)})  ",
    f"  🗓  ALL GAMES ({len(games)})  ",
])

with tab1:
    if not bets:
        st.markdown('<div style="text-align:center;padding:3rem;color:#5a6a7a"><div style="font-size:2rem">🔍</div><div style="margin-top:0.5rem">No plays meet the minimum threshold today.</div></div>', unsafe_allow_html=True)
    else:
        c1, c2 = st.columns(2)
        with c1:
            bet_filter = st.selectbox("Bet Type", ["All", "Moneyline", "Total"])
        with c2:
            min_r = st.selectbox("Min Rating", [5.5, 6.0, 7.0, 8.0])
        filtered = [b for b in bets if b["rating"] >= min_r and (bet_filter == "All" or b["type"] == bet_filter)]
        filtered.sort(key=lambda x: x["rating"], reverse=True)
        strong = [b for b in filtered if b["rating"] >= 8.0]
        if strong:
            st.markdown('<div style="font-family:\'Bebas Neue\',cursive;font-size:1.5rem;letter-spacing:0.08em;margin:1.5rem 0 0.8rem">🔥 STRONG PLAYS</div>', unsafe_allow_html=True)
            for b in strong: render_bet(b)
        solid = [b for b in filtered if 6.0 <= b["rating"] < 8.0]
        if solid:
            st.markdown('<div style="font-family:\'Bebas Neue\',cursive;font-size:1.5rem;letter-spacing:0.08em;margin:1.5rem 0 0.8rem">✅ SOLID VALUE</div>', unsafe_allow_html=True)
            for b in solid: render_bet(b)
        marginal = [b for b in filtered if b["rating"] < 6.0]
        if marginal:
            st.markdown('<div style="font-family:\'Bebas Neue\',cursive;font-size:1.5rem;letter-spacing:0.08em;margin:1.5rem 0 0.8rem">🔵 MARGINAL</div>', unsafe_allow_html=True)
            for b in marginal: render_bet(b)
        if not filtered:
            st.info("No bets match the current filter.")

with tab2:
    if not props:
        st.markdown('<div style="text-align:center;padding:3rem;color:#5a6a7a"><div style="font-size:2rem">🎯</div><div style="margin-top:0.5rem">No props available — PrizePicks lines post around 10 AM ET.</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-family:\'Bebas Neue\',cursive;font-size:1.5rem;letter-spacing:0.08em;margin-bottom:1rem">⭐ TOP PLAYER PROPS</div>', unsafe_allow_html=True)
        for i, prop in enumerate(props): render_prop(prop, i)

with tab3:
    if not games:
        st.markdown('<div style="text-align:center;padding:3rem;color:#5a6a7a">No game data available.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-family:\'Bebas Neue\',cursive;font-size:1.5rem;letter-spacing:0.08em;margin-bottom:1rem">🗓 FULL SLATE</div>', unsafe_allow_html=True)
        search = st.text_input("Filter by team", placeholder="e.g. Yankees, LAD, NYM…")
        shown = [g for g in games if not search or search.lower() in g["home_team"].lower() or search.lower() in g["away_team"].lower() or search.lower() in g.get("home_abbr","").lower() or search.lower() in g.get("away_abbr","").lower()]
        for g in shown: render_game(g)

st.markdown('<div style="margin-top:3rem;padding:1rem 1.5rem;background:rgba(255,59,59,0.06);border:1px solid rgba(255,59,59,0.2);border-radius:10px;font-size:0.7rem;color:#5a6a7a;line-height:1.8">⚠️ <strong style="color:#e8edf2">DISCLAIMER:</strong> For educational purposes only. No content constitutes financial or betting advice. Bet responsibly. If you have a gambling problem, call 1-800-522-4700.</div>', unsafe_allow_html=True)
