import json
import streamlit as st
from datetime import datetime, date
from pathlib import Path

st.set_page_config(page_title="MLB Edge", page_icon="⚾", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Mono:wght@300;400;500&family=Cormorant+Garamond:ital,wght@0,300;0,600;1,300&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #050709 !important;
    color: #e2ddd6 !important;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 60% 40% at 80% 0%, rgba(255,200,60,0.07) 0%, transparent 55%),
        radial-gradient(ellipse 50% 30% at 0% 100%, rgba(0,255,180,0.05) 0%, transparent 50%),
        #050709 !important;
}
[data-testid="stHeader"] { background: transparent !important; }
.block-container { padding: 2.5rem 3rem !important; max-width: 1500px !important; }
* { font-family: 'DM Mono', monospace !important; }

[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0d1117 0%, #111820 100%) !important;
    border: 1px solid rgba(255,200,60,0.15) !important;
    border-radius: 16px !important;
    padding: 1.2rem 1.4rem !important;
    position: relative !important;
    overflow: hidden !important;
}
[data-testid="metric-container"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,200,60,0.6), transparent);
}
[data-testid="metric-container"] label {
    color: rgba(255,200,60,0.6) !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Playfair Display', serif !important;
    font-size: 2.4rem !important;
    color: #ffc83c !important;
    font-weight: 700 !important;
}
[data-baseweb="tab-list"] {
    background: #0d1117 !important;
    border: 1px solid rgba(255,200,60,0.12) !important;
    border-radius: 12px !important;
    padding: 5px !important;
    gap: 4px !important;
}
[data-baseweb="tab"] {
    color: rgba(226,221,214,0.4) !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    border-radius: 8px !important;
}
[aria-selected="true"] {
    background: linear-gradient(135deg, #1a1408, #201a08) !important;
    color: #ffc83c !important;
    border: 1px solid rgba(255,200,60,0.3) !important;
}
hr { border-color: rgba(255,200,60,0.1) !important; }
div[data-testid="stSelectbox"] > div > div {
    background: #0d1117 !important;
    border: 1px solid rgba(255,200,60,0.2) !important;
    color: #e2ddd6 !important;
    border-radius: 10px !important;
}
input[type="text"] {
    background: #0d1117 !important;
    border: 1px solid rgba(255,200,60,0.2) !important;
    color: #e2ddd6 !important;
    border-radius: 10px !important;
}
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
    if r >= 8.0: return "#00ffb3"
    if r >= 6.0: return "#ffc83c"
    return "#a78bfa"

def ev_color(ev):
    if ev >= 8: return "#00ffb3"
    if ev >= 4: return "#ffc83c"
    return "#a78bfa"

def render_bet(bet):
    rc = rating_color(bet["rating"])
    ec = ev_color(bet["ev_pct"])
    mo = bet.get("market_odds_fmt", str(bet.get("market_odds", "")))
    fo = bet.get("fair_odds_fmt", str(bet.get("fair_odds", "")))
    btype = bet.get("type", "")
    icon = "◆" if btype == "Moneyline" else "◈"
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#111820 100%);
                border:1px solid rgba(255,200,60,0.12);border-radius:18px;
                padding:1.5rem 1.8rem;margin-bottom:1.2rem;position:relative;overflow:hidden;">
      <div style="position:absolute;top:0;left:0;right:0;height:2px;
                  background:linear-gradient(90deg,transparent,{rc},transparent)"></div>
      <div style="position:absolute;top:-60px;right:-60px;width:180px;height:180px;
                  border-radius:50%;background:radial-gradient(circle,rgba(255,200,60,0.04),transparent);
                  pointer-events:none"></div>
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.2rem">
        <div>
          <div style="font-family:'Playfair Display',serif;font-size:1.5rem;font-weight:700;
                      letter-spacing:0.03em;color:#e2ddd6">{bet['matchup']}</div>
          <div style="font-size:0.65rem;color:rgba(255,200,60,0.5);margin-top:0.3rem;
                      letter-spacing:0.2em;text-transform:uppercase">{icon} {btype} &nbsp;·&nbsp; {bet['game_time']}</div>
        </div>
        <div style="text-align:center;background:rgba(0,0,0,0.3);border:1px solid {rc}33;
                    border-radius:50%;width:58px;height:58px;display:flex;flex-direction:column;
                    align-items:center;justify-content:center;flex-shrink:0">
          <div style="font-family:'Playfair Display',serif;font-size:1.4rem;font-weight:700;
                      color:{rc};line-height:1">{bet['rating']}</div>
          <div style="font-size:0.5rem;color:rgba(226,221,214,0.3);letter-spacing:0.1em">RATING</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:2.2fr 1fr 1fr 1.2fr 1fr;gap:1.2rem;
                  padding:1rem 0;border-top:1px solid rgba(255,200,60,0.08);
                  border-bottom:1px solid rgba(255,200,60,0.08);margin-bottom:0.9rem">
        <div>
          <div style="font-size:0.58rem;color:rgba(255,200,60,0.45);text-transform:uppercase;
                      letter-spacing:0.2em;margin-bottom:0.4rem">Suggested Bet</div>
          <div style="font-family:'Playfair Display',serif;font-size:1.35rem;font-weight:700;
                      color:#e2ddd6">{bet['bet']}</div>
          <div style="font-size:0.63rem;color:rgba(226,221,214,0.35);margin-top:0.2rem">{bet.get('pitcher_note','')}</div>
        </div>
        <div>
          <div style="font-size:0.58rem;color:rgba(255,200,60,0.45);text-transform:uppercase;
                      letter-spacing:0.2em;margin-bottom:0.6rem">Market</div>
          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                      border-radius:8px;padding:0.3rem 0.6rem;display:inline-block;
                      font-size:1rem;color:#e2ddd6">{mo}</div>
        </div>
        <div>
          <div style="font-size:0.58rem;color:rgba(255,200,60,0.45);text-transform:uppercase;
                      letter-spacing:0.2em;margin-bottom:0.6rem">Fair Odds</div>
          <div style="background:rgba(0,255,179,0.06);border:1px solid rgba(0,255,179,0.25);
                      border-radius:8px;padding:0.3rem 0.6rem;display:inline-block;
                      font-size:1rem;color:#00ffb3">{fo}</div>
        </div>
        <div>
          <div style="font-size:0.58rem;color:rgba(255,200,60,0.45);text-transform:uppercase;
                      letter-spacing:0.2em;margin-bottom:0.3rem">Edge</div>
          <div style="font-family:'Playfair Display',serif;font-size:1.5rem;font-weight:700;
                      color:{ec}">+{bet['ev_pct']}%</div>
        </div>
        <div>
          <div style="font-size:0.58rem;color:rgba(255,200,60,0.45);text-transform:uppercase;
                      letter-spacing:0.2em;margin-bottom:0.3rem">Win Prob</div>
          <div style="font-family:'Playfair Display',serif;font-size:1.5rem;font-weight:700;
                      color:#e2ddd6">{bet.get('our_prob','--')}%</div>
        </div>
      </div>
      <div style="font-size:0.7rem;color:rgba(226,221,214,0.4);line-height:1.7;
                  font-style:italic;font-family:'Cormorant Garamond',serif;font-size:0.85rem">
        ◈ &nbsp;{bet['logic']}
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_prop(prop, rank):
    icons = ["I", "II", "III", "IV", "V"]
    rc = rating_color(prop["rating"])
    ec = ev_color(prop["ev_pct"])
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1117,#0f1520);
                border:1px solid rgba(167,139,250,0.15);border-radius:16px;
                padding:1.1rem 1.4rem;margin-bottom:0.9rem;position:relative;overflow:hidden">
      <div style="position:absolute;top:0;left:0;bottom:0;width:2px;
                  background:linear-gradient(180deg,transparent,#a78bfa,transparent)"></div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div style="display:flex;align-items:center;gap:1rem">
          <div style="font-family:'Playfair Display',serif;font-size:1.1rem;font-weight:700;
                      color:rgba(167,139,250,0.4);min-width:24px">{icons[rank] if rank < 5 else 'V'}</div>
          <div>
            <div style="font-size:0.95rem;color:#e2ddd6;font-weight:500">{prop['player']}
              <span style="color:rgba(226,221,214,0.3);font-size:0.75rem;font-weight:400">
                {prop.get('team','')}</span></div>
            <div style="font-size:0.6rem;color:#a78bfa;text-transform:uppercase;
                        letter-spacing:0.18em;margin-top:0.15rem">{prop['prop_type']}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:1.4rem">
          <div style="text-align:center">
            <div style="font-size:0.55rem;color:rgba(255,200,60,0.4);text-transform:uppercase;letter-spacing:0.18em">Bet</div>
            <div style="font-size:0.85rem;color:#e2ddd6;margin-top:0.2rem">{prop['bet']}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:0.55rem;color:rgba(255,200,60,0.4);text-transform:uppercase;letter-spacing:0.18em">Odds</div>
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                        border-radius:7px;padding:0.2rem 0.5rem;margin-top:0.2rem;font-size:0.9rem">
              {prop.get('odds_fmt', prop['odds'])}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:0.55rem;color:rgba(255,200,60,0.4);text-transform:uppercase;letter-spacing:0.18em">Edge</div>
            <div style="font-family:'Playfair Display',serif;font-size:1.2rem;font-weight:700;
                        color:{ec};margin-top:0.1rem">+{prop['ev_pct']}%</div>
          </div>
          <div style="background:rgba(0,0,0,0.3);border:1px solid {rc}44;border-radius:50%;
                      width:44px;height:44px;display:flex;flex-direction:column;align-items:center;
                      justify-content:center;flex-shrink:0">
            <div style="font-family:'Playfair Display',serif;font-size:1.1rem;font-weight:700;
                        color:{rc};line-height:1">{prop['rating']}</div>
          </div>
        </div>
      </div>
      <div style="font-size:0.75rem;color:rgba(226,221,214,0.35);margin-top:0.7rem;
                  padding-top:0.6rem;border-top:1px solid rgba(167,139,250,0.08);
                  font-family:'Cormorant Garamond',serif;font-style:italic">
        ◈ &nbsp;{prop['logic']}
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_game(game):
    hp = game.get("home_win_prob", 50)
    ap = game.get("away_win_prob", 50)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1117,#0f1318);
                border:1px solid rgba(255,200,60,0.1);border-radius:14px;
                padding:1rem 1.3rem;margin-bottom:0.8rem">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-family:'Playfair Display',serif;font-size:1.15rem;font-weight:700;
                      letter-spacing:0.03em;color:#e2ddd6">
            {game['away_abbr']} <span style="color:rgba(255,200,60,0.3)">@</span> {game['home_abbr']}
          </div>
          <div style="font-size:0.62rem;color:rgba(255,200,60,0.4);margin-top:0.25rem;
                      letter-spacing:0.15em;text-transform:uppercase">
            {game['game_time']} &nbsp;·&nbsp; {game.get('venue','')}
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:0.55rem;color:rgba(255,200,60,0.4);text-transform:uppercase;letter-spacing:0.18em">Win Probability</div>
          <div style="font-family:'Playfair Display',serif;font-size:0.95rem;margin-top:0.2rem">
            {game['away_abbr']} <span style="color:#00ffb3">{ap}%</span>
            <span style="color:rgba(255,200,60,0.2)"> / </span>
            {game['home_abbr']} <span style="color:#00ffb3">{hp}%</span>
          </div>
        </div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border-radius:3px;height:3px;margin:0.7rem 0;overflow:hidden">
        <div style="width:{hp}%;height:100%;background:linear-gradient(90deg,#ffc83c,#00ffb3);border-radius:3px"></div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:0.35rem">
        <span style="background:rgba(255,200,60,0.05);border:1px solid rgba(255,200,60,0.1);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(255,200,60,0.5)">SP(H) <span style="color:#e2ddd6">{game['home_pitcher'][:16]}</span></span>
        <span style="background:rgba(255,200,60,0.05);border:1px solid rgba(255,200,60,0.1);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(255,200,60,0.5)">SP(A) <span style="color:#e2ddd6">{game['away_pitcher'][:16]}</span></span>
        <span style="background:rgba(255,200,60,0.05);border:1px solid rgba(255,200,60,0.1);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(255,200,60,0.5)">xFIP(H) <span style="color:#e2ddd6">{game.get('home_xfip','--')}</span></span>
        <span style="background:rgba(255,200,60,0.05);border:1px solid rgba(255,200,60,0.1);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(255,200,60,0.5)">xFIP(A) <span style="color:#e2ddd6">{game.get('away_xfip','--')}</span></span>
        <span style="background:rgba(255,200,60,0.05);border:1px solid rgba(255,200,60,0.1);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(255,200,60,0.5)">wRC+(H) <span style="color:#e2ddd6">{game.get('home_wrc','--')}</span></span>
        <span style="background:rgba(255,200,60,0.05);border:1px solid rgba(255,200,60,0.1);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(255,200,60,0.5)">wRC+(A) <span style="color:#e2ddd6">{game.get('away_wrc','--')}</span></span>
        <span style="background:rgba(0,255,179,0.05);border:1px solid rgba(0,255,179,0.15);border-radius:6px;padding:0.12rem 0.5rem;font-size:0.62rem;color:rgba(0,255,179,0.6)">Proj O/U <span style="color:#00ffb3">{game.get('proj_total','--')}</span></span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── MAIN ──────────────────────────────────────────────────────────────────────
data = load_data()
today_str = date.today().strftime("%A, %B %d, %Y")
gen_str = "—"
if data:
    try:
        gen_dt = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
        gen_str = gen_dt.strftime("%I:%M %p UTC")
    except Exception:
        gen_str = data.get("generated_at", "")[:16]

# ── Header ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;
            margin-bottom:2.5rem;padding-bottom:2rem;
            border-bottom:1px solid rgba(255,200,60,0.12)">
  <div>
    <div style="font-family:'Playfair Display',serif;font-size:3.8rem;font-weight:900;
                line-height:1;letter-spacing:-0.01em">
      <span style="color:#e2ddd6">MLB</span><span style="color:#ffc83c">EDGE</span>
    </div>
    <div style="font-size:0.62rem;color:rgba(255,200,60,0.4);letter-spacing:0.3em;
                text-transform:uppercase;margin-top:0.5rem;font-family:'DM Mono',monospace">
      Sabermetric Betting Intelligence &nbsp;·&nbsp; Est. 2026
    </div>
  </div>
  <div style="text-align:right;padding-top:0.5rem">
    <div style="display:inline-flex;align-items:center;gap:0.5rem;
                background:rgba(0,255,179,0.07);border:1px solid rgba(0,255,179,0.2);
                border-radius:30px;padding:0.3rem 0.9rem;
                font-size:0.62rem;color:#00ffb3;letter-spacing:0.18em;text-transform:uppercase">
      <div style="width:6px;height:6px;border-radius:50%;background:#00ffb3"></div>
      Live Data
    </div>
    <div style="font-family:'Playfair Display',serif;font-size:1rem;color:#e2ddd6;
                margin-top:0.6rem;font-style:italic">{today_str}</div>
    <div style="font-size:0.6rem;color:rgba(255,200,60,0.35);margin-top:0.2rem;
                letter-spacing:0.15em">Model run: {gen_str}</div>
  </div>
</div>
""", unsafe_allow_html=True)

if not data:
    st.markdown("""
    <div style="text-align:center;padding:5rem;color:rgba(226,221,214,0.3)">
      <div style="font-family:'Playfair Display',serif;font-size:4rem;color:rgba(255,200,60,0.15)">⚾</div>
      <div style="font-family:'Playfair Display',serif;font-size:2rem;margin-top:1rem;color:rgba(226,221,214,0.5)">
        Awaiting Today's Analysis</div>
      <div style="margin-top:0.7rem;font-size:0.78rem;letter-spacing:0.1em;color:rgba(255,200,60,0.3)">
        Algorithm runs daily at 11:00 AM ET</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

bets  = data.get("bets", [])
props = data.get("props", [])
games = data.get("games", [])
best_ev = max((b["ev_pct"] for b in bets), default=0)

# ── KPIs ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Games Today",      data.get("game_count", 0))
k2.metric("Total Bets",       len(bets))
k3.metric("Strong Plays",     len([b for b in bets if b["rating"] >= 8.0]))
k4.metric("Solid Plays",      len([b for b in bets if 6.0 <= b["rating"] < 8.0]))
k5.metric("Best Edge",        f"+{best_ev:.1f}%")

st.markdown("<div style='margin:2rem 0 0'></div>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    f"  ◆  TODAY'S BETS  ({len(bets)})  ",
    f"  ◈  PLAYER PROPS  ({len(props)})  ",
    f"  ◉  ALL GAMES  ({len(games)})  ",
])

with tab1:
    if not bets:
        st.markdown("""
        <div style="text-align:center;padding:4rem;color:rgba(226,221,214,0.25)">
          <div style="font-family:'Playfair Display',serif;font-size:1.5rem;margin-bottom:0.5rem">No plays today</div>
          <div style="font-size:0.72rem;letter-spacing:0.1em">No bets meet the minimum threshold.</div>
        </div>""", unsafe_allow_html=True)
    else:
        c1, c2 = st.columns(2)
        with c1:
            bet_filter = st.selectbox("Bet Type", ["All", "Moneyline", "Run Line", "Total"])
        with c2:
            min_r = st.selectbox("Minimum Rating", [5.5, 6.0, 7.0, 8.0])

        filtered = [b for b in bets if b["rating"] >= min_r
                    and (bet_filter == "All" or b["type"] == bet_filter)]
        filtered.sort(key=lambda x: x["rating"], reverse=True)

        strong = [b for b in filtered if b["rating"] >= 8.0]
        if strong:
            st.markdown("""<div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                font-weight:700;letter-spacing:0.03em;margin:2rem 0 1rem;color:#00ffb3">
                Strong Plays <span style="font-size:0.9rem;font-weight:400;color:rgba(0,255,179,0.4);
                font-family:'DM Mono',monospace;letter-spacing:0.12em">RATING ≥ 8.0</span></div>""",
                unsafe_allow_html=True)
            for b in strong: render_bet(b)

        solid = [b for b in filtered if 6.0 <= b["rating"] < 8.0]
        if solid:
            st.markdown("""<div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                font-weight:700;letter-spacing:0.03em;margin:2rem 0 1rem;color:#ffc83c">
                Solid Value <span style="font-size:0.9rem;font-weight:400;color:rgba(255,200,60,0.4);
                font-family:'DM Mono',monospace;letter-spacing:0.12em">RATING 6.0–7.9</span></div>""",
                unsafe_allow_html=True)
            for b in solid: render_bet(b)

        marginal = [b for b in filtered if b["rating"] < 6.0]
        if marginal:
            st.markdown("""<div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                font-weight:700;letter-spacing:0.03em;margin:2rem 0 1rem;color:#a78bfa">
                Marginal <span style="font-size:0.9rem;font-weight:400;color:rgba(167,139,250,0.4);
                font-family:'DM Mono',monospace;letter-spacing:0.12em">RATING 5.5–5.9</span></div>""",
                unsafe_allow_html=True)
            for b in marginal: render_bet(b)

        if not filtered:
            st.info("No bets match the current filter.")

with tab2:
    if not props:
        st.markdown("""
        <div style="text-align:center;padding:4rem;color:rgba(226,221,214,0.25)">
          <div style="font-family:'Playfair Display',serif;font-size:1.5rem;margin-bottom:0.5rem">No props yet</div>
          <div style="font-size:0.72rem;letter-spacing:0.1em">PrizePicks lines post around 10 AM ET.</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div style="display:flex;align-items:center;gap:1rem;margin:1.5rem 0 1.2rem">
          <div style="font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;color:#a78bfa">
            Top Player Props</div>
          <div style="background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.2);
                      border-radius:20px;padding:0.2rem 0.7rem;font-size:0.58rem;color:rgba(167,139,250,0.7);
                      letter-spacing:0.18em;text-transform:uppercase">PrizePicks · Free</div>
        </div>""", unsafe_allow_html=True)
        for i, prop in enumerate(props):
            render_prop(prop, i)

with tab3:
    if not games:
        st.markdown('<div style="text-align:center;padding:4rem;color:rgba(226,221,214,0.25)">No game data.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown("""<div style="font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;
            color:#ffc83c;margin:1.5rem 0 1.2rem">Full Slate</div>""", unsafe_allow_html=True)
        search = st.text_input("Filter by team", placeholder="e.g. Yankees, LAD, NYM…")
        shown = [g for g in games if not search
                 or search.lower() in g["home_team"].lower()
                 or search.lower() in g["away_team"].lower()
                 or search.lower() in g.get("home_abbr","").lower()
                 or search.lower() in g.get("away_abbr","").lower()]
        for g in shown:
            render_game(g)

st.markdown("""
<div style="margin-top:4rem;padding:1.2rem 1.8rem;
            background:rgba(255,50,50,0.04);border:1px solid rgba(255,50,50,0.12);
            border-radius:14px;font-size:0.68rem;color:rgba(226,221,214,0.3);line-height:2;
            letter-spacing:0.05em">
  ⚠ &nbsp;<strong style="color:rgba(226,221,214,0.5)">Disclaimer:</strong>
  For educational purposes only. No content constitutes financial or betting advice.
  Past model performance does not guarantee future results.
  Bet responsibly — if you have a gambling problem, call 1-800-522-4700.
</div>
""", unsafe_allow_html=True)
