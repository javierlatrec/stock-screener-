"""
html_generator.py v4
====================
v4 añade en el modal:
- Descripción larga de la empresa (en inglés)
- Industry específica
- País
- Website (clicable)
- Número de empleados
- Dividend yield

Más todo lo de v3 (5 filtros fundamentales).
"""

import os
import json
import hashlib
from datetime import datetime


DATA_DIR        = "data"
SIGNALS_JSON    = os.path.join(DATA_DIR, "signals.json")
SUMMARY_JSON    = os.path.join(DATA_DIR, "signals_summary.json")

OUTPUT_DIR      = "docs"
OUTPUT_HTML     = os.path.join(OUTPUT_DIR, "index.html")
OUTPUT_JSON     = os.path.join(OUTPUT_DIR, "signals.json")
OUTPUT_SUMMARY  = os.path.join(OUTPUT_DIR, "signals_summary.json")

PASSWORD        = "1234"


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CB Scanner — Señales de mercado</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body {
    background: #0a0a0a;
    color: #e5e5e5;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }
  .card { background: #141414; border: 1px solid #262626; }
  .badge {
    padding: 2px 8px; border-radius: 6px; font-size: 11px;
    font-weight: 600; display: inline-block; white-space: nowrap;
  }
  .badge-gold  { background: #fbbf24; color: #000; }
  .badge-buy   { background: #10b981; color: #000; }
  .badge-sell  { background: #ef4444; color: #fff; }
  .badge-sellp { background: #f97316; color: #fff; }
  .badge-carvana { background: linear-gradient(135deg, #fbbf24, #f97316);
                   color: #000; font-weight: 700; }
  .tier-micro  { background: #7f1d1d; color: #fecaca; }
  .tier-small  { background: #9a3412; color: #fed7aa; }
  .tier-mid    { background: #854d0e; color: #fef3c7; }
  .tier-large  { background: #14532d; color: #d1fae5; }
  .tier-crypto { background: #1e3a8a; color: #dbeafe; }
  tr.row-clickable { cursor: pointer; transition: background 0.1s; }
  tr.row-clickable:hover { background: #1f1f1f; }
  tr.row-carvana { background: rgba(251, 191, 36, 0.05); }
  tr.row-carvana:hover { background: rgba(251, 191, 36, 0.1); }
  .sortable { cursor: pointer; user-select: none; }
  .sortable:hover { color: #fbbf24; }
  .login-overlay {
    position: fixed; inset: 0; background: #0a0a0a; z-index: 100;
    display: flex; align-items: center; justify-content: center;
  }
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.85);
    z-index: 90; display: none; align-items: center; justify-content: center;
    padding: 16px;
  }
  .modal-overlay.open { display: flex; }
  .modal-content {
    background: #141414; border: 1px solid #404040;
    border-radius: 12px; max-width: 800px; width: 100%;
    max-height: 92vh; overflow-y: auto; padding: 24px;
  }
  .metric-good { color: #10b981; }
  .metric-bad  { color: #ef4444; }
  .metric-neutral { color: #a3a3a3; }
  .metric-row {
    display: flex; justify-content: space-between;
    padding: 8px 0; border-bottom: 1px solid #262626;
  }
  .metric-row:last-child { border-bottom: none; }
  .metric-label { color: #a3a3a3; font-size: 13px; }
  .metric-value { color: #e5e5e5; font-weight: 600; font-size: 14px; }
  .reason-item {
    padding: 6px 10px; background: rgba(16, 185, 129, 0.1);
    border-left: 3px solid #10b981; margin: 4px 0;
    border-radius: 4px; font-size: 13px;
  }
  .warning-item {
    padding: 6px 10px; background: rgba(239, 68, 68, 0.1);
    border-left: 3px solid #ef4444; margin: 4px 0;
    border-radius: 4px; font-size: 13px;
  }
  .score-bar {
    height: 8px; background: #262626; border-radius: 4px;
    overflow: hidden; margin-top: 4px;
  }
  .score-fill {
    height: 100%; background: linear-gradient(90deg, #f97316, #fbbf24);
    transition: width 0.3s;
  }
  .company-summary {
    background: #0f0f0f; padding: 12px; border-radius: 8px;
    border-left: 3px solid #fbbf24;
    font-size: 13px; line-height: 1.6; color: #d4d4d4;
    max-height: 240px; overflow-y: auto;
  }
  .company-summary::-webkit-scrollbar { width: 4px; }
  .company-summary::-webkit-scrollbar-thumb { background: #404040; }
  .info-pill {
    display: inline-flex; align-items: center; gap: 4px;
    background: #1f1f1f; padding: 4px 10px; border-radius: 12px;
    font-size: 11px; color: #a3a3a3; margin: 2px;
  }
  .info-pill a { color: #fbbf24; }
  .modal-content::-webkit-scrollbar { width: 6px; }
  .modal-content::-webkit-scrollbar-track { background: #0a0a0a; }
  .modal-content::-webkit-scrollbar-thumb { background: #404040; border-radius: 3px; }
</style>
</head>
<body class="min-h-screen">

<!-- LOGIN -->
<div id="loginOverlay" class="login-overlay">
  <div class="card p-8 rounded-lg w-80">
    <h1 class="text-2xl font-bold mb-2">🔒 CB Scanner</h1>
    <p class="text-sm text-neutral-400 mb-6">Acceso privado</p>
    <input id="passwordInput" type="password" placeholder="Contraseña"
      class="w-full bg-neutral-800 text-white px-3 py-2 rounded mb-3 outline-none"
      onkeypress="if(event.key==='Enter') checkPassword()">
    <button onclick="checkPassword()"
      class="w-full bg-yellow-500 text-black font-semibold py-2 rounded hover:bg-yellow-400">
      Entrar
    </button>
    <p id="loginError" class="text-red-500 text-sm mt-2 hidden">Contraseña incorrecta</p>
  </div>
</div>

<!-- CONTENT -->
<div id="content" class="hidden">

  <!-- HEADER -->
  <header class="border-b border-neutral-800 sticky top-0 z-50 bg-black/95 backdrop-blur">
    <div class="max-w-7xl mx-auto px-4 py-3">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 class="text-xl font-bold">📊 CB Scanner</h1>
          <p class="text-xs text-neutral-500">{{scan_date_human}} · {{total_scanned}} tickers</p>
        </div>
        <div class="flex gap-2 items-center text-sm flex-wrap">
          <span class="badge badge-carvana">⭐ {{count_carvana}}</span>
          <span class="badge badge-gold">🏆 {{count_gold}}</span>
          <span class="badge badge-buy">🟢 {{count_buy}}</span>
          <span class="badge badge-sellp">🔥 {{count_sellp}}</span>
          <span class="badge badge-sell">🔴 {{count_sell}}</span>
        </div>
      </div>
    </div>
  </header>

  <!-- FILTERS -->
  <div class="max-w-7xl mx-auto px-4 py-4">
    <div class="card rounded-lg p-3 mb-3">
      <div class="flex gap-2 flex-wrap items-center">
        <input id="searchInput" type="text" placeholder="🔍 Ticker o nombre..."
          class="bg-neutral-800 text-white px-3 py-2 rounded outline-none flex-1 min-w-[180px]"
          oninput="applyFilters()">

        <select id="signalFilter" onchange="applyFilters()"
          class="bg-neutral-800 text-white px-3 py-2 rounded outline-none">
          <option value="">Todas las señales</option>
          <option value="BUY_GOLD">🏆 BUY GOLD</option>
          <option value="BUY">🟢 BUY</option>
          <option value="SELL_PLUS">🔥 SELL+</option>
          <option value="SELL">🔴 SELL</option>
        </select>

        <select id="tierFilter" onchange="applyFilters()"
          class="bg-neutral-800 text-white px-3 py-2 rounded outline-none">
          <option value="">Todas las caps</option>
          <option value="micro">🔴 Micro</option>
          <option value="small">🟠 Small</option>
          <option value="mid">🟡 Mid</option>
          <option value="large">🟢 Large</option>
          <option value="crypto">🪙 Crypto</option>
        </select>

        <select id="sectorFilter" onchange="applyFilters()"
          class="bg-neutral-800 text-white px-3 py-2 rounded outline-none max-w-[200px]">
          <option value="">Todos los sectores</option>
          {{sector_options}}
        </select>

        <label class="flex items-center gap-2 cursor-pointer bg-neutral-800 px-3 py-2 rounded">
          <input id="carvanaOnly" type="checkbox" onchange="applyFilters()" class="accent-yellow-500">
          <span class="text-sm">⭐ Solo Carvana</span>
        </label>

        <button onclick="resetFilters()"
          class="bg-neutral-700 text-white px-3 py-2 rounded hover:bg-neutral-600">
          Reset
        </button>
      </div>

      <div class="mt-3 pt-3 border-t border-neutral-800">
        <div class="text-xs text-neutral-500 mb-2 uppercase">Filtros técnicos</div>
        <div class="flex gap-2 flex-wrap items-center text-sm">
          <select id="drawdownFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier drawdown</option>
            <option value="50">≥ 50% caída</option>
            <option value="70">≥ 70% caída</option>
            <option value="85">≥ 85% caída</option>
            <option value="95">≥ 95% caída</option>
          </select>
          <select id="peFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier PER</option>
            <option value="15">PER &lt; 15</option>
            <option value="25">PER &lt; 25</option>
            <option value="50">PER &lt; 50</option>
          </select>
          <select id="ipoFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier IPO</option>
            <option value="3">IPO &lt; 3 años</option>
            <option value="5">IPO 1-5 años</option>
            <option value="7">IPO 1-7 años</option>
          </select>
          <select id="shortFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier short</option>
            <option value="10">Short ≥ 10%</option>
            <option value="20">Short ≥ 20%</option>
            <option value="30">Short ≥ 30%</option>
            <option value="50">Short ≥ 50%</option>
          </select>
        </div>
      </div>

      <div class="mt-3 pt-3 border-t border-neutral-800">
        <div class="text-xs text-neutral-500 mb-2 uppercase">Filtros fundamentales</div>
        <div class="flex gap-2 flex-wrap items-center text-sm">
          <select id="insiderFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier insider %</option>
            <option value="5">Insiders ≥ 5%</option>
            <option value="10">Insiders ≥ 10%</option>
            <option value="20">Insiders ≥ 20%</option>
          </select>
          <select id="ratingFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier rating</option>
            <option value="strong_buy">⭐ Strong Buy</option>
            <option value="buy">🟢 Buy o mejor</option>
            <option value="hold">🟡 Hold o mejor</option>
          </select>
          <select id="revenueFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier rev growth</option>
            <option value="0">Revenue &gt; 0%</option>
            <option value="10">Revenue &gt; 10%</option>
            <option value="20">Revenue &gt; 20%</option>
            <option value="50">Revenue &gt; 50%</option>
          </select>
          <select id="upsideFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier upside</option>
            <option value="30">Upside &gt; 30%</option>
            <option value="50">Upside &gt; 50%</option>
            <option value="100">Upside &gt; 100%</option>
          </select>
          <label class="flex items-center gap-1 cursor-pointer">
            <input id="safeRunwayOnly" type="checkbox" onchange="applyFilters()" class="accent-green-500">
            <span class="text-xs">💰 Solo cash runway sano</span>
          </label>
          <span id="resultsCount" class="text-xs text-neutral-400 ml-auto"></span>
        </div>
      </div>
    </div>

    <div class="card rounded-lg overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-neutral-900 text-xs text-neutral-400 uppercase">
          <tr>
            <th class="px-2 py-2 text-left">⭐</th>
            <th class="px-2 py-2 text-left sortable" onclick="sortBy('type')">Señal</th>
            <th class="px-2 py-2 text-left sortable" onclick="sortBy('ticker')">Ticker</th>
            <th class="px-2 py-2 text-left">Nombre</th>
            <th class="px-2 py-2 text-left sortable" onclick="sortBy('tier')">Cap</th>
            <th class="px-2 py-2 text-left">Sector</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('price')">Precio</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('wt2')">wt2</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('drawdown')">ATH↓</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('pe')">PER</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('ipo')">IPO</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('short')">Short</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('insider')">Ins</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('upside')">Up</th>
            <th class="px-2 py-2 text-center">Chart</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>

    <div id="emptyState" class="hidden text-center py-12 text-neutral-500">
      No hay señales que coincidan con los filtros.
    </div>
  </div>

  <footer class="text-center py-6 text-xs text-neutral-600">
    Generado el {{scan_date_human}} · CB Scanner v4.0
  </footer>
</div>

<div id="detailModal" class="modal-overlay" onclick="closeModalOnBackdrop(event)">
  <div class="modal-content" onclick="event.stopPropagation()">
    <div id="modalContent"></div>
  </div>
</div>

<script>
const SIGNALS_DATA = {{signals_json}};
const PWD_HASH = "{{password_hash}}";

let currentSort = { col: 'carvana', dir: 'desc' };
let filteredData = [];

async function hashPwd(pwd) {
  const buf = new TextEncoder().encode(pwd);
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, "0")).join("");
}

async function checkPassword() {
  const input = document.getElementById("passwordInput").value;
  const hash = await hashPwd(input);
  if (hash === PWD_HASH) {
    sessionStorage.setItem("cb_auth", "1");
    showContent();
  } else {
    document.getElementById("loginError").classList.remove("hidden");
  }
}

function showContent() {
  document.getElementById("loginOverlay").style.display = "none";
  document.getElementById("content").classList.remove("hidden");
  applyFilters();
}

if (sessionStorage.getItem("cb_auth") === "1") {
  showContent();
}

function getActiveSignals() {
  return SIGNALS_DATA.results.filter(r => r.active_signal !== null);
}

const RATING_LEVELS = {
  "strong_buy": 1, "buy": 2, "hold": 3, "sell": 4, "strong_sell": 5
};

function applyFilters() {
  const search = document.getElementById("searchInput").value.toLowerCase();
  const sig = document.getElementById("signalFilter").value;
  const tier = document.getElementById("tierFilter").value;
  const sector = document.getElementById("sectorFilter").value;
  const carvanaOnly = document.getElementById("carvanaOnly").checked;
  const drawdownMin = parseFloat(document.getElementById("drawdownFilter").value) || 0;
  const peMax = parseFloat(document.getElementById("peFilter").value) || Infinity;
  const ipoMax = parseFloat(document.getElementById("ipoFilter").value) || Infinity;
  const shortMin = parseFloat(document.getElementById("shortFilter").value) || 0;
  const insiderMin = parseFloat(document.getElementById("insiderFilter").value) || 0;
  const ratingMax = document.getElementById("ratingFilter").value;
  const revenueMin = document.getElementById("revenueFilter").value;
  const upsideMin = parseFloat(document.getElementById("upsideFilter").value) || -Infinity;
  const safeRunwayOnly = document.getElementById("safeRunwayOnly").checked;

  filteredData = getActiveSignals().filter(r => {
    if (search && !r.ticker.toLowerCase().includes(search)
        && !(r.name || "").toLowerCase().includes(search)) return false;
    if (sig && r.active_signal.type !== sig) return false;
    if (tier && r.cap_tier !== tier) return false;
    if (sector && r.sector !== sector) return false;
    if (carvanaOnly && !(r.carvana_setup && r.carvana_setup.is_carvana_setup)) return false;
    if (drawdownMin && Math.abs(r.drawdown_from_ath_pct) < drawdownMin) return false;
    if (peMax !== Infinity) {
      if (r.pe_trailing === null || r.pe_trailing === undefined) return false;
      if (r.pe_trailing > peMax || r.pe_trailing <= 0) return false;
    }
    if (ipoMax !== Infinity) {
      if (r.years_since_ipo === null || r.years_since_ipo === undefined) return false;
      if (r.years_since_ipo > ipoMax || r.years_since_ipo < 1) return false;
    }
    if (shortMin) {
      if (r.short_pct_float === null || r.short_pct_float === undefined) return false;
      if (r.short_pct_float < shortMin) return false;
    }
    if (insiderMin) {
      if (r.insider_pct === null || r.insider_pct === undefined) return false;
      if (r.insider_pct < insiderMin) return false;
    }
    if (ratingMax) {
      if (!r.recommendation) return false;
      const userLvl = RATING_LEVELS[ratingMax];
      const stockLvl = RATING_LEVELS[r.recommendation.toLowerCase()] || 99;
      if (stockLvl > userLvl) return false;
    }
    if (revenueMin !== "") {
      const minVal = parseFloat(revenueMin);
      if (r.revenue_growth === null || r.revenue_growth === undefined) return false;
      if (r.revenue_growth <= minVal) return false;
    }
    if (upsideMin > -Infinity) {
      if (r.upside_pct === null || r.upside_pct === undefined) return false;
      if (r.upside_pct < upsideMin) return false;
    }
    if (safeRunwayOnly) {
      const rw = r.cash_runway_years;
      if (rw !== null && rw !== undefined && rw !== 999 && rw < 2) return false;
    }
    return true;
  });

  sortAndRender();
}

function resetFilters() {
  document.getElementById("searchInput").value = "";
  document.getElementById("signalFilter").value = "";
  document.getElementById("tierFilter").value = "";
  document.getElementById("sectorFilter").value = "";
  document.getElementById("carvanaOnly").checked = false;
  document.getElementById("drawdownFilter").value = "";
  document.getElementById("peFilter").value = "";
  document.getElementById("ipoFilter").value = "";
  document.getElementById("shortFilter").value = "";
  document.getElementById("insiderFilter").value = "";
  document.getElementById("ratingFilter").value = "";
  document.getElementById("revenueFilter").value = "";
  document.getElementById("upsideFilter").value = "";
  document.getElementById("safeRunwayOnly").checked = false;
  applyFilters();
}

function sortBy(col) {
  if (currentSort.col === col) {
    currentSort.dir = currentSort.dir === "asc" ? "desc" : "asc";
  } else {
    currentSort.col = col;
    currentSort.dir = col === 'wt2' ? 'asc' : 'desc';
  }
  sortAndRender();
}

function getVal(r, col) {
  switch(col) {
    case 'carvana':  return (r.carvana_setup && r.carvana_setup.score) || 0;
    case 'type':     return r.active_signal.type;
    case 'ticker':   return r.ticker;
    case 'tier':     return r.cap_tier;
    case 'price':    return r.current_price;
    case 'wt2':      return r.active_signal.wt2;
    case 'drawdown': return r.drawdown_from_ath_pct;
    case 'pe':       return r.pe_trailing === null ? Infinity : r.pe_trailing;
    case 'ipo':      return r.years_since_ipo === null ? Infinity : r.years_since_ipo;
    case 'short':    return r.short_pct_float === null ? -1 : r.short_pct_float;
    case 'insider':  return r.insider_pct === null ? -1 : r.insider_pct;
    case 'upside':   return r.upside_pct === null ? -1000 : r.upside_pct;
    default: return 0;
  }
}

function sortAndRender() {
  const dir = currentSort.dir === "asc" ? 1 : -1;
  filteredData.sort((a, b) => {
    const va = getVal(a, currentSort.col);
    const vb = getVal(b, currentSort.col);
    if (typeof va === "string") return va.localeCompare(vb) * dir;
    return (va - vb) * dir;
  });
  render();
}

const SIG_BADGE = {
  "BUY_GOLD":  {cls: "badge-gold",  icon: "🏆", label: "BUY GOLD"},
  "BUY":       {cls: "badge-buy",   icon: "🟢", label: "BUY"},
  "SELL_PLUS": {cls: "badge-sellp", icon: "🔥", label: "SELL+"},
  "SELL":      {cls: "badge-sell",  icon: "🔴", label: "SELL"}
};
const TIER_BADGE = {
  "micro":  {cls: "tier-micro",  label: "Micro"},
  "small":  {cls: "tier-small",  label: "Small"},
  "mid":    {cls: "tier-mid",    label: "Mid"},
  "large":  {cls: "tier-large",  label: "Large"},
  "crypto": {cls: "tier-crypto", label: "Crypto"}
};
const RATING_LABEL = {
  "strong_buy":  "⭐ Strong Buy",
  "buy":         "🟢 Buy",
  "hold":        "🟡 Hold",
  "sell":        "🔴 Sell",
  "strong_sell": "🔴 Strong Sell"
};

function fmtPrice(p) {
  if (p === null || p === undefined) return "—";
  if (p >= 1000) return "$" + p.toLocaleString("en", {maximumFractionDigits: 0});
  if (p >= 10)   return "$" + p.toFixed(2);
  return "$" + p.toFixed(4);
}
function fmtNum(n, dec) {
  if (n === null || n === undefined) return "—";
  return n.toFixed(dec || 1);
}
function fmtPct(p, dec) {
  if (p === null || p === undefined) return "—";
  return p.toFixed(dec || 1) + "%";
}
function fmtBig(n) {
  if (n === null || n === undefined) return "—";
  if (n >= 1e9) return "$" + (n/1e9).toFixed(1) + "B";
  if (n >= 1e6) return "$" + (n/1e6).toFixed(1) + "M";
  return "$" + n.toFixed(0);
}
function fmtNumInt(n) {
  if (n === null || n === undefined) return "—";
  if (n >= 1e6) return (n/1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n/1e3).toFixed(0) + "K";
  return n.toString();
}
function fmtTV(ticker) {
  if (ticker.endsWith("-USD")) {
    return "https://www.tradingview.com/chart/?symbol=CRYPTO%3A" + ticker.replace("-USD", "USD");
  }
  return "https://www.tradingview.com/chart/?symbol=" + ticker;
}
function escapeHtml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function render() {
  const tbody = document.getElementById("tableBody");
  const empty = document.getElementById("emptyState");
  const count = document.getElementById("resultsCount");

  count.textContent = filteredData.length + " resultados";

  if (filteredData.length === 0) {
    tbody.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  tbody.innerHTML = filteredData.map((r, idx) => {
    const sig = r.active_signal;
    const sb = SIG_BADGE[sig.type] || {cls:"", icon:"?", label: sig.type};
    const tb = TIER_BADGE[r.cap_tier] || {cls:"", label: r.cap_tier};
    const isCarvana = r.carvana_setup && r.carvana_setup.is_carvana_setup;
    const score = (r.carvana_setup && r.carvana_setup.score) || 0;

    const carvanaCell = isCarvana
      ? '<span class="badge badge-carvana" title="Score ' + score + '/19">⭐ ' + score + '</span>'
      : '<span class="text-neutral-700 text-xs">' + (score > 0 ? score : '—') + '</span>';

    const pe = r.pe_trailing;
    const peTxt = pe === null || pe === undefined ? '—'
      : (pe <= 0 ? '<span class="text-red-400">neg</span>' : pe.toFixed(1));

    const ipo = r.years_since_ipo;
    const ipoTxt = ipo === null || ipo === undefined ? '—' : ipo.toFixed(1) + 'a';

    const sh = r.short_pct_float;
    const shTxt = sh === null || sh === undefined ? '—'
      : (sh >= 20 ? '<span class="text-orange-400">' + sh.toFixed(0) + '%</span>'
                  : sh.toFixed(0) + '%');

    const ins = r.insider_pct;
    const insTxt = ins === null || ins === undefined ? '—'
      : (ins >= 10 ? '<span class="text-green-400">' + ins.toFixed(0) + '%</span>'
                   : ins.toFixed(0) + '%');

    const up = r.upside_pct;
    const upTxt = up === null || up === undefined ? '—'
      : (up >= 50 ? '<span class="text-green-400">+' + up.toFixed(0) + '%</span>'
        : up < 0  ? '<span class="text-red-400">' + up.toFixed(0) + '%</span>'
                  : '+' + up.toFixed(0) + '%');

    return '<tr class="border-t border-neutral-800 row-clickable ' + (isCarvana ? 'row-carvana' : '') + '" onclick="openDetail(' + idx + ')">'
      + '<td class="px-2 py-2">' + carvanaCell + '</td>'
      + '<td class="px-2 py-2"><span class="badge ' + sb.cls + '">' + sb.icon + ' ' + sb.label + '</span></td>'
      + '<td class="px-2 py-2 font-bold">' + r.ticker + '</td>'
      + '<td class="px-2 py-2 text-neutral-400 max-w-[160px] truncate">' + escapeHtml(r.name || '') + '</td>'
      + '<td class="px-2 py-2"><span class="badge ' + tb.cls + '">' + tb.label + '</span></td>'
      + '<td class="px-2 py-2 text-neutral-400 text-xs max-w-[120px] truncate">' + escapeHtml(r.sector || '') + '</td>'
      + '<td class="px-2 py-2 text-right">' + fmtPrice(r.current_price) + '</td>'
      + '<td class="px-2 py-2 text-right ' + (sig.wt2 < 0 ? 'text-green-400' : 'text-red-400') + '">' + sig.wt2.toFixed(1) + '</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400">' + r.drawdown_from_ath_pct.toFixed(0) + '%</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400 text-xs">' + peTxt + '</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400 text-xs">' + ipoTxt + '</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400 text-xs">' + shTxt + '</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400 text-xs">' + insTxt + '</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400 text-xs">' + upTxt + '</td>'
      + '<td class="px-2 py-2 text-center">'
      + '<a href="' + fmtTV(r.ticker) + '" target="_blank" onclick="event.stopPropagation()" class="text-yellow-500 hover:text-yellow-300">📊</a>'
      + '</td></tr>';
  }).join("");
}

function openDetail(idx) {
  const r = filteredData[idx];
  const sig = r.active_signal;
  const sb = SIG_BADGE[sig.type] || {cls:"", icon:"?", label: sig.type};
  const tb = TIER_BADGE[r.cap_tier] || {cls:"", label: r.cap_tier};
  const cs = r.carvana_setup || {score: 0, max_score: 19, reasons: [], warnings: []};
  const ratingDisplay = r.recommendation ? (RATING_LABEL[r.recommendation.toLowerCase()] || r.recommendation) : '—';

  const reasonsHtml = (cs.reasons || []).map(rs =>
    '<div class="reason-item">✓ ' + escapeHtml(rs) + '</div>'
  ).join("");
  const warningsHtml = (cs.warnings || []).map(w =>
    '<div class="warning-item">' + escapeHtml(w) + '</div>'
  ).join("");

  const scorePct = Math.round((cs.score / (cs.max_score || 19)) * 100);

  const recentSigsHtml = (r.recent_signals || []).map(s => {
    const ic = SIG_BADGE[s.type] || {icon: "?", label: s.type};
    return '<div class="text-xs flex justify-between py-1 border-b border-neutral-800">'
      + '<span>' + ic.icon + ' ' + ic.label + '</span>'
      + '<span class="text-neutral-500">' + s.date + ' · $' + s.price.toFixed(2) + ' · wt2: ' + s.wt2.toFixed(1) + '</span>'
      + '</div>';
  }).join("");

  // NUEVO v4: Pills de información de empresa
  const pills = [];
  if (r.industry)  pills.push('<span class="info-pill">🏭 ' + escapeHtml(r.industry) + '</span>');
  if (r.country)   pills.push('<span class="info-pill">🌍 ' + escapeHtml(r.country) + '</span>');
  if (r.employees) pills.push('<span class="info-pill">👥 ' + fmtNumInt(r.employees) + ' empleados</span>');
  if (r.website)   pills.push('<span class="info-pill">🔗 <a href="' + escapeHtml(r.website) + '" target="_blank" class="hover:underline">Web oficial</a></span>');
  if (r.dividend_yield && r.dividend_yield > 0) {
    pills.push('<span class="info-pill">💵 Div ' + r.dividend_yield.toFixed(2) + '%</span>');
  }
  const pillsHtml = pills.length ? '<div class="mt-3">' + pills.join('') + '</div>' : '';

  // NUEVO v4: Descripción de la empresa
  const summaryHtml = r.long_summary
    ? `<div class="mb-4">
         <div class="text-xs text-neutral-500 uppercase mb-2">📖 Sobre la empresa</div>
         <div class="company-summary">${escapeHtml(r.long_summary)}</div>
         <p class="text-xs text-neutral-600 mt-1 italic">Descripción en inglés (fuente: Yahoo Finance)</p>
       </div>`
    : '';

  const html = `
    <div class="flex justify-between items-start mb-4">
      <div class="flex-1">
        <h2 class="text-2xl font-bold">${escapeHtml(r.ticker)}</h2>
        <p class="text-sm text-neutral-400">${escapeHtml(r.name || '')}</p>
        <div class="flex gap-2 mt-2 flex-wrap">
          <span class="badge ${sb.cls}">${sb.icon} ${sb.label}</span>
          <span class="badge ${tb.cls}">${tb.label}</span>
          ${cs.is_carvana_setup ? '<span class="badge badge-carvana">⭐ CARVANA SETUP</span>' : ''}
        </div>
        ${pillsHtml}
      </div>
      <button onclick="closeModal()" class="text-neutral-400 hover:text-white text-xl ml-2">✕</button>
    </div>

    ${summaryHtml}

    <div class="grid grid-cols-2 gap-3 mb-4">
      <div class="card p-3 rounded">
        <div class="text-xs text-neutral-500 mb-1">PRECIO ACTUAL</div>
        <div class="text-xl font-bold">${fmtPrice(r.current_price)}</div>
        <div class="text-xs text-neutral-500 mt-1">ATH: ${fmtPrice(r.ath)}</div>
      </div>
      <div class="card p-3 rounded">
        <div class="text-xs text-neutral-500 mb-1">DRAWDOWN</div>
        <div class="text-xl font-bold text-red-400">${r.drawdown_from_ath_pct.toFixed(0)}%</div>
        <div class="text-xs text-neutral-500 mt-1">52w: ${fmtNum(r.position_52w_pct, 0)}%</div>
      </div>
    </div>

    ${cs.score > 0 ? `
    <div class="card p-3 rounded mb-4">
      <div class="flex justify-between items-center mb-1">
        <span class="text-sm font-semibold">⭐ Carvana Setup Score</span>
        <span class="text-lg font-bold">${cs.score} / ${cs.max_score || 19}</span>
      </div>
      <div class="score-bar"><div class="score-fill" style="width: ${scorePct}%"></div></div>
      <div class="mt-3">
        ${reasonsHtml}
        ${warningsHtml}
      </div>
    </div>
    ` : ''}

    <div class="grid grid-cols-2 gap-3 mb-4">
      <div>
        <div class="text-xs text-neutral-500 uppercase mb-2">Valoración</div>
        <div class="metric-row"><span class="metric-label">PER trailing</span><span class="metric-value">${fmtNum(r.pe_trailing)}</span></div>
        <div class="metric-row"><span class="metric-label">PER forward</span><span class="metric-value">${fmtNum(r.pe_forward)}</span></div>
        <div class="metric-row"><span class="metric-label">P/Book</span><span class="metric-value">${fmtNum(r.price_to_book)}</span></div>
        <div class="metric-row"><span class="metric-label">P/Sales</span><span class="metric-value">${fmtNum(r.price_to_sales)}</span></div>
      </div>
      <div>
        <div class="text-xs text-neutral-500 uppercase mb-2">Crecimiento</div>
        <div class="metric-row"><span class="metric-label">Revenue YoY</span><span class="metric-value">${fmtPct(r.revenue_growth)}</span></div>
        <div class="metric-row"><span class="metric-label">Earnings YoY</span><span class="metric-value">${fmtPct(r.earnings_growth)}</span></div>
        <div class="metric-row"><span class="metric-label">Op. margin</span><span class="metric-value">${fmtPct(r.operating_margin)}</span></div>
        <div class="metric-row"><span class="metric-label">Profit margin</span><span class="metric-value">${fmtPct(r.profit_margin)}</span></div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-4">
      <div>
        <div class="text-xs text-neutral-500 uppercase mb-2">Salud financiera</div>
        <div class="metric-row"><span class="metric-label">Debt/Equity</span><span class="metric-value">${fmtNum(r.debt_to_equity)}</span></div>
        <div class="metric-row"><span class="metric-label">Total cash</span><span class="metric-value">${fmtBig(r.total_cash)}</span></div>
        <div class="metric-row"><span class="metric-label">Free CF</span><span class="metric-value">${fmtBig(r.free_cashflow)}</span></div>
        <div class="metric-row"><span class="metric-label">Runway</span><span class="metric-value">${r.cash_runway_years === 999 ? '✅ FCF+' : fmtNum(r.cash_runway_years) + ' años'}</span></div>
      </div>
      <div>
        <div class="text-xs text-neutral-500 uppercase mb-2">Mercado</div>
        <div class="metric-row"><span class="metric-label">Short % float</span><span class="metric-value">${fmtPct(r.short_pct_float, 1)}</span></div>
        <div class="metric-row"><span class="metric-label">Insider %</span><span class="metric-value">${fmtPct(r.insider_pct, 1)}</span></div>
        <div class="metric-row"><span class="metric-label">Beta</span><span class="metric-value">${fmtNum(r.beta, 2)}</span></div>
        <div class="metric-row"><span class="metric-label">Years IPO</span><span class="metric-value">${fmtNum(r.years_since_ipo)}</span></div>
      </div>
    </div>

    <div class="card p-3 rounded mb-4">
      <div class="text-xs text-neutral-500 uppercase mb-2">Analistas</div>
      <div class="grid grid-cols-3 gap-3 text-center">
        <div>
          <div class="text-xs text-neutral-500">Target</div>
          <div class="text-lg font-bold">${fmtPrice(r.target_price)}</div>
        </div>
        <div>
          <div class="text-xs text-neutral-500">Upside</div>
          <div class="text-lg font-bold ${r.upside_pct > 0 ? 'metric-good' : 'metric-bad'}">${fmtPct(r.upside_pct, 0)}</div>
        </div>
        <div>
          <div class="text-xs text-neutral-500">Rating</div>
          <div class="text-sm font-bold">${ratingDisplay}</div>
        </div>
      </div>
    </div>

    ${recentSigsHtml ? `
    <div class="card p-3 rounded mb-4">
      <div class="text-xs text-neutral-500 uppercase mb-2">Últimas señales</div>
      ${recentSigsHtml}
    </div>
    ` : ''}

    <div class="flex gap-2">
      <a href="${fmtTV(r.ticker)}" target="_blank"
        class="flex-1 bg-yellow-500 text-black font-semibold py-2 rounded text-center hover:bg-yellow-400">
        📊 Ver chart en TradingView
      </a>
      <button onclick="closeModal()"
        class="bg-neutral-700 text-white px-4 py-2 rounded hover:bg-neutral-600">
        Cerrar
      </button>
    </div>
  `;

  document.getElementById("modalContent").innerHTML = html;
  document.getElementById("detailModal").classList.add("open");
}

function closeModal() {
  document.getElementById("detailModal").classList.remove("open");
}
function closeModalOnBackdrop(e) {
  if (e.target.id === "detailModal") closeModal();
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});
</script>

</body>
</html>
"""


def generate_html():
    if not os.path.exists(SIGNALS_JSON):
        print(f"❌ No existe {SIGNALS_JSON}")
        print("   Ejecuta primero: python3 main.py")
        return False

    with open(SIGNALS_JSON) as f:
        signals_data = json.load(f)
    with open(SUMMARY_JSON) as f:
        summary_data = json.load(f)

    by_sig = summary_data.get("by_signal", {})
    count_gold  = by_sig.get("BUY_GOLD", 0)
    count_buy   = by_sig.get("BUY", 0)
    count_sellp = by_sig.get("SELL_PLUS", 0)
    count_sell  = by_sig.get("SELL", 0)
    count_carvana = summary_data.get("total_carvana_setups", 0)

    sectors = set()
    for r in signals_data["results"]:
        if r.get("sector"):
            sectors.add(r["sector"])
    sector_options = "\n".join([f'<option value="{s}">{s}</option>'
                                for s in sorted(sectors)])

    pwd_hash = hashlib.sha256(PASSWORD.encode()).hexdigest()

    html = HTML_TEMPLATE
    html = html.replace("{{scan_date_human}}", signals_data["scan_date_human"])
    html = html.replace("{{total_scanned}}",   str(signals_data["total_scanned"]))
    html = html.replace("{{count_carvana}}",   str(count_carvana))
    html = html.replace("{{count_gold}}",      str(count_gold))
    html = html.replace("{{count_buy}}",       str(count_buy))
    html = html.replace("{{count_sellp}}",     str(count_sellp))
    html = html.replace("{{count_sell}}",      str(count_sell))
    html = html.replace("{{sector_options}}",  sector_options)
    html = html.replace("{{signals_json}}",    json.dumps(signals_data))
    html = html.replace("{{password_hash}}",   pwd_hash)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_HTML, "w") as f:
        f.write(html)
    print(f"✅ HTML generado: {OUTPUT_HTML}")

    import shutil
    shutil.copy(SIGNALS_JSON, OUTPUT_JSON)
    shutil.copy(SUMMARY_JSON, OUTPUT_SUMMARY)

    print(f"\n🔑 Contraseña: '{PASSWORD}'")
    print("\n📂 Para ver la web:")
    print(f"   open {OUTPUT_HTML}\n")

    return True


if __name__ == "__main__":
    print("═" * 60)
    print("  CB SCANNER — Generador HTML v4")
    print("═" * 60 + "\n")
    generate_html()
