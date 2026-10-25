"""Build site/analytics.html: standalone, self-contained IPTC Kabaddi Analytics & Prediction Dashboard.

Matches the exact design system, typography, and aesthetic of site/index.html:
  - --paper: #FBFBF8
  - --ink: #1B1E23
  - --green: #1C5E41
  - --panel: #14161B
  - Fonts: IBM Plex Sans, IBM Plex Sans Condensed, IBM Plex Mono
  - .sheet, .sheet-h, .fields, .btn, .btn-dark, .btn-line, .code, .tab-bar

No fetch(), no CDN, works directly from file:// or any browser.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"


def main():
    analytics_json_path = DATA_DIR / "analytics_usecase.json"
    if not analytics_json_path.exists():
        print("analytics_usecase.json not found, running analytics pipeline first...")
        from analytics.pipeline import run_analytics_pipeline
        run_analytics_pipeline(ROOT)

    analytics_data = json.loads(analytics_json_path.read_text(encoding="utf-8"))
    inlined_data = json.dumps(analytics_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    html_content = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analytics &amp; Predictor · Raid Replay</title>
<meta name="description" content="Downstream AI game prediction, real-time win probability, and player intelligence powered by standardized IPTC Sport Schema Kabaddi data.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='2' y='2' width='28' height='28' fill='%23FBFBF8' stroke='%231B1E23' stroke-width='3'/%3E%3Cpath d='M16 2v28' stroke='%231B1E23' stroke-width='3'/%3E%3Ccircle cx='9' cy='16' r='3.6' fill='%231C5E41'/%3E%3C/svg%3E">
<style>
:root {{
  --paper:#FBFBF8; --white:#FFFFFF; --ink:#1B1E23; --ink2:#2F3339; --muted:#50555D; --rule:#C9CCD1; --rule2:#E2E4E7; --code:#F3F4F1;
  --green:#1C5E41; --green-bg:#E3F1E8; --bad:#B4232F; --bad-bg:#FDF0F0;
  --gold:#946C00; --gold-bg:#FEF8E7;
  --panel:#14161B;
  --sans:"IBM Plex Sans","Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;
  --cond:"IBM Plex Sans Condensed","Arial Narrow","Segoe UI",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  color-scheme: light;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; -webkit-text-size-adjust:100%; }}
body {{
  margin:0; font-family:var(--sans); color:var(--ink); background:var(--paper);
  line-height:1.55; font-size:16.5px; -webkit-font-smoothing:antialiased; overflow-x:hidden;
}}
a {{ color:inherit; text-decoration:none; }}
a:hover {{ color:var(--green); }}
code {{ font-family:var(--mono); font-size:.88em; background:var(--code); padding:.05em .35em; color:var(--ink); }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 28px; }}
h1,h2,h3 {{ margin:0; line-height:1.15; }}
h1 {{ font:700 clamp(40px,5.2vw,58px)/1 var(--cond); letter-spacing:-.01em; }}
h2 {{ font:700 clamp(26px,3vw,34px)/1.15 var(--cond); letter-spacing:-.005em; max-width:820px; margin-bottom:12px; }}
h3 {{ font-size:18px; font-weight:700; font-family:var(--cond); }}
.eyebrow {{ font:600 12px var(--mono); letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 10px; }}
.intro {{ font-size:17px; color:var(--ink2); max-width:740px; margin:0 0 32px; }}

/* Navigation */
.nav {{ position:fixed; inset:0 0 auto 0; z-index:50; background:rgba(251,251,248,.96); border-bottom:1.5px solid var(--ink); }}
.nav-in {{ display:flex; align-items:center; gap:28px; height:60px; }}
.brand {{ display:flex; align-items:center; gap:10px; font:700 18px var(--cond); letter-spacing:.01em; text-decoration:none; color:var(--ink); }}
.logo {{ width:24px; height:24px; flex:none; color:var(--ink); }}
.links {{ display:flex; gap:22px; margin-left:auto; }}
.links a {{ text-decoration:none; font-weight:600; font-size:14.5px; color:var(--ink2); }}
.links a.active {{ color:var(--green); border-bottom:2px solid var(--green); }}

/* Buttons */
.btn {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:44px; padding:0 20px; font-weight:650; font-size:15px; text-decoration:none; border:1.5px solid var(--ink); cursor:pointer; transition:background .15s,color .15s; }}
.btn-sm {{ min-height:38px; padding:0 14px; font-size:14px; }}
.btn-dark {{ background:var(--ink); color:#fff; }}
.btn-dark:hover {{ background:var(--green); border-color:var(--green); color:#fff; }}
.btn-line {{ background:transparent; color:var(--ink); }}
.btn-line:hover {{ background:var(--ink); color:#fff; }}

/* Hero */
.hero {{ padding:104px 0 56px; border-bottom:1.5px solid var(--ink); }}
.kicker {{ font:600 12px var(--mono); letter-spacing:.05em; text-transform:uppercase; color:var(--muted); margin:0 0 14px; }}
.sub {{ font-size:17.5px; max-width:740px; color:var(--ink2); margin:16px 0 28px; }}

/* Sheet */
.sheet {{ border:1.5px solid var(--ink); background:var(--white); margin-bottom:24px; }}
.sheet-h {{ display:flex; align-items:baseline; justify-content:space-between; gap:14px; padding:10px 18px; border-bottom:1.5px solid var(--ink); }}
.sheet-h b {{ font:700 17px var(--cond); letter-spacing:.01em; }}
.sheet-h span {{ font:500 13px var(--mono); color:var(--muted); }}
.fields {{ margin:0; display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); border-bottom:1px solid var(--rule); }}
.fields div {{ padding:9px 16px; border-right:1px solid var(--rule); }}
.fields div:last-child {{ border-right:0; }}
.fields dt {{ font:600 11px var(--cond); letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
.fields dd {{ margin:2px 0 0; font-weight:600; font-size:15px; }}
.ok-badge {{ background:var(--green-bg); color:var(--green); padding:2px 8px; font:600 12.5px var(--mono); display:inline-block; }}
.bad-badge {{ background:var(--bad-bg); color:var(--bad); padding:2px 8px; font:600 12.5px var(--mono); display:inline-block; }}
.gold-badge {{ background:var(--gold-bg); color:var(--gold); padding:2px 8px; font:600 12.5px var(--mono); display:inline-block; }}

/* Hero stats strip */
.stats {{ display:grid; grid-template-columns:repeat(5,1fr); margin-top:32px; border-top:1.5px solid var(--ink); border-bottom:1px solid var(--rule); }}
.stat {{ padding:16px 18px 14px 0; border-right:1px solid var(--rule); margin-right:18px; }}
.stat:last-child {{ border-right:0; margin-right:0; }}
.stat b {{ display:block; font:600 28px var(--mono); letter-spacing:-.02em; font-variant-numeric:tabular-nums; }}
.stat span {{ font-size:13.5px; color:var(--muted); }}
.cta {{ display:flex; gap:10px; flex-wrap:wrap; margin:24px 0 0; }}

/* Sections */
.sec {{ padding:64px 0; border-bottom:1.5px solid var(--ink); }}
.sec:last-of-type {{ border-bottom:0; }}
.grid-2col {{ display:grid; grid-template-columns:1.2fr .8fr; gap:28px; align-items:start; }}

/* Controls and Selectors */
select.styled-sel {{
  font:600 14px var(--sans); padding:8px 14px; border:1.5px solid var(--ink);
  background:var(--white); color:var(--ink); cursor:pointer; outline:none;
}}
select.styled-sel:focus {{ border-color:var(--green); }}

/* Win probability display board */
.mat-wrap {{ background:var(--panel); color:#F4F3EE; padding:18px; border:1.5px solid var(--ink); }}
.board-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }}
.board-title {{ font:700 15px var(--cond); text-transform:uppercase; letter-spacing:.05em; color:#A9AEB8; }}
.wp-chart-box {{ position:relative; width:100%; height:240px; background:#0E1014; border:1px solid rgba(255,255,255,.15); }}
.wp-svg {{ width:100%; height:100%; display:block; }}

.scrub-box {{
  margin-top:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,.15);
  display:flex; flex-direction:column; gap:8px;
}}
.scrub-top {{ display:flex; justify-content:space-between; font:600 13.5px var(--mono); color:#A9AEB8; }}
.scrub-range {{
  width:100%; height:6px; background:#2A2E37; outline:none; cursor:pointer; accent-color:#8FE0B4;
}}
.score-tally {{
  display:grid; grid-template-columns:1fr auto auto 1fr; align-items:center; gap:12px;
  background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); padding:10px 14px; margin-top:8px;
}}
.score-tally .tm {{ font:600 15px var(--cond); }}
.score-tally .tm.away {{ text-align:right; }}
.score-tally em {{
  font:600 24px/1 var(--mono); font-style:normal; font-variant-numeric:tabular-nums;
  border:1px solid rgba(255,255,255,.3); padding:4px 8px; min-width:48px; text-align:center;
}}

/* Turning points list */
.tp-list {{ display:flex; flex-direction:column; max-height:430px; overflow-y:auto; }}
.tp-row {{
  padding:10px 14px; border-bottom:1px solid var(--rule); display:flex; justify-content:space-between;
  align-items:center; gap:10px; cursor:pointer; background:var(--white); transition:background .1s;
}}
.tp-row:hover {{ background:var(--code); }}
.tp-row:last-child {{ border-bottom:0; }}
.tp-main {{ min-width:0; }}
.tp-name {{ font-weight:600; font-size:14.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.tp-sub {{ font-size:12.5px; color:var(--muted); font-family:var(--mono); margin-top:2px; }}
.tp-swing {{ font:600 15px var(--mono); flex-shrink:0; }}

/* Next raid sandbox */
.pills {{ display:flex; border:1.5px solid var(--ink); width:fit-content; background:var(--white); }}
.pill-btn {{
  border:0; border-right:1px solid var(--rule); background:transparent; font:600 14px var(--sans);
  padding:8px 14px; cursor:pointer; color:var(--ink2);
}}
.pill-btn:last-child {{ border-right:0; }}
.pill-btn.active {{ background:var(--ink); color:#fff; }}

.toggle-wrap {{ display:flex; align-items:center; gap:10px; font-weight:600; font-size:14.5px; }}
.toggle-chk {{ width:18px; height:18px; accent-color:var(--ink); cursor:pointer; }}

/* Output card */
.ev-grid {{ display:grid; grid-template-columns:repeat(3,1fr); border-bottom:1.5px solid var(--ink); }}
.ev-cell {{ padding:12px 16px; border-right:1px solid var(--rule); text-align:center; }}
.ev-cell:last-child {{ border-right:0; }}
.ev-cell dt {{ font:600 11px var(--cond); text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
.ev-cell dd {{ margin:4px 0 0; font:600 24px/1 var(--mono); }}

.bar-row {{ padding:10px 16px; border-bottom:1px solid var(--rule2); }}
.bar-row:last-child {{ border-bottom:0; }}
.bar-labels {{ display:flex; justify-content:space-between; font-size:14px; font-weight:500; margin-bottom:4px; }}
.bar-labels b {{ font-family:var(--mono); font-size:13.5px; }}
.bar-track {{ width:100%; height:8px; background:var(--code); border:1px solid var(--rule); }}
.bar-fill {{ height:100%; background:var(--ink); transition:width .2s ease; }}

/* Tables */
.table-sheet {{ width:100%; border-collapse:collapse; font-size:14.5px; text-align:left; }}
.table-sheet th {{
  font:700 12px var(--mono); text-transform:uppercase; letter-spacing:.05em; background:var(--paper);
  color:var(--muted); padding:10px 14px; border-bottom:1.5px solid var(--ink);
}}
.table-sheet td {{
  padding:10px 14px; border-bottom:1px solid var(--rule2); color:var(--ink);
}}
.table-sheet tr:last-child td {{ border-bottom:0; }}
.table-sheet tr:hover td {{ background:var(--code); cursor:pointer; }}
.num-cell {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}

/* Code Snippet */
.code {{ margin:0; padding:14px 18px; font:13px/1.65 var(--mono); color:var(--ink); background:var(--code); border:1px solid var(--rule); overflow:auto; }}
.code .k {{ color:#1C5E41; font-weight:600; }}
.code .s {{ color:#8A4B0F; }}
.code .kw {{ color:var(--ink); font-weight:700; }}

/* Footer */
.foot {{ border-top:1.5px solid var(--ink); color:var(--muted); padding:36px 0 48px; background:var(--paper); }}
.foot-in {{ display:grid; gap:14px; }}
.foot-brand {{ display:flex; gap:12px; align-items:center; color:var(--ink); }}
.foot-brand b {{ display:block; font:700 17px var(--cond); }}
.foot-brand span {{ font-size:14px; color:var(--muted); }}
.foot-note {{ font-size:13.5px; max-width:820px; margin:0; }}

@media (max-width: 900px) {{
  .grid-2col {{ grid-template-columns:1fr; }}
  .stats {{ grid-template-columns:repeat(2,1fr); }}
  .links {{ display:none; }}
}}
</style>
</head>
<body>

<!-- NAVIGATION -->
<header class="nav" id="nav">
  <div class="wrap nav-in">
    <a class="brand" href="index.html" aria-label="Raid Replay home">
      <svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><rect x="2" y="2" width="28" height="28" fill="none" stroke="currentColor" stroke-width="3"/><path d="M16 2v28" stroke="currentColor" stroke-width="3"/><circle cx="9" cy="16" r="3.6" fill="#1C5E41"/></svg>
      <span>Raid Replay</span>
    </a>
    <nav class="links" aria-label="Sections">
      <a href="index.html#how">How it works</a>
      <a href="index.html#demo">Live demo</a>
      <a href="analytics.html" class="active">Analytics &amp; Predictor</a>
    </nav>
    <a class="btn btn-sm btn-dark" href="index.html#demo">Watch the replay</a>
  </div>
</header>

<main id="top">

<!-- HERO -->
<section class="hero">
  <div class="wrap">
    <p class="kicker">IEEE CS Confluence Buildathon · Track: Lossless · Team Byte Tackle</p>
    <h1>Analytics &amp; Predictor</h1>
    <p class="sub">
      Proof of standard utility: how broadcasters, fantasy platforms, and analytics engines consume converted <strong>IPTC Sport Schema</strong> data. Because kabaddi data is modeled losslessly into RDF, downstream models can compute real-time in-game win probabilities, tactical raid outcome predictions, and player leaderboards directly from the triples.
    </p>

    <!-- Match Sheet Style Metadata -->
    <div class="sheet" aria-label="Dataset and Model Summary">
      <div class="sheet-h">
        <b>Downstream IPTC Intelligence Pipeline</b>
        <span class="ok-badge">diff = 0 ✓ IPTC Validated</span>
      </div>
      <dl class="fields">
        <div><dt>Standard Source</dt><dd>IPTC Sport Schema JSON-LD</dd></div>
        <div><dt>Ontology Plugin</dt><dd>kabaddi_plugin/ (proposed)</dd></div>
        <div><dt>Validation Suite</dt><dd>IPTC SHACL + Kabaddi Shapes</dd></div>
        <div><dt>Engine Status</dt><dd>Trained &amp; Inlined</dd></div>
      </dl>
      <div style="padding:14px 18px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; background:var(--white);">
        <div style="font-size:14.5px; color:var(--ink2);">
          Model outputs generated directly from <code>data/jsonld/*.jsonld</code> actions. No external API or proprietary parser required.
        </div>
        <div class="cta" style="margin:0;">
          <a class="btn btn-sm btn-dark" href="#win-prob">Win Predictor</a>
          <a class="btn btn-sm btn-line" href="#raid-sim">Raid Simulator</a>
          <a class="btn btn-sm btn-line" href="#players">Player Stats</a>
        </div>
      </div>
    </div>

    <!-- Stats summary strip -->
    <div class="stats">
      <div class="stat"><b>5</b><span>Matches analyzed</span></div>
      <div class="stat"><b>355</b><span>Standardized raids</span></div>
      <div class="stat"><b>72</b><span>Profiled athletes</span></div>
      <div class="stat"><b style="color:var(--green);">0</b><span>DeepDiff loss</span></div>
      <div class="stat"><b style="color:var(--green);">100%</b><span>SHACL conformance</span></div>
    </div>
  </div>
</section>

<!-- SECTION 1: WIN PROBABILITY -->
<section class="sec" id="win-prob">
  <div class="wrap">
    <p class="eyebrow">Use Case 1 · Broadcaster Expectancy</p>
    <h2>Real-time win probability, raid by raid.</h2>
    <p class="intro">
      Broadcasters need real-time win probability curves during play. Our engine ingests <code>kab:homeScore</code>, <code>kab:awayScore</code>, <code>kab:clockSeconds</code>, and <code>kab:homeOnMat</code> to compute live win odds at every action.
    </p>

    <div style="margin-bottom:18px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
      <span style="font-weight:600; font-size:14.5px;">Select Match:</span>
      <select class="styled-sel" id="matchSelect">
        <!-- Populated dynamically -->
      </select>
    </div>

    <div class="grid-2col">
      <!-- Chart in mat-wrap -->
      <div class="mat-wrap">
        <div class="board-header">
          <span class="board-title">In-Game Win Probability Curve</span>
          <span style="font:600 12.5px var(--mono); color:#8FE0B4;" id="wpMatchBadge">Final · DKL26-F01</span>
        </div>

        <div class="wp-chart-box">
          <svg class="wp-svg" id="wpSvg" viewBox="0 0 680 240" preserveAspectRatio="none">
            <!-- Dynamic SVG Curve -->
          </svg>
        </div>

        <!-- Scrubber -->
        <div class="scrub-box">
          <div class="scrub-top">
            <span id="scrubSeqLbl">Sequence #1 / 89</span>
            <span id="scrubClockLbl" style="color:#F2D9A0;">Half 1 · 00:00</span>
          </div>
          <input type="range" class="scrub-range" id="wpScrubber" min="0" max="88" value="0">
          <div class="score-tally">
            <span class="tm" id="scHomeName">Home</span>
            <em id="scHomeScore">0</em>
            <em id="scAwayScore">0</em>
            <span class="tm away" id="scAwayName">Away</span>
          </div>
          <div style="display:flex; justify-content:space-between; font:600 13px var(--mono); margin-top:4px;">
            <span id="scActionText" style="color:#A9AEB8; max-width:440px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Match Start</span>
            <span id="scProbText" style="color:#8FE0B4;">Home Win Prob: 50.0%</span>
          </div>
        </div>
      </div>

      <!-- Turning Points in Sheet -->
      <div class="sheet" style="margin:0;">
        <div class="sheet-h">
          <b>Key Momentum Pivots</b>
          <span>&Delta; Win Prob &ge; 7%</span>
        </div>
        <div class="tp-list" id="tpList">
          <!-- Populated dynamically -->
        </div>
      </div>
    </div>
  </div>
</section>

<!-- SECTION 2: RAID SIMULATOR -->
<section class="sec" id="raid-sim">
  <div class="wrap">
    <p class="eyebrow">Use Case 2 · AI Tactical Sandbox</p>
    <h2>Predict the next raid outcome.</h2>
    <p class="intro">
      Teams and analysts simulate upcoming raids based on formation dynamics and player history. Rules like bonus line activation (&ge; 6 defenders) and super tackles (&le; 3 defenders) are strictly enforced from the IPTC vocabulary.
    </p>

    <div class="grid-2col">
      <!-- Input Controls -->
      <div class="sheet" style="margin:0;">
        <div class="sheet-h">
          <b>Raid Setup Parameters</b>
          <span>Tactical Inputs</span>
        </div>
        <div style="padding:18px; display:flex; flex-direction:column; gap:18px;">
          <div>
            <label style="display:block; font:600 12px var(--cond); text-transform:uppercase; color:var(--muted); margin-bottom:6px;">1. Select Raider</label>
            <select class="styled-sel" id="simRaiderSelect" style="width:100%;">
              <!-- Populated dynamically -->
            </select>
          </div>

          <div>
            <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
              <label style="font:600 12px var(--cond); text-transform:uppercase; color:var(--muted);">2. Defenders on Mat</label>
              <span id="defRuleTag" class="gold-badge">Bonus line active (6-7)</span>
            </div>
            <div class="pills" id="defPills">
              <button class="pill-btn" data-defs="1">1</button>
              <button class="pill-btn" data-defs="2">2</button>
              <button class="pill-btn" data-defs="3">3</button>
              <button class="pill-btn" data-defs="4">4</button>
              <button class="pill-btn" data-defs="5">5</button>
              <button class="pill-btn" data-defs="6">6</button>
              <button class="pill-btn active" data-defs="7">7</button>
            </div>
          </div>

          <div style="padding-top:12px; border-top:1px solid var(--rule2); display:flex; justify-content:space-between; align-items:center;">
            <div>
              <b style="font-size:15px; display:block;">Do-or-Die Raid</b>
              <span style="font-size:13px; color:var(--muted);">Raider must score or is automatically out</span>
            </div>
            <div class="toggle-wrap">
              <input type="checkbox" class="toggle-chk" id="simDodToggle">
            </div>
          </div>

          <div style="background:var(--code); border:1px solid var(--rule); padding:12px 14px; font-size:13.5px; color:var(--ink2);">
            <b>Tactical Note:</b> <span id="simCoachText">Standard raid: safe probing recommended.</span>
          </div>
        </div>
      </div>

      <!-- Output Expectations -->
      <div class="sheet" style="margin:0;">
        <div class="sheet-h">
          <b>Predicted Outcome Probabilities</b>
          <span class="ok-badge" id="simNetTag">Raider Advantaged</span>
        </div>

        <dl class="ev-grid">
          <div class="ev-cell">
            <dt>Expected Raid Pts (xRP)</dt>
            <dd id="simXrp">0.55</dd>
          </div>
          <div class="ev-cell">
            <dt>Expected Def Pts (xDP)</dt>
            <dd id="simXdp">0.30</dd>
          </div>
          <div class="ev-cell">
            <dt>Net Raid Value</dt>
            <dd id="simNetEv" style="color:var(--green);">+0.25</dd>
          </div>
        </dl>

        <div style="padding:10px 0;">
          <div class="bar-row">
            <div class="bar-labels"><span>Touch Points (1-2 pts)</span><b id="pTouchVal">20.0%</b></div>
            <div class="bar-track"><div class="bar-fill" id="pTouchFill" style="width:20%;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-labels"><span>Super Raid (&ge; 3 pts)</span><b id="pSrVal">7.0%</b></div>
            <div class="bar-track"><div class="bar-fill" id="pSrFill" style="width:7%; background:#D97706;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-labels"><span>Bonus Point (&ge; 6 defs)</span><b id="pBonusVal">18.0%</b></div>
            <div class="bar-track"><div class="bar-fill" id="pBonusFill" style="width:18%; background:var(--gold);"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-labels"><span>Empty Raid (Safe return)</span><b id="pEmptyVal">25.0%</b></div>
            <div class="bar-track"><div class="bar-fill" id="pEmptyFill" style="width:25%; background:#9CA3AF;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-labels"><span>Tackled Out (1 pt)</span><b id="pTackleVal">30.0%</b></div>
            <div class="bar-track"><div class="bar-fill" id="pTackleFill" style="width:30%; background:var(--bad);"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-labels"><span>Super Tackle (&le; 3 defs, 2 pts)</span><b id="pStVal">0.0%</b></div>
            <div class="bar-track"><div class="bar-fill" id="pStFill" style="width:0%; background:#991B1B;"></div></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- SECTION 3: PLAYER LEADERBOARDS -->
<section class="sec" id="players">
  <div class="wrap">
    <p class="eyebrow">Use Case 3 · Player Intelligence</p>
    <h2>League player statistics &amp; duels.</h2>
    <p class="intro">
      Computed directly by traversing RDF triples for <code>kab:Raid</code>, <code>kab:raider</code>, <code>kab:tackledBy</code>, and <code>kab:defenderOut</code> across all matches. Click any player to inspect their radar.
    </p>

    <!-- Spotlight Sheet -->
    <div class="sheet">
      <div class="sheet-h">
        <b>Player Spotlight</b>
        <span id="spotRole">Raider</span>
      </div>
      <div style="display:grid; grid-template-columns:auto 1fr; gap:24px; padding:20px; align-items:center;">
        <svg id="radarSvg" width="180" height="180" viewBox="0 0 200 200" style="border:1px solid var(--rule2); background:var(--paper);">
          <!-- Radar Chart -->
        </svg>
        <div>
          <h3 id="spotName" style="font-size:24px; margin-bottom:4px;">Vikram Malik</h3>
          <div style="font-size:13.5px; color:var(--muted); font-family:var(--mono); margin-bottom:14px;">
            <span id="spotTeam" style="font-weight:700; color:var(--ink);">CRM</span> · Jersey <span id="spotJersey">#1</span> · <span id="spotTotalPts">34</span> Career Points
          </div>
          <dl class="fields" style="border:1.5px solid var(--ink); border-radius:0;">
            <div><dt>Raid Strike Rate</dt><dd id="spotStrikeRate">1.22</dd></div>
            <div><dt>Super Raids</dt><dd id="spotSuperRaids">4</dd></div>
            <div><dt>Tackle Efficiency</dt><dd id="spotTackleEff">64.3%</dd></div>
            <div><dt>Do-or-Die Win %</dt><dd id="spotDodWin">100%</dd></div>
          </dl>
        </div>
      </div>
    </div>

    <div class="grid-2col">
      <!-- Top Raiders -->
      <div class="sheet" style="margin:0;">
        <div class="sheet-h">
          <b>Top Raiders by Strike Rate</b>
          <span>kab:raidPoints</span>
        </div>
        <table class="table-sheet" id="raidersTable">
          <thead>
            <tr>
              <th>Player</th>
              <th>Raids</th>
              <th>Points</th>
              <th>Strike Rate</th>
              <th>Super Raids</th>
            </tr>
          </thead>
          <tbody>
            <!-- Populated dynamically -->
          </tbody>
        </table>
      </div>

      <!-- Top Defenders -->
      <div class="sheet" style="margin:0;">
        <div class="sheet-h">
          <b>Top Defenders by Efficiency</b>
          <span>kab:tacklePoints</span>
        </div>
        <table class="table-sheet" id="defendersTable">
          <thead>
            <tr>
              <th>Defender</th>
              <th>Tackle Pts</th>
              <th>Tackles</th>
              <th>Super Tackles</th>
              <th>Efficiency</th>
            </tr>
          </thead>
          <tbody>
            <!-- Populated dynamically -->
          </tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<!-- SECTION 4: IPTC LINEAGE -->
<section class="sec" id="lineage">
  <div class="wrap">
    <p class="eyebrow">Proof of Lineage</p>
    <h2>Strictly derived from IPTC Sport Schema.</h2>
    <p class="intro">
      Every metric on this page is produced from our proposed kabaddi plugin. Below are the SPARQL queries and RDF predicates backing each calculation.
    </p>

    <div class="sheet">
      <div class="sheet-h">
        <b>IPTC SPARQL Query Map</b>
        <span class="ok-badge">Standard Compliant</span>
      </div>
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; padding:18px;">
        <div>
          <b style="font:700 15px var(--cond); display:block; margin-bottom:4px;">1. Raider Strike Rate</b>
          <p style="font-size:13px; color:var(--muted); margin:0 0 8px;">Triples: <code>kab:raider</code>, <code>kab:raidPoints</code>, <code>kab:touchPoints</code></p>
          <pre class="code"><code><span class="k">SELECT</span> ?raider (<span class="k">SUM</span>(?pts) <span class="k">AS</span> ?totalPts)
<span class="k">WHERE</span> {{
  ?raid a kab:Raid ;
        kab:raider ?raider ;
        kab:raidPoints ?pts .
}} <span class="k">GROUP BY</span> ?raider</code></pre>
        </div>
        <div>
          <b style="font:700 15px var(--cond); display:block; margin-bottom:4px;">2. Real-Time Win Expectancy</b>
          <p style="font-size:13px; color:var(--muted); margin:0 0 8px;">Triples: <code>kab:homeScore</code>, <code>kab:awayScore</code>, <code>kab:homeOnMat</code></p>
          <pre class="code"><code><span class="k">SELECT</span> ?seq ?hScore ?aScore ?hMat
<span class="k">WHERE</span> {{
  ?action a sport:Action ;
          sport:sequenceNumber ?seq ;
          kab:homeScore ?hScore ;
          kab:awayScore ?aScore ;
          kab:homeOnMat ?hMat .
}} <span class="k">ORDER BY</span> ?seq</code></pre>
        </div>
        <div>
          <b style="font:700 15px var(--cond); display:block; margin-bottom:4px;">3. Next-Raid Outcome Model</b>
          <p style="font-size:13px; color:var(--muted); margin:0 0 8px;">Triples: <code>kab:defendersOnMat</code>, <code>kab:doOrDie</code>, <code>kab:raidOutcome</code></p>
          <pre class="code"><code><span class="k">SELECT</span> ?defs ?dod ?outcome
<span class="k">WHERE</span> {{
  ?raid a kab:Raid ;
        kab:defendersOnMat ?defs ;
        kab:doOrDie ?dod ;
        kab:raidOutcome ?outcome .
}}</code></pre>
        </div>
      </div>
    </div>
  </div>
</section>

</main>

<!-- FOOTER -->
<footer class="foot">
  <div class="wrap foot-in">
    <div class="foot-brand">
      <svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><rect x="2" y="2" width="28" height="28" fill="none" stroke="currentColor" stroke-width="3"/><path d="M16 2v28" stroke="currentColor" stroke-width="3"/><circle cx="9" cy="16" r="3.6" fill="#1C5E41"/></svg>
      <div><b>Raid Replay</b><span>Kabaddi's open data standard — by Byte Tackle.</span></div>
    </div>
    <p class="foot-note">
      IEEE CS Confluence Buildathon · Track: <strong>Lossless – Bridging systems and formats</strong> · Team <strong>Byte Tackle</strong>.
      All analytics, win probabilities, and raid outcome models are evaluated directly on the converted IPTC Sport Schema files.
    </p>
    <div style="display:flex; gap:12px;">
      <a class="btn btn-sm btn-dark" href="index.html">Back to Main Replay</a>
      <a class="btn btn-sm btn-line" href="index.html#how">How it works</a>
    </div>
  </div>
</footer>

<script>
window.RR_ANALYTICS = {inlined_data};
</script>
<script>
// Match Dashboard Controller
(function() {{
  const data = window.RR_ANALYTICS;
  if (!data) return;

  const currentMatchId = "match3_final";
  let activeTimeline = data.timelines[currentMatchId] || [];
  let activeTurningPoints = data.turningPoints[currentMatchId] || [];

  // Match selector
  const matchSelect = document.getElementById("matchSelect");
  data.matches.forEach(m => {{
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.name || m.id;
    if (m.id === currentMatchId) opt.selected = true;
    matchSelect.appendChild(opt);
  }});

  matchSelect.addEventListener("change", (e) => {{
    const mId = e.target.value;
    activeTimeline = data.timelines[mId] || [];
    activeTurningPoints = data.turningPoints[mId] || [];
    document.getElementById("wpMatchBadge").textContent = mId;
    renderWinProbChart();
    renderTurningPoints();
    setupScrubber();
  }});

  // Win Probability SVG Chart
  function renderWinProbChart() {{
    const svg = document.getElementById("wpSvg");
    if (!svg || activeTimeline.length === 0) return;

    const N = activeTimeline.length;
    const W = 680, H = 240, padX = 14, padY = 20;
    const chartW = W - padX * 2, chartH = H - padY * 2;

    let pts = [];
    activeTimeline.forEach((pt, i) => {{
      const x = padX + (i / (N - 1)) * chartW;
      const y = padY + (1.0 - pt.homeWinProb) * chartH;
      pts.push([x, y]);
    }});

    const pathD = pts.reduce((acc, p, i) => acc + (i === 0 ? `M${{p[0]}},${{p[1]}}` : ` L${{p[0]}},${{p[1]}}`), "");
    const areaD = pathD + ` L${{pts[pts.length - 1][0]}},${{padY + chartH / 2}} L${{pts[0][0]}},${{padY + chartH / 2}} Z`;

    svg.innerHTML = `
      <line x1="${{padX}}" y1="${{padY}}" x2="${{W - padX}}" y2="${{padY}}" stroke="rgba(255,255,255,0.1)" stroke-dasharray="3"/>
      <line x1="${{padX}}" y1="${{padY + chartH / 2}}" x2="${{W - padX}}" y2="${{padY + chartH / 2}}" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>
      <line x1="${{padX}}" y1="${{padY + chartH}}" x2="${{W - padX}}" y2="${{padY + chartH}}" stroke="rgba(255,255,255,0.1)" stroke-dasharray="3"/>
      
      <text x="${{padX + 4}}" y="${{padY + 12}}" fill="#A9AEB8" font-size="10" font-family="monospace">HOME 100%</text>
      <text x="${{padX + 4}}" y="${{padY + chartH / 2 - 4}}" fill="#A9AEB8" font-size="10" font-family="monospace">50% TIE</text>
      <text x="${{padX + 4}}" y="${{padY + chartH - 4}}" fill="#A9AEB8" font-size="10" font-family="monospace">AWAY 100%</text>

      <path d="${{areaD}}" fill="#1C5E41" fill-opacity="0.25"/>
      <path d="${{pathD}}" fill="none" stroke="#8FE0B4" stroke-width="2.5" stroke-linecap="round"/>

      <line id="wpCursor" x1="${{pts[0][0]}}" y1="${{padY}}" x2="${{pts[0][0]}}" y2="${{padY + chartH}}" stroke="#FFB347" stroke-width="1.5" stroke-dasharray="3"/>
      <circle id="wpPoint" cx="${{pts[0][0]}}" cy="${{pts[0][1]}}" r="4.5" fill="#FFB347"/>
    `;

    svg.addEventListener("mousemove", (e) => {{
      const rect = svg.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const relX = (mouseX / rect.width) * W;
      const idx = Math.max(0, Math.min(N - 1, Math.round(((relX - padX) / chartW) * (N - 1))));
      updateScrubberIndex(idx);
    }});
  }}

  // Scrubber
  function setupScrubber() {{
    const scrubber = document.getElementById("wpScrubber");
    scrubber.max = activeTimeline.length - 1;
    scrubber.value = 0;
    updateScrubberIndex(0);

    scrubber.addEventListener("input", (e) => {{
      updateScrubberIndex(parseInt(e.target.value));
    }});
  }}

  function updateScrubberIndex(idx) {{
    const pt = activeTimeline[idx];
    if (!pt) return;

    document.getElementById("wpScrubber").value = idx;
    document.getElementById("scrubSeqLbl").textContent = `Sequence #${{pt.seq}} / ${{activeTimeline.length}}`;
    const mins = String(Math.floor(pt.clockSeconds / 60)).padStart(2, '0');
    const secs = String(pt.clockSeconds % 60).padStart(2, '0');
    document.getElementById("scrubClockLbl").textContent = `Half ${{pt.half}} · ${{mins}}:${{secs}}`;
    document.getElementById("scActionText").textContent = pt.label || "Action";
    document.getElementById("scHomeScore").textContent = pt.homeScore;
    document.getElementById("scAwayScore").textContent = pt.awayScore;
    const pPct = (pt.homeWinProb * 100).toFixed(1);
    document.getElementById("scProbText").textContent = `Home Win Prob: ${{pPct}}%`;

    const W = 680, padX = 14, padY = 20, chartW = W - padX * 2, chartH = 240 - padY * 2;
    const x = padX + (idx / (activeTimeline.length - 1)) * chartW;
    const y = padY + (1.0 - pt.homeWinProb) * chartH;
    const cursor = document.getElementById("wpCursor");
    const circle = document.getElementById("wpPoint");
    if (cursor) cursor.setAttribute("x1", x), cursor.setAttribute("x2", x);
    if (circle) circle.setAttribute("cx", x), circle.setAttribute("cy", y);
  }}

  // Turning points
  function renderTurningPoints() {{
    const tpList = document.getElementById("tpList");
    tpList.innerHTML = "";

    activeTurningPoints.slice(0, 8).forEach(tp => {{
      const row = document.createElement("div");
      row.className = "tp-row";
      const swingSign = tp.swingDelta > 0 ? "+" : "";
      const swingVal = swingSign + (tp.swingDelta * 100).toFixed(1) + "%";
      const badgeCls = tp.reason === "Super Raid" ? "gold-badge" : (tp.reason === "Super Tackle" ? "ok-badge" : "bad-badge");

      row.innerHTML = `
        <div class="tp-main">
          <div class="tp-name">${{tp.label}}</div>
          <div class="tp-sub"><span class="${{badgeCls}}">${{tp.reason}}</span> Seq #${{tp.seq}} · Score: ${{tp.homeScore}}-${{tp.awayScore}}</div>
        </div>
        <div class="tp-swing" style="color: ${{tp.swingDelta >= 0 ? "var(--green)" : "var(--bad)"}};">${{swingVal}}</div>
      `;

      row.addEventListener("click", () => {{
        const idx = activeTimeline.findIndex(t => t.seq === tp.seq);
        if (idx >= 0) updateScrubberIndex(idx);
      }});

      tpList.appendChild(row);
    }});
  }}

  // Next raid simulator
  const simRaiderSelect = document.getElementById("simRaiderSelect");
  const defPills = document.querySelectorAll(".pill-btn");
  const dodToggle = document.getElementById("simDodToggle");
  let selectedDefs = 7;

  const genOpt = document.createElement("option");
  genOpt.value = "generic";
  genOpt.textContent = "League Average Raider";
  simRaiderSelect.appendChild(genOpt);

  data.topRaiders.forEach(r => {{
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = `${{r.name}} (${{r.teamShort}} - Strike Rate: ${{r.raiding.strikeRate}})`;
    simRaiderSelect.appendChild(opt);
  }});

  defPills.forEach(btn => {{
    btn.addEventListener("click", () => {{
      defPills.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectedDefs = parseInt(btn.dataset.defs);
      runSimulation();
    }});
  }});

  simRaiderSelect.addEventListener("change", runSimulation);
  dodToggle.addEventListener("change", runSimulation);

  function runSimulation() {{
    const raiderId = simRaiderSelect.value;
    const isDod = dodToggle.checked;
    const grid = data.simulationGrid[raiderId] || data.simulationGrid["generic"];
    const defData = grid[String(selectedDefs)] || data.simulationGrid["generic"][String(selectedDefs)];
    const pred = isDod ? defData.doOrDie : defData.normal;

    const tag = document.getElementById("defRuleTag");
    if (selectedDefs >= 6) {{
      tag.className = "gold-badge";
      tag.textContent = "Bonus line active (6-7 defs)";
    }} else if (selectedDefs <= 3) {{
      tag.className = "ok-badge";
      tag.textContent = "Super tackle active (1-3 defs, 2 pts)";
    }} else {{
      tag.className = "gold-badge";
      tag.textContent = "Standard chains (4-5 defs)";
    }}

    document.getElementById("simXrp").textContent = pred.expectedRaidPoints.toFixed(2);
    document.getElementById("simXdp").textContent = pred.expectedDefencePoints.toFixed(2);
    const net = pred.netExpectedPoints;
    const netEl = document.getElementById("simNetEv");
    netEl.textContent = (net >= 0 ? "+" : "") + net.toFixed(2);
    netEl.style.color = net >= 0 ? "var(--green)" : "var(--bad)";

    const netTag = document.getElementById("simNetTag");
    if (net >= 0.2) {{
      netTag.className = "ok-badge";
      netTag.textContent = "Raider Advantaged";
    }} else if (net <= -0.1) {{
      netTag.className = "bad-badge";
      netTag.textContent = "Defense Advantaged";
    }} else {{
      netTag.className = "gold-badge";
      netTag.textContent = "Balanced Raid";
    }}

    const pb = pred.probabilities;
    updateBar("pTouch", pb.touch);
    updateBar("pSr", pb.superRaid);
    updateBar("pBonus", pb.bonus);
    updateBar("pEmpty", pb.empty);
    updateBar("pTackle", pb.tackle);
    updateBar("pSt", pb.superTackle);

    document.getElementById("simCoachText").textContent = pred.recommendation;
  }}

  function updateBar(prefix, prob) {{
    const pct = (prob * 100).toFixed(1) + "%";
    document.getElementById(`${{prefix}}Val`).textContent = pct;
    document.getElementById(`${{prefix}}Fill`).style.width = pct;
  }}

  // Leaderboards
  function populateLeaderboards() {{
    const rBody = document.querySelector("#raidersTable tbody");
    data.topRaiders.slice(0, 8).forEach(r => {{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><b>${{r.name}}</b> <span style="font-size:12px; color:var(--muted);">${{r.teamShort}}</span></td>
        <td class="num-cell">${{r.raiding.raids}}</td>
        <td class="num-cell"><b>${{r.raiding.raidPoints}}</b></td>
        <td class="num-cell" style="color:var(--green); font-weight:700;">${{r.raiding.strikeRate.toFixed(2)}}</td>
        <td class="num-cell">${{r.raiding.superRaids}}</td>
      `;
      tr.addEventListener("click", () => renderSpotlight(r));
      rBody.appendChild(tr);
    }});

    const dBody = document.querySelector("#defendersTable tbody");
    data.topDefenders.slice(0, 8).forEach(d => {{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><b>${{d.name}}</b> <span style="font-size:12px; color:var(--muted);">${{d.teamShort}}</span></td>
        <td class="num-cell"><b>${{d.defending.tacklePoints}}</b></td>
        <td class="num-cell">${{d.defending.tackles}}</td>
        <td class="num-cell">${{d.defending.superTackles}}</td>
        <td class="num-cell" style="color:var(--green); font-weight:700;">${{d.defending.efficiencyPct}}%</td>
      `;
      tr.addEventListener("click", () => renderSpotlight(d));
      dBody.appendChild(tr);
    }});

    if (data.topRaiders.length > 0) renderSpotlight(data.topRaiders[0]);
  }}

  function renderSpotlight(p) {{
    document.getElementById("spotName").textContent = p.name;
    document.getElementById("spotRole").textContent = p.role.toUpperCase();
    document.getElementById("spotTeam").textContent = p.teamShort;
    document.getElementById("spotJersey").textContent = `#${{p.jersey}}`;
    document.getElementById("spotTotalPts").textContent = p.totalPoints;
    document.getElementById("spotStrikeRate").textContent = p.raiding.strikeRate.toFixed(2);
    document.getElementById("spotSuperRaids").textContent = p.raiding.superRaids;
    document.getElementById("spotTackleEff").textContent = `${{p.defending.efficiencyPct}}%`;
    document.getElementById("spotDodWin").textContent = `${{p.raiding.doOrDieSuccessPct}}%`;

    renderRadar(p);
  }}

  function renderRadar(p) {{
    const svg = document.getElementById("radarSvg");
    const cx = 100, cy = 100, r = 70;
    const axes = [
      {{ label: "Strike Rate", val: Math.min(1.0, p.raiding.strikeRate / 1.5) }},
      {{ label: "Super Raids", val: Math.min(1.0, p.raiding.superRaids / 4) }},
      {{ label: "DoD Win", val: p.raiding.doOrDieSuccessPct / 100 }},
      {{ label: "Tackle Eff", val: p.defending.efficiencyPct / 100 }},
      {{ label: "Bonus", val: Math.min(1.0, p.raiding.bonusPoints / 3) }}
    ];

    const numAxes = axes.length;
    let gridCircles = "";
    [0.33, 0.66, 1.0].forEach(level => {{
      let pts = [];
      for (let i = 0; i < numAxes; i++) {{
        const angle = (Math.PI * 2 / numAxes) * i - Math.PI / 2;
        pts.push(`${{cx + Math.cos(angle) * r * level}},${{cy + Math.sin(angle) * r * level}}`);
      }}
      gridCircles += `<polygon points="${{pts.join(" ")}}" fill="none" stroke="var(--rule)" stroke-width="1"/>`;
    }});

    let dataPts = [];
    axes.forEach((axis, i) => {{
      const angle = (Math.PI * 2 / numAxes) * i - Math.PI / 2;
      const valR = r * Math.max(0.15, axis.val);
      const px = cx + Math.cos(angle) * valR;
      const py = cy + Math.sin(angle) * valR;
      dataPts.push(`${{px}},${{py}}`);
    }});

    svg.innerHTML = `
      ${{gridCircles}}
      <polygon points="${{dataPts.join(" ")}}" fill="var(--green-bg)" stroke="var(--green)" stroke-width="2"/>
      ${{dataPts.map(pt => `<circle cx="${{pt.split(',')[0]}}" cy="${{pt.split(',')[1]}}" r="3.5" fill="var(--ink)"/>`).join("")}}
    `;
  }}

  // Initialize
  renderWinProbChart();
  renderTurningPoints();
  setupScrubber();
  runSimulation();
  populateLeaderboards();
}})();
</script>
</body>
</html>
"""

    out_file = SITE_DIR / "analytics.html"
    out_file.write_text(html_content, encoding="utf-8")
    print(f"Built {out_file} ({out_file.stat().st_size:,} bytes) - perfectly matched to site design!")


if __name__ == "__main__":
    main()
