import os

code = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CineRisk — Release Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {
  --bg:#07090c;--bg2:#0c0f14;--bg3:#111620;--bg4:#171e2a;
  --border:rgba(255,255,255,0.07);--border2:rgba(255,255,255,0.13);
  --gold:#c9a84c;--gold2:#e8c96a;--red:#d94f4f;--green:#3db87a;--blue:#5b9cf6;
  --text:#dde1e8;--text2:#7a8494;--text3:#3a4150;
  --display:'Bebas Neue',sans-serif;--mono:'DM Mono',monospace;--sans:'DM Sans',sans-serif;
}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:14px}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;display:flex}

.sidebar{width:210px;flex-shrink:0;background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column}
.logo{padding:20px 16px 18px;border-bottom:1px solid var(--border)}
.logo-mark{font-family:var(--display);font-size:24px;letter-spacing:2px;line-height:1}
.logo-mark span{color:var(--gold)}
.logo-sub{font-family:var(--mono);font-size:9px;color:var(--text3);letter-spacing:.15em;margin-top:3px;text-transform:uppercase}
.nav{padding:12px 8px;flex:1}
.nav-label{font-family:var(--mono);font-size:9px;letter-spacing:.15em;color:var(--text3);text-transform:uppercase;padding:0 8px;margin:10px 0 5px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 8px;border-radius:5px;cursor:pointer;color:var(--text2);font-size:12px;transition:all .15s;border:1px solid transparent}
.nav-item:hover{background:var(--bg3);color:var(--text)}
.nav-item.active{background:rgba(201,168,76,.1);color:var(--gold);border-color:rgba(201,168,76,.2)}
.nav-item svg{width:14px;height:14px;flex-shrink:0}
.api-status{padding:12px 16px;border-top:1px solid var(--border)}
.status-dot{width:7px;height:7px;border-radius:50%;background:var(--text3);display:inline-block;margin-right:6px;transition:background .3s}
.status-dot.online{background:var(--green);animation:pulse 2s ease infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.status-text{font-family:var(--mono);font-size:10px;color:var(--text3)}

.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:52px;border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0}
.topbar-title{font-family:var(--mono);font-size:11px;letter-spacing:.1em;color:var(--text3);text-transform:uppercase}
.topbar-right{display:flex;align-items:center;gap:10px}
.btn{padding:7px 14px;border-radius:5px;font-family:var(--sans);font-size:12px;font-weight:500;cursor:pointer;border:1px solid var(--border2);background:var(--bg3);color:var(--text);transition:all .15s}
.btn:hover{background:var(--bg4)}
.btn-gold{background:var(--gold);border-color:var(--gold);color:var(--bg)}
.btn-gold:hover{background:var(--gold2)}
.btn-sm{padding:5px 10px;font-size:11px}
.btn-danger{background:rgba(217,79,79,.15);border-color:rgba(217,79,79,.3);color:var(--red)}
.btn-danger:hover{background:rgba(217,79,79,.25)}
.content{flex:1;overflow-y:auto;padding:24px}
.screen{display:none}.screen.active{display:block}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}
.kpi{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;position:relative;overflow:hidden}
.kpi::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;background:var(--kc,var(--gold));opacity:.5}
.kpi-label{font-family:var(--mono);font-size:9px;letter-spacing:.12em;color:var(--text3);text-transform:uppercase;margin-bottom:6px}
.kpi-val{font-family:var(--display);font-size:30px;letter-spacing:1px;line-height:1}
.kpi-delta{font-family:var(--mono);font-size:10px;color:var(--text3);margin-top:4px}

/* Cards */
.card{background:var(--bg2);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:14px}
.card-hdr{display:flex;align-items:center;justify-content:space-between;padding:13px 18px;border-bottom:1px solid var(--border)}
.card-title{font-family:var(--mono);font-size:10px;letter-spacing:.1em;color:var(--text2);text-transform:uppercase}
.card-body{padding:18px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}

/* Pipeline table */
.pipeline-table{width:100%;border-collapse:collapse}
.pipeline-table th{font-family:var(--mono);font-size:9px;letter-spacing:.12em;color:var(--text3);text-transform:uppercase;text-align:left;padding:0 0 10px;border-bottom:1px solid var(--border)}
.pipeline-table td{padding:12px 0;border-bottom:1px solid var(--border);vertical-align:middle}
.pipeline-table tr:last-child td{border-bottom:none}
.pipeline-table tbody tr{cursor:pointer;transition:background .1s}
.pipeline-table tbody tr:hover td{background:rgba(255,255,255,.02);padding-left:4px}
.film-name{font-size:13px;font-weight:500;color:var(--text)}
.film-meta{font-family:var(--mono);font-size:10px;color:var(--text3);margin-top:2px}
.risk-badge{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:500}
.risk-high{background:rgba(217,79,79,.15);color:var(--red);border:1px solid rgba(217,79,79,.25)}
.risk-med{background:rgba(201,168,76,.15);color:var(--gold);border:1px solid rgba(201,168,76,.25)}
.risk-low{background:rgba(61,184,122,.15);color:var(--green);border:1px solid rgba(61,184,122,.25)}
.score-bar-wrap{width:80px;height:4px;background:var(--bg4);border-radius:2px;overflow:hidden}
.score-bar-fill{height:100%;border-radius:2px}
.rev-range{font-family:var(--mono);font-size:11px;color:var(--green)}
.leak-window{font-family:var(--mono);font-size:11px;color:var(--red)}
.rec-pill{font-family:var(--mono);font-size:9px;padding:2px 8px;border-radius:3px;background:rgba(91,156,246,.12);color:var(--blue);border:1px solid rgba(91,156,246,.2)}

/* Add film form */
.add-form{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr 1.2fr auto;gap:10px;align-items:flex-end;margin-bottom:0}
.fg{display:flex;flex-direction:column;gap:5px}
.fl{font-family:var(--mono);font-size:9px;letter-spacing:.1em;color:var(--text3);text-transform:uppercase}
select,input[type=number],input[type=text]{background:var(--bg3);border:1px solid var(--border2);border-radius:5px;padding:8px 10px;font-family:var(--sans);font-size:12px;color:var(--text);outline:none;width:100%;transition:border-color .15s;appearance:none}
select:focus,input:focus{border-color:var(--gold)}

/* Simulate */
.form-row{display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:10px;align-items:flex-end}
.strat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
.strat-card{background:var(--bg3);border:1px solid var(--border);border-radius:7px;padding:14px;transition:border-color .2s;position:relative}
.strat-card.recommended{border-color:var(--green);background:rgba(61,184,122,.04)}
.strat-card.current{border-color:var(--gold);background:rgba(201,168,76,.04)}
.strat-tag{font-family:var(--mono);font-size:9px;letter-spacing:.1em;border-radius:3px;padding:2px 7px;display:inline-block;margin-bottom:8px;font-weight:500}
.tag-rec{background:rgba(61,184,122,.15);color:var(--green)}
.tag-cur{background:rgba(201,168,76,.15);color:var(--gold)}
.strat-name{font-size:13px;font-weight:500;color:var(--text);margin-bottom:10px}
.strat-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border);font-size:11px}
.strat-row:last-child{border-bottom:none}
.sl{color:var(--text3);font-family:var(--mono);font-size:10px}
.sv{font-weight:500}.sv.r{color:var(--red)}.sv.g{color:var(--green)}.sv.gold{color:var(--gold)}
.rbar-wrap{width:100%;height:5px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden;margin:6px 0 10px}
.rbar-fill{height:100%;border-radius:3px;transition:width .8s ease}
.expl-list{list-style:none;display:flex;flex-direction:column;gap:7px}
.expl-list li{font-size:12px;color:var(--text2);line-height:1.6;padding-left:14px;position:relative}
.expl-list li::before{content:'';position:absolute;left:0;top:7px;width:5px;height:5px;border-radius:50%;background:var(--gold);opacity:.7}
.conf-badge{font-family:var(--mono);font-size:10px;padding:3px 8px;border-radius:3px;background:rgba(255,255,255,.05);color:var(--text3);border:1px solid var(--border)}
.rec-box{background:rgba(61,184,122,.06);border:1px solid rgba(61,184,122,.2);border-left:3px solid var(--green);border-radius:0 7px 7px 0;padding:14px 16px;margin-bottom:14px}
.rec-label{font-family:var(--mono);font-size:9px;letter-spacing:.12em;color:var(--green);text-transform:uppercase;margin-bottom:6px}
.rec-text{font-size:13px;color:var(--text);line-height:1.6}
.loading-state{text-align:center;padding:48px;color:var(--text3)}
.spinner{width:32px;height:32px;border:2px solid var(--border);border-top-color:var(--gold);border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 12px}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-text{font-family:var(--mono);font-size:11px;letter-spacing:.1em}
.loading-text::after{content:'...';animation:dots 1.2s steps(3,end) infinite}
@keyframes dots{0%,100%{content:'.'}33%{content:'..'}66%{content:'...'}}
.error-state{background:rgba(217,79,79,.08);border:1px solid rgba(217,79,79,.2);border-radius:7px;padding:16px;color:var(--red);font-size:13px;margin-bottom:14px}
.empty-state{text-align:center;padding:48px;color:var(--text3)}
.empty-icon{font-size:32px;margin-bottom:12px;opacity:.4}
.empty-text{font-family:var(--mono);font-size:11px;letter-spacing:.08em}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg4);border-radius:2px}

/* Priority dot */
.priority-dot{width:8px;height:8px;border-radius:50%;display:inline-block}

/* Alert banner */
.alert-banner{background:rgba(217,79,79,.08);border:1px solid rgba(217,79,79,.2);border-radius:7px;padding:10px 14px;margin-bottom:14px;display:flex;align-items:center;gap:10px}
.alert-dot{width:6px;height:6px;border-radius:50%;background:var(--red);animation:pulse 1.5s ease infinite;flex-shrink:0}
.alert-text{font-size:12px;color:var(--text2)}
.alert-text strong{color:var(--red)}
</style>
</head>
<body>

<aside class="sidebar">
  <div class="logo">
    <div class="logo-mark">CINE<span>RISK</span></div>
    <div class="logo-sub">Release Intelligence</div>
  </div>
  <nav class="nav">
    <div class="nav-label">Overview</div>
    <div class="nav-item active" onclick="showScreen('pipeline',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
      Pipeline
      <span id="pipeline-badge" style="margin-left:auto;font-family:var(--mono);font-size:9px;background:rgba(201,168,76,.2);color:var(--gold);padding:1px 6px;border-radius:10px;display:none"></span>
    </div>
    <div class="nav-label">Analysis</div>
    <div class="nav-item" onclick="showScreen('simulate',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>
      Simulate
    </div>
    <div class="nav-item" onclick="showScreen('compare',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="M7 16l4-4 4 4 4-6"/></svg>
      Compare
    </div>
    <div class="nav-label">Reference</div>
    <div class="nav-item" onclick="showScreen('genres',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      Genre Index
    </div>
  </nav>
  <div class="api-status">
    <span class="status-dot" id="apiDot"></span>
    <span class="status-text" id="apiText">Checking API...</span>
  </div>
</aside>

<div class="main">
  <header class="topbar">
    <div class="topbar-title" id="screenTitle">Film Pipeline</div>
    <div class="topbar-right">
      <span class="conf-badge" id="engineBadge">Engine v2</span>
      <button class="btn btn-gold" onclick="showScreen('pipeline', document.querySelector('.nav-item'));document.getElementById('add-film-form').scrollIntoView({behavior:'smooth'})">+ Add Film</button>
    </div>
  </header>

  <div class="content">

    <!-- ── PIPELINE ── -->
    <div id="screen-pipeline" class="screen active">
      <!-- High risk alert -->
      <div id="alert-banner" class="alert-banner" style="display:none">
        <div class="alert-dot"></div>
        <div class="alert-text" id="alert-text"></div>
      </div>

      <!-- KPIs -->
      <div class="kpis" id="pipeline-kpis">
        <div class="kpi" style="--kc:var(--text3)"><div class="kpi-label">Films Tracked</div><div class="kpi-val" id="kpi-total">0</div><div class="kpi-delta">in pipeline</div></div>
        <div class="kpi" style="--kc:var(--red)"><div class="kpi-label">High Risk</div><div class="kpi-val" id="kpi-high" style="color:var(--red)">0</div><div class="kpi-delta">need attention</div></div>
        <div class="kpi" style="--kc:var(--green)"><div class="kpi-label">Revenue Range</div><div class="kpi-val" id="kpi-rev" style="font-size:18px;color:var(--green)">—</div><div class="kpi-delta">total pipeline</div></div>
        <div class="kpi" style="--kc:var(--gold)"><div class="kpi-label">Avg Risk Score</div><div class="kpi-val" id="kpi-avg">—</div><div class="kpi-delta">across all films</div></div>
      </div>

      <!-- Film table -->
      <div class="card">
        <div class="card-hdr">
          <span class="card-title">Film Pipeline — ranked by risk</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-sm" onclick="sortPipeline('risk')">Sort: Risk</button>
            <button class="btn btn-sm" onclick="sortPipeline('revenue')">Sort: Revenue</button>
            <button class="btn btn-sm" onclick="sortPipeline('leak')">Sort: Leak Day</button>
          </div>
        </div>
        <div class="card-body" style="padding:0">
          <div id="pipeline-table-wrap" style="padding:18px">
            <div class="empty-state">
              <div class="empty-icon">◎</div>
              <div class="empty-text">No films yet — add one below</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Add film form -->
      <div class="card" id="add-film-form">
        <div class="card-hdr"><span class="card-title">Add Film to Pipeline</span></div>
        <div class="card-body">
          <div class="add-form">
            <div class="fg">
              <label class="fl">Film Title</label>
              <input type="text" id="p-title" placeholder="e.g. Nova Station">
            </div>
            <div class="fg">
              <label class="fl">Genre</label>
              <select id="p-genre">
                <option value="action">Action</option>
                <option value="scifi">Sci-Fi</option>
                <option value="thriller">Thriller</option>
                <option value="horror">Horror</option>
                <option value="animation">Animation</option>
                <option value="drama">Drama</option>
              </select>
            </div>
            <div class="fg">
              <label class="fl">Hype</label>
              <select id="p-hype">
                <option value="low">Low</option>
                <option value="medium" selected>Medium</option>
                <option value="high">High</option>
              </select>
            </div>
            <div class="fg">
              <label class="fl">Strategy</label>
              <select id="p-strategy">
                <option value="global_day1">Global Day-One</option>
                <option value="staggered" selected>Staggered</option>
                <option value="streaming_delay">Streaming Delay</option>
              </select>
            </div>
            <div class="fg">
              <label class="fl">Budget ($M)</label>
              <input type="number" id="p-budget" value="100" min="1" max="2000">
            </div>
            <button class="btn btn-gold" onclick="addFilm()" style="height:36px;white-space:nowrap">Analyse →</button>
          </div>
        </div>
      </div>

      <!-- Pipeline chart -->
      <div id="pipeline-chart-wrap" style="display:none">
        <div class="grid2">
          <div class="card">
            <div class="card-hdr"><span class="card-title">Risk Score Distribution</span></div>
            <div class="card-body"><canvas id="riskChart" height="200"></canvas></div>
          </div>
          <div class="card">
            <div class="card-hdr"><span class="card-title">Revenue Range by Film</span></div>
            <div class="card-body"><canvas id="revChart" height="200"></canvas></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── SIMULATE ── -->
    <div id="screen-simulate" class="screen">
      <div class="card">
        <div class="card-hdr">
          <span class="card-title">Film Parameters</span>
          <span class="conf-badge">3 inputs · engine calculates the rest</span>
        </div>
        <div class="card-body">
          <div class="form-row">
            <div class="fg"><label class="fl">Genre</label>
              <select id="i-genre"><option value="action">Action</option><option value="scifi">Sci-Fi</option><option value="thriller">Thriller</option><option value="horror">Horror</option><option value="animation">Animation</option><option value="drama">Drama</option></select>
            </div>
            <div class="fg"><label class="fl">Hype</label>
              <select id="i-hype"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option></select>
            </div>
            <div class="fg"><label class="fl">Strategy</label>
              <select id="i-strategy"><option value="global_day1">Global Day-One</option><option value="staggered" selected>Staggered</option><option value="streaming_delay">Streaming Delay</option></select>
            </div>
            <div class="fg"><label class="fl">Budget ($M)</label>
              <input type="number" id="i-budget" value="150" min="1" max="2000">
            </div>
            <button class="btn btn-gold" onclick="runSimulation()" style="height:36px">Run →</button>
          </div>
        </div>
      </div>
      <div id="sim-results">
        <div class="empty-state"><div class="empty-icon">◎</div><div class="empty-text">Set parameters above and click Run</div></div>
      </div>
    </div>

    <!-- ── COMPARE ── -->
    <div id="screen-compare" class="screen">
      <div class="card">
        <div class="card-hdr"><span class="card-title">Strategy Comparison</span></div>
        <div class="card-body">
          <div class="form-row">
            <div class="fg"><label class="fl">Genre</label>
              <select id="c-genre"><option value="action">Action</option><option value="scifi">Sci-Fi</option><option value="thriller">Thriller</option><option value="horror">Horror</option><option value="animation">Animation</option><option value="drama">Drama</option></select>
            </div>
            <div class="fg"><label class="fl">Hype</label>
              <select id="c-hype"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option></select>
            </div>
            <div class="fg"><label class="fl">Budget ($M)</label>
              <input type="number" id="c-budget" value="150" min="1" max="2000">
            </div>
            <div class="fg"><label class="fl">Film Title</label>
              <input type="text" id="c-title" placeholder="Optional">
            </div>
            <button class="btn btn-gold" onclick="runCompare()" style="height:36px">Compare →</button>
          </div>
        </div>
      </div>
      <div id="cmp-results">
        <div class="empty-state"><div class="empty-icon">◈</div><div class="empty-text">Compare all 3 release strategies side by side</div></div>
      </div>
    </div>

    <!-- ── GENRES ── -->
    <div id="screen-genres" class="screen">
      <div id="genre-content">
        <div class="loading-state"><div class="spinner"></div><div class="loading-text">Loading</div></div>
      </div>
    </div>

  </div>
</div>

<script>
const API = 'https://web-production-f7244.up.railway.app';

// ── State ─────────────────────────────────────────────────────────────
let pipeline = [];   // [{title, genre, hype, strategy, budget, result}]
let sortKey  = 'risk';
let simChart = null, riskChart = null, revChart = null;

// ── Health check ──────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`,{signal:AbortSignal.timeout(4000)});
    const d = await r.json();
    document.getElementById('apiDot').className='status-dot online';
    document.getElementById('apiText').textContent='API online';
    document.getElementById('engineBadge').textContent=`Engine ${d.version||'v2'}`;
  } catch {
    document.getElementById('apiDot').className='status-dot';
    document.getElementById('apiText').textContent='API offline';
  }
}
checkHealth(); setInterval(checkHealth,15000);

// ── Navigation ────────────────────────────────────────────────────────
const titles={pipeline:'Film Pipeline',simulate:'Simulation Engine',compare:'Strategy Comparison',genres:'Genre Risk Index'};
function showScreen(id,el){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById(`screen-${id}`).classList.add('active');
  if(el)el.classList.add('active');
  document.getElementById('screenTitle').textContent=titles[id]||id;
  if(id==='genres')loadGenres();
}

// ── Helpers ───────────────────────────────────────────────────────────
function rc(s){return s>=0.70?'var(--red)':s>=0.45?'var(--gold)':'var(--green)'}
function rl(s){return s>=0.70?'High':s>=0.45?'Medium':'Low'}
function rclass(s){return s>=0.70?'risk-high':s>=0.45?'risk-med':'risk-low'}
function sl(s){return{global_day1:'Global Day-One',staggered:'Staggered',streaming_delay:'Streaming Delay'}[s]||s}

// ── Add film to pipeline ──────────────────────────────────────────────
async function addFilm(){
  const title    = document.getElementById('p-title').value || 'Untitled';
  const genre    = document.getElementById('p-genre').value;
  const hype     = document.getElementById('p-hype').value;
  const strategy = document.getElementById('p-strategy').value;
  const budget   = parseFloat(document.getElementById('p-budget').value)||100;

  const btn = document.querySelector('#add-film-form .btn-gold');
  btn.textContent = 'Analysing...'; btn.disabled = true;

  try {
    const res = await fetch(`${API}/simulate`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({genre,hype,strategy,budget_m:budget,film_title:title})
    });
    if(!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    const cur  = data.strategies.find(s=>s.strategy===data.current_strategy);

    pipeline.push({
      id: Date.now(),
      title, genre, hype, strategy, budget,
      risk:      cur.risk_score,
      risk_label:cur.risk_label,
      rev_low:   cur.revenue_low,
      rev_high:  cur.revenue_high,
      leak_low:  cur.leak_day_low,
      leak_high: cur.leak_day_high,
      confidence:cur.confidence,
      recommended: data.recommended,
      rec_text:  data.recommendation_text,
      full_data: data,
    });

    document.getElementById('p-title').value = '';
    renderPipeline();
  } catch(e) {
    alert(`Could not analyse film: ${e.message}\nMake sure API is running.`);
  } finally {
    btn.textContent = 'Analyse →'; btn.disabled = false;
  }
}

// ── Sort ──────────────────────────────────────────────────────────────
function sortPipeline(key){
  sortKey = key;
  renderPipeline();
}

// ── Render pipeline ───────────────────────────────────────────────────
function renderPipeline(){
  const films = [...pipeline].sort((a,b)=>{
    if(sortKey==='risk')    return b.risk - a.risk;
    if(sortKey==='revenue') return b.rev_high - a.rev_high;
    if(sortKey==='leak')    return a.leak_low - b.leak_low;
    return 0;
  });

  // Update KPIs
  const total  = films.length;
  const highs  = films.filter(f=>f.risk>=0.70).length;
  const totLo  = films.reduce((s,f)=>s+f.rev_low,0);
  const totHi  = films.reduce((s,f)=>s+f.rev_high,0);
  const avgRisk= total ? (films.reduce((s,f)=>s+f.risk,0)/total).toFixed(2) : '—';

  document.getElementById('kpi-total').textContent = total||'0';
  document.getElementById('kpi-high').textContent  = highs||'0';
  document.getElementById('kpi-rev').textContent   = total ? `$${totLo}M–$${totHi}M` : '—';
  document.getElementById('kpi-avg').textContent   = avgRisk;

  // Badge
  const badge = document.getElementById('pipeline-badge');
  if(total>0){ badge.textContent=total; badge.style.display='inline'; }
  else badge.style.display='none';

  // Alert banner
  const alertBanner = document.getElementById('alert-banner');
  if(highs>0){
    alertBanner.style.display='flex';
    const names = films.filter(f=>f.risk>=0.70).map(f=>f.title).join(', ');
    document.getElementById('alert-text').innerHTML =
      `<strong>${highs} film${highs>1?'s':''} at HIGH risk</strong> — ${names}. Strategy review recommended before locking release calendar.`;
  } else { alertBanner.style.display='none'; }

  // Table
  const wrap = document.getElementById('pipeline-table-wrap');
  if(total===0){
    wrap.innerHTML='<div class="empty-state"><div class="empty-icon">◎</div><div class="empty-text">No films yet — add one below</div></div>';
    document.getElementById('pipeline-chart-wrap').style.display='none';
    return;
  }

  wrap.innerHTML = `
    <table class="pipeline-table">
      <thead><tr>
        <th>Film</th>
        <th>Strategy</th>
        <th>Risk Score</th>
        <th>Risk Level</th>
        <th>Revenue Range</th>
        <th>Leak Window</th>
        <th>Recommended</th>
        <th>Conf.</th>
        <th></th>
      </tr></thead>
      <tbody>
        ${films.map(f=>`
        <tr onclick="drillDown('${f.id}')">
          <td>
            <div class="film-name">${f.title}</div>
            <div class="film-meta">${f.genre} · $${f.budget}M · ${f.hype} hype</div>
          </td>
          <td><span style="font-family:var(--mono);font-size:11px;color:var(--text2)">${sl(f.strategy)}</span></td>
          <td>
            <div style="display:flex;align-items:center;gap:8px">
              <div class="score-bar-wrap"><div class="score-bar-fill" style="width:${f.risk*100}%;background:${rc(f.risk)}"></div></div>
              <span style="font-family:var(--mono);font-size:11px;color:${rc(f.risk)}">${f.risk.toFixed(2)}</span>
            </div>
          </td>
          <td><span class="risk-badge ${rclass(f.risk)}">${rl(f.risk)}</span></td>
          <td class="rev-range">$${f.rev_low}M–$${f.rev_high}M</td>
          <td class="leak-window">Day ${f.leak_low}–${f.leak_high}</td>
          <td><span class="rec-pill">${sl(f.recommended)}</span></td>
          <td><span style="font-family:var(--mono);font-size:11px;color:var(--text3)">${(f.confidence*100).toFixed(0)}%</span></td>
          <td><button class="btn btn-sm btn-danger" onclick="event.stopPropagation();removeFilm('${f.id}')">✕</button></td>
        </tr>`).join('')}
      </tbody>
    </table>`;

  // Charts
  document.getElementById('pipeline-chart-wrap').style.display='block';
  renderPipelineCharts(films);
}

// ── Drill down into a film ────────────────────────────────────────────
function drillDown(id){
  const film = pipeline.find(f=>String(f.id)===String(id));
  if(!film) return;

  // Pre-fill simulate form and switch to it
  document.getElementById('i-genre').value    = film.genre;
  document.getElementById('i-hype').value     = film.hype;
  document.getElementById('i-strategy').value = film.strategy;
  document.getElementById('i-budget').value   = film.budget;

  showScreen('simulate', document.querySelectorAll('.nav-item')[2]);
  renderSimResult(film.full_data);
}

// ── Remove film ───────────────────────────────────────────────────────
function removeFilm(id){
  pipeline = pipeline.filter(f=>String(f.id)!==String(id));
  renderPipeline();
}

// ── Pipeline charts ───────────────────────────────────────────────────
function renderPipelineCharts(films){
  const labels = films.map(f=>f.title.length>12?f.title.slice(0,12)+'…':f.title);

  if(riskChart){ riskChart.destroy(); riskChart=null; }
  const ctx1=document.getElementById('riskChart').getContext('2d');
  riskChart=new Chart(ctx1,{
    type:'bar',
    data:{labels,datasets:[{
      label:'Risk Score',
      data:films.map(f=>f.risk),
      backgroundColor:films.map(f=>f.risk>=0.70?'rgba(217,79,79,0.7)':f.risk>=0.45?'rgba(201,168,76,0.7)':'rgba(61,184,122,0.7)'),
      borderRadius:3,
    }]},
    options:{responsive:true,plugins:{legend:{display:false}},scales:{
      x:{ticks:{color:'#3a4150',font:{family:'DM Mono',size:10}},grid:{display:false}},
      y:{max:1,ticks:{color:'#3a4150',font:{family:'DM Mono',size:10}},grid:{color:'rgba(255,255,255,0.04)'}},
    }}
  });

  if(revChart){ revChart.destroy(); revChart=null; }
  const ctx2=document.getElementById('revChart').getContext('2d');
  revChart=new Chart(ctx2,{
    type:'bar',
    data:{labels,datasets:[
      {label:'Revenue High',data:films.map(f=>f.rev_high),backgroundColor:'rgba(61,184,122,0.6)',borderRadius:3},
      {label:'Revenue Low', data:films.map(f=>f.rev_low), backgroundColor:'rgba(61,184,122,0.25)',borderRadius:3},
    ]},
    options:{responsive:true,plugins:{legend:{labels:{color:'#7a8494',font:{family:'DM Mono',size:10}}}},scales:{
      x:{ticks:{color:'#3a4150',font:{family:'DM Mono',size:10}},grid:{display:false}},
      y:{ticks:{color:'#3a4150',font:{family:'DM Mono',size:10},callback:v=>'$'+v+'M'},grid:{color:'rgba(255,255,255,0.04)'}},
    }}
  });
}

// ── Simulate ──────────────────────────────────────────────────────────
async function runSimulation(){
  const genre    = document.getElementById('i-genre').value;
  const hype     = document.getElementById('i-hype').value;
  const strategy = document.getElementById('i-strategy').value;
  const budget   = parseFloat(document.getElementById('i-budget').value)||100;

  document.getElementById('sim-results').innerHTML=`<div class="loading-state"><div class="spinner"></div><div class="loading-text">Running simulation</div></div>`;

  try {
    const res=await fetch(`${API}/simulate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({genre,hype,strategy,budget_m:budget})});
    if(!res.ok)throw new Error(`API ${res.status}`);
    const data=await res.json();
    renderSimResult(data);
  } catch(e){
    document.getElementById('sim-results').innerHTML=`<div class="error-state">API not reachable — make sure it's running. Error: ${e.message}</div>`;
  }
}

function renderSimResult(data){
  const cur=data.strategies.find(s=>s.strategy===data.current_strategy);
  document.getElementById('sim-results').innerHTML=`
    <div class="kpis">
      <div class="kpi" style="--kc:${rc(cur.risk_score)}"><div class="kpi-label">Current Risk</div><div class="kpi-val" style="color:${rc(cur.risk_score)}">${cur.risk_score.toFixed(2)}</div><div class="kpi-delta">${cur.risk_label}</div></div>
      <div class="kpi" style="--kc:var(--green)"><div class="kpi-label">Revenue Range</div><div class="kpi-val" style="font-size:18px;color:var(--green)">$${cur.revenue_low}M–$${cur.revenue_high}M</div><div class="kpi-delta">${sl(data.current_strategy)}</div></div>
      <div class="kpi" style="--kc:var(--red)"><div class="kpi-label">Est. Leak Window</div><div class="kpi-val" style="font-size:22px;color:var(--red)">D+${cur.leak_day_low}–${cur.leak_day_high}</div><div class="kpi-delta">first leak estimate</div></div>
      <div class="kpi" style="--kc:var(--gold)"><div class="kpi-label">Recommended</div><div class="kpi-val" style="font-size:16px;color:var(--gold)">${sl(data.recommended)}</div><div class="kpi-delta">${(data.strategies.find(s=>s.strategy===data.recommended).confidence*100).toFixed(0)}% confidence</div></div>
    </div>
    <div class="rec-box"><div class="rec-label">Engine Recommendation</div><div class="rec-text">${data.recommendation_text}</div></div>
    <div class="strat-grid">${renderStratCards(data.strategies,data.recommended,data.current_strategy)}</div>
    <div class="grid2">
      <div class="card"><div class="card-hdr"><span class="card-title">Revenue Range by Strategy</span></div><div class="card-body"><canvas id="simChart" height="200"></canvas></div></div>
      <div class="card"><div class="card-hdr"><span class="card-title">Why This Result — ${sl(data.current_strategy)}</span><span class="conf-badge">${(cur.confidence*100).toFixed(0)}% confidence</span></div><div class="card-body"><ul class="expl-list">${cur.explanation.map(e=>`<li>${e}</li>`).join('')}</ul></div></div>
    </div>
    <div style="margin-top:10px;text-align:right">
      <button class="btn btn-sm" onclick="addFromSim()">+ Add to Pipeline</button>
    </div>`;
  renderSimChart(data.strategies,'simChart');
}

function addFromSim(){
  document.getElementById('p-genre').value    = document.getElementById('i-genre').value;
  document.getElementById('p-hype').value     = document.getElementById('i-hype').value;
  document.getElementById('p-strategy').value = document.getElementById('i-strategy').value;
  document.getElementById('p-budget').value   = document.getElementById('i-budget').value;
  showScreen('pipeline',document.querySelector('.nav-item'));
  document.getElementById('add-film-form').scrollIntoView({behavior:'smooth'});
}

function renderStratCards(strategies,recommended,current){
  return strategies.map(s=>{
    const isRec=s.strategy===recommended, isCur=s.strategy===current&&!isRec;
    return `<div class="strat-card ${isRec?'recommended':''} ${isCur?'current':''}">
      ${isRec?'<span class="strat-tag tag-rec">RECOMMENDED</span>':''}
      ${isCur?'<span class="strat-tag tag-cur">CURRENT</span>':''}
      <div class="strat-name">${sl(s.strategy)}</div>
      <div class="rbar-wrap"><div class="rbar-fill" style="width:${s.risk_score*100}%;background:${rc(s.risk_score)}"></div></div>
      <div class="strat-row"><span class="sl">Risk Score</span><span class="sv ${s.risk_score>=0.70?'r':s.risk_score>=0.45?'gold':'g'}">${s.risk_score.toFixed(2)} · ${s.risk_label}</span></div>
      <div class="strat-row"><span class="sl">Revenue Range</span><span class="sv g">$${s.revenue_low}M–$${s.revenue_high}M</span></div>
      <div class="strat-row"><span class="sl">Leak Window</span><span class="sv r">Day ${s.leak_day_low}–${s.leak_day_high}</span></div>
      <div class="strat-row"><span class="sl">Confidence</span><span class="sv" style="color:var(--text2)">${(s.confidence*100).toFixed(0)}%</span></div>
    </div>`;
  }).join('');
}

function renderSimChart(strategies,canvasId){
  setTimeout(()=>{
    const ctx=document.getElementById(canvasId); if(!ctx)return;
    if(simChart){simChart.destroy();simChart=null;}
    simChart=new Chart(ctx,{type:'bar',data:{labels:strategies.map(s=>sl(s.strategy)),datasets:[
      {label:'Revenue High ($M)',data:strategies.map(s=>s.revenue_high),backgroundColor:'rgba(61,184,122,0.6)',borderRadius:3},
      {label:'Revenue Low ($M)', data:strategies.map(s=>s.revenue_low), backgroundColor:'rgba(61,184,122,0.25)',borderRadius:3},
    ]},options:{responsive:true,plugins:{legend:{labels:{color:'#7a8494',font:{family:'DM Mono',size:10}}}},scales:{
      x:{ticks:{color:'#3a4150',font:{family:'DM Mono',size:10}},grid:{display:false}},
      y:{ticks:{color:'#3a4150',font:{family:'DM Mono',size:10},callback:v=>'$'+v+'M'},grid:{color:'rgba(255,255,255,0.04)'}},
    }}});
  },50);
}

// ── Compare ───────────────────────────────────────────────────────────
async function runCompare(){
  const genre=document.getElementById('c-genre').value,hype=document.getElementById('c-hype').value;
  const budget=parseFloat(document.getElementById('c-budget').value)||100,title=document.getElementById('c-title').value||null;
  document.getElementById('cmp-results').innerHTML=`<div class="loading-state"><div class="spinner"></div><div class="loading-text">Comparing strategies</div></div>`;
  try{
    const res=await fetch(`${API}/compare`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({genre,hype,strategy:'global_day1',budget_m:budget,film_title:title})});
    if(!res.ok)throw new Error(`API ${res.status}`);
    const data=await res.json();
    document.getElementById('cmp-results').innerHTML=`
      <div class="rec-box"><div class="rec-label">Engine Recommendation${title?' — '+title:''}</div><div class="rec-text">${data.recommendation}</div></div>
      <div class="card"><div class="card-hdr"><span class="card-title">All Strategies</span></div><div class="card-body" style="padding:0">
        <table style="width:100%;border-collapse:collapse"><thead><tr style="border-bottom:1px solid var(--border)">
          ${['Strategy','Risk','Level','Revenue Range','Leak Window','Confidence'].map(h=>`<th style="padding:10px 14px;font-family:var(--mono);font-size:9px;letter-spacing:.1em;color:var(--text3);text-align:left;text-transform:uppercase">${h}</th>`).join('')}
        </tr></thead><tbody>
          ${data.comparison.map((s,i)=>`<tr style="background:${i%2===0?'var(--bg2)':'var(--bg3)'};border-bottom:1px solid var(--border)">
            <td style="padding:11px 14px"><span style="font-size:12px;font-weight:500;color:var(--text)">${s.label}</span>
              ${s.recommended?'<span class="strat-tag tag-rec" style="margin-left:6px;font-size:9px">REC</span>':''}
              ${s.current?'<span class="strat-tag tag-cur" style="margin-left:6px;font-size:9px">CURRENT</span>':''}
            </td>
            <td style="padding:11px 14px;font-family:var(--mono);font-size:11px;color:${rc(s.risk)}">${s.risk.toFixed(2)}</td>
            <td style="padding:11px 14px;font-family:var(--mono);font-size:10px;color:${rc(s.risk)}">${s.risk_label}</td>
            <td style="padding:11px 14px;font-family:var(--mono);font-size:11px;color:var(--green)">${s.revenue_range}</td>
            <td style="padding:11px 14px;font-family:var(--mono);font-size:11px;color:var(--red)">${s.leak_window}</td>
            <td style="padding:11px 14px;font-family:var(--mono);font-size:11px;color:var(--text3)">${s.confidence}</td>
          </tr>`).join('')}
        </tbody></table>
      </div></div>`;
  }catch(e){document.getElementById('cmp-results').innerHTML=`<div class="error-state">API not reachable. Error: ${e.message}</div>`;}
}

// ── Genre index ───────────────────────────────────────────────────────
async function loadGenres(){
  try{
    const r=await fetch(`${API}/genres`); const d=await r.json();
    document.getElementById('genre-content').innerHTML=`<div class="card"><div class="card-hdr"><span class="card-title">Genre Piracy Sensitivity Index</span></div><div class="card-body" style="padding:0">
      <table style="width:100%;border-collapse:collapse"><thead><tr style="border-bottom:1px solid var(--border)">
        ${['Genre','Sensitivity','Risk Level','Revenue Mult'].map(h=>`<th style="padding:10px 14px;font-family:var(--mono);font-size:9px;letter-spacing:.1em;color:var(--text3);text-align:left;text-transform:uppercase">${h}</th>`).join('')}
      </tr></thead><tbody>
        ${d.genres.map((g,i)=>`<tr style="background:${i%2===0?'var(--bg2)':'var(--bg3)'};border-bottom:1px solid var(--border)">
          <td style="padding:12px 14px;font-size:13px;font-weight:500;color:var(--text)">${g.label}</td>
          <td style="padding:12px 14px"><div style="display:flex;align-items:center;gap:10px">
            <div style="width:100px;height:5px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden"><div style="width:${g.sensitivity*100}%;height:100%;background:${rc(g.sensitivity)};border-radius:3px"></div></div>
            <span style="font-family:var(--mono);font-size:11px;color:${rc(g.sensitivity)}">${(g.sensitivity*100).toFixed(0)}%</span>
          </div></td>
          <td style="padding:12px 14px;font-family:var(--mono);font-size:10px;color:${rc(g.sensitivity)}">${g.sensitivity>=0.55?'HIGH':g.sensitivity>=0.35?'MEDIUM':'LOW'}</td>
          <td style="padding:12px 14px;font-family:var(--mono);font-size:11px;color:var(--text2)">${{action:'2.6x',scifi:'2.3x',thriller:'1.8x',horror:'2.0x',drama:'1.4x',animation:'2.9x'}[g.id]||'2.0x'}</td>
        </tr>`).join('')}
      </tbody></table>
    </div></div>`;
  }catch(e){document.getElementById('genre-content').innerHTML=`<div class="error-state">Could not load genres. Error: ${e.message}</div>`;}
}
</script>
</body>
</html>'''

path = os.path.expanduser("~/Desktop/cinerisk/dashboard_v3.html")
with open(path, "w") as f:
    f.write(code)
print(f"Created: {path}")
print("Open in browser: open ~/Desktop/cinerisk/dashboard_v3.html")
