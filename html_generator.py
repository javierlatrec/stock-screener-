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
  .badge-ch-high { background: linear-gradient(135deg, #a855f7, #ec4899);
                   color: #fff; font-weight: 700; }
  .badge-ch-buy  { background: #8b5cf6; color: #fff; font-weight: 600; }
  .badge-ch-gold { background: linear-gradient(135deg, #14b8a6, #fbbf24);
                   color: #000; font-weight: 700; }
  .badge-ch-exit { background: #dc2626; color: #fff; font-weight: 600; }
  tr.row-ch-entry { background: rgba(168, 85, 247, 0.06); }
  tr.row-ch-entry:hover { background: rgba(168, 85, 247, 0.12); }
  .tab-active { background: #fbbf24; color: #000; }
  .tab-inactive { background: transparent; color: #a3a3a3; }
  .tab-inactive:hover { color: #fff; }
  .sector-card {
    background: #141414; border: 1px solid #262626;
    border-left-width: 4px; border-radius: 8px; padding: 12px;
    transition: background 0.1s;
  }
  .sector-card:hover { background: #1a1a1a; }
  .sec-green      { border-left-color: #10b981; background: rgba(16,185,129,0.06); }
  .sec-greenlight { border-left-color: #65a30d; }
  .sec-red        { border-left-color: #ef4444; background: rgba(239,68,68,0.06); }
  .sec-gray       { border-left-color: #525252; }
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
        <div class="flex items-center gap-1 bg-neutral-800 rounded-lg p-1">
          <button id="tabWeekly" onclick="setView('weekly')"
            class="px-4 py-1.5 rounded-md text-sm font-semibold transition">
            📅 Semanal
          </button>
          <button id="tabMonthly" onclick="setView('monthly')"
            class="px-4 py-1.5 rounded-md text-sm font-semibold transition">
            🗓️ Mensual
          </button>
          <button id="tabSectors" onclick="setView('sectors')"
            class="px-4 py-1.5 rounded-md text-sm font-semibold transition">
            🗺️ Sectores
          </button>
        </div>
        <div class="flex gap-2 items-center text-sm flex-wrap">
          <span class="badge badge-carvana">⭐ {{count_carvana}}</span>
          <span class="badge badge-ch-high">🎯 {{count_ch}}</span>
          <span class="badge badge-gold">🏆 {{count_gold}}</span>
          <span class="badge badge-buy">🟢 {{count_buy}}</span>
          <span class="badge badge-sellp">🔥 {{count_sellp}}</span>
          <span class="badge badge-sell">🔴 {{count_sell}}</span>
        </div>
      </div>
    </div>
  </header>

  <!-- FILTERS -->
  <div id="stocksView" class="max-w-7xl mx-auto px-4 py-4">
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

        <span id="chControls" class="flex gap-2 flex-wrap items-center">
        <label class="flex items-center gap-2 cursor-pointer bg-neutral-800 px-3 py-2 rounded">
          <input id="chEntryOnly" type="checkbox" onchange="applyFilters()" class="accent-purple-500">
          <span class="text-sm">🎯 Solo CH entrada</span>
        </label>

        <select id="chFilter" onchange="applyFilters()"
          class="bg-neutral-800 text-white px-3 py-2 rounded outline-none text-sm">
          <option value="">CH: cualquiera</option>
          <option value="ASH_HIGH">💎 ASH HIGH</option>
          <option value="WT_SELL_PLUS">🔴 WT SELL+ (salida)</option>
        </select>
        </span>

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

      <div class="mt-3 pt-3 border-t border-neutral-800">
        <div class="text-xs text-neutral-500 mb-2 uppercase">Filtros avanzados (Mejora 2)</div>
        <div class="flex gap-2 flex-wrap items-center text-sm">
          <select id="instFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier institucional</option>
            <option value="30">Inst. ≥ 30%</option>
            <option value="50">Inst. ≥ 50%</option>
            <option value="70">Inst. ≥ 70%</option>
          </select>
          <select id="w52Filter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier 52w</option>
            <option value="-30">52w &lt; -30%</option>
            <option value="-50">52w &lt; -50%</option>
            <option value="-70">52w &lt; -70%</option>
            <option value="up">52w &gt; 0% (recuperando)</option>
          </select>
          <select id="volFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier volumen</option>
            <option value="500000">Vol ≥ 500K</option>
            <option value="1000000">Vol ≥ 1M</option>
            <option value="5000000">Vol ≥ 5M</option>
          </select>
          <select id="floatFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier float</option>
            <option value="50000000">Float &lt; 50M (squeeze)</option>
            <option value="20000000">Float &lt; 20M (squeeze fuerte)</option>
            <option value="10000000">Float &lt; 10M (micro float)</option>
          </select>
          <select id="earningsFilter" onchange="applyFilters()" class="bg-neutral-800 text-white px-2 py-1 rounded text-xs">
            <option value="">Cualquier earnings</option>
            <option value="0">Earnings &gt; 0% (beat)</option>
            <option value="20">Earnings &gt; 20%</option>
            <option value="50">Earnings &gt; 50%</option>
          </select>
        </div>
      </div>
    </div>

    <div class="card rounded-lg overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-neutral-900 text-xs text-neutral-400 uppercase">
          <tr>
            <th class="px-2 py-2 text-left">⭐</th>
            <th id="thCH" class="px-2 py-2 text-left">🎯CH</th>
            <th class="px-2 py-2 text-left sortable" onclick="sortBy('type')">Señal</th>
            <th class="px-2 py-2 text-left sortable" onclick="sortBy('ticker')">Ticker</th>
            <th class="px-2 py-2 text-left">Nombre</th>
            <th class="px-2 py-2 text-left sortable" onclick="sortBy('tier')">Cap</th>
            <th class="px-2 py-2 text-left">Sector</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('price')">Precio</th>
            <th id="thMetric" class="px-2 py-2 text-right sortable" onclick="sortBy('wt2')">wt2</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('drawdown')">ATH↓</th>
            <th class="px-2 py-2 text-right sortable" onclick="sortBy('w52')">52w</th>
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

  <!-- SECTORS VIEW -->
  <div id="sectorsView" class="max-w-7xl mx-auto px-4 py-4 hidden">
    <p class="text-sm text-neutral-400 mb-4">
      🗺️ Mapa de mercado por sectores y temáticas. Verde = momento alcista (entrada/zona baja girando), Rojo = momento de techo/salida, Gris = neutral.
      Úsalo para ver dónde buscar acciones: si un sector está girando al alza, busca sus tickers en las pestañas Semanal/Mensual.
    </p>
    <div id="sectorsContent"></div>
  </div>

  <footer class="text-center py-6 text-xs text-neutral-600">
    Generado el {{scan_date_human}} · CB Scanner v5.0
  </footer>
</div>

<div id="detailModal" class="modal-overlay" onclick="closeModalOnBackdrop(event)">
  <div class="modal-content" onclick="event.stopPropagation()">
    <div id="modalContent"></div>
  </div>
</div>

<script>
const SIGNALS_DATA = {{signals_json}};
const SECTORS_DATA = {{sectors_json}};
const PWD_HASH = "{{password_hash}}";

let currentSort = { col: 'carvana', dir: 'desc' };
let filteredData = [];
let currentView = 'weekly';   // 'weekly' (ASH+MFI) | 'monthly' (WT CB)

function setView(view) {
  currentView = view;
  document.getElementById('tabWeekly').className =
    'px-4 py-1.5 rounded-md text-sm font-semibold transition ' +
    (view === 'weekly' ? 'tab-active' : 'tab-inactive');
  document.getElementById('tabMonthly').className =
    'px-4 py-1.5 rounded-md text-sm font-semibold transition ' +
    (view === 'monthly' ? 'tab-active' : 'tab-inactive');
  const tabSectors = document.getElementById('tabSectors');
  if (tabSectors) tabSectors.className =
    'px-4 py-1.5 rounded-md text-sm font-semibold transition ' +
    (view === 'sectors' ? 'tab-active' : 'tab-inactive');

  const stocksView = document.getElementById('stocksView');
  const sectorsView = document.getElementById('sectorsView');
  if (view === 'sectors') {
    if (stocksView) stocksView.classList.add('hidden');
    if (sectorsView) sectorsView.classList.remove('hidden');
    renderSectors();
    return;
  }
  if (stocksView) stocksView.classList.remove('hidden');
  if (sectorsView) sectorsView.classList.add('hidden');

  const chControls = document.getElementById('chControls');
  if (chControls) chControls.style.display = view === 'weekly' ? '' : 'none';
  const thCH = document.getElementById('thCH');
  if (thCH) thCH.style.display = view === 'weekly' ? '' : 'none';
  const thMetric = document.getElementById('thMetric');
  if (thMetric) thMetric.textContent = view === 'weekly' ? 'MFI' : 'wt2';
  applyFilters();
}

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
  setView('weekly');
}

if (sessionStorage.getItem("cb_auth") === "1") {
  showContent();
}

function getActiveSignals() {
  if (currentView === 'monthly') {
    return SIGNALS_DATA.results.filter(r => r.active_signal !== null);
  }
  return SIGNALS_DATA.results.filter(r =>
    r.carvana_hunter && (r.carvana_hunter.active_entry || r.carvana_hunter.active_exit)
  );
}

// Señal "efectiva" del ticker según la vista activa
function effSignal(r) {
  if (currentView === 'monthly') return r.active_signal;
  const ch = r.carvana_hunter;
  if (!ch) return null;
  if (ch.active_entry === 'ASH_HIGH')
    return { type: 'ASH_HIGH', wt2: ch.mfi_value, date: '', price: r.current_price };
  if (ch.active_exit === 'WT_SELL_PLUS')
    return { type: 'WT_SELL_PLUS', wt2: ch.mfi_value, date: '', price: r.current_price };
  return null;
}

const CH_BADGE = {
  "ASH_HIGH":       {cls: "badge-ch-high", icon: "💎", label: "ASH HIGH"},
  "ASH_BUY_STRONG": {cls: "badge-ch-buy",  icon: "🟣", label: "ASH BUY"},
  "WT_BUY_GOLD":    {cls: "badge-ch-gold", icon: "🎯", label: "WT GOLD"},
  "WT_SELL_PLUS":   {cls: "badge-ch-exit", icon: "🔴", label: "WT SELL+"}
};

const RATING_LEVELS = {
  "strong_buy": 1, "buy": 2, "hold": 3, "sell": 4, "strong_sell": 5
};

function applyFilters() {
  const search = document.getElementById("searchInput").value.toLowerCase();
  const sig = document.getElementById("signalFilter").value;
  const tier = document.getElementById("tierFilter").value;
  const sector = document.getElementById("sectorFilter").value;
  const carvanaOnly = document.getElementById("carvanaOnly").checked;
  const chEntryOnly = document.getElementById("chEntryOnly").checked;
  const chType = document.getElementById("chFilter").value;
  const drawdownMin = parseFloat(document.getElementById("drawdownFilter").value) || 0;
  const peMax = parseFloat(document.getElementById("peFilter").value) || Infinity;
  const ipoMax = parseFloat(document.getElementById("ipoFilter").value) || Infinity;
  const shortMin = parseFloat(document.getElementById("shortFilter").value) || 0;
  const insiderMin = parseFloat(document.getElementById("insiderFilter").value) || 0;
  const ratingMax = document.getElementById("ratingFilter").value;
  const revenueMin = document.getElementById("revenueFilter").value;
  const upsideMin = parseFloat(document.getElementById("upsideFilter").value) || -Infinity;
  const safeRunwayOnly = document.getElementById("safeRunwayOnly").checked;
  const instMin = parseFloat(document.getElementById("instFilter").value) || 0;
  const w52Raw = document.getElementById("w52Filter").value;
  const volMin = parseFloat(document.getElementById("volFilter").value) || 0;
  const floatMax = parseFloat(document.getElementById("floatFilter").value) || Infinity;
  const earningsRaw = document.getElementById("earningsFilter").value;

  filteredData = getActiveSignals().filter(r => {
    if (search && !r.ticker.toLowerCase().includes(search)
        && !(r.name || "").toLowerCase().includes(search)) return false;
    if (sig) { const es = effSignal(r); if (!es || es.type !== sig) return false; }
    if (tier && r.cap_tier !== tier) return false;
    if (sector && r.sector !== sector) return false;
    if (carvanaOnly && !(r.carvana_setup && r.carvana_setup.is_carvana_setup)) return false;
    if (chEntryOnly && !(r.carvana_hunter && r.carvana_hunter.active_entry)) return false;
    if (chType) {
      const ch = r.carvana_hunter;
      if (!ch) return false;
      if (chType === "WT_SELL_PLUS") {
        if (ch.active_exit !== "WT_SELL_PLUS") return false;
      } else if (chType === "ASH_BUY_STRONG") {
        if (!ch.ash_buy_strong) return false;
      } else {
        if (ch.active_entry !== chType) return false;
      }
    }
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
    if (instMin) {
      if (r.institutional_pct === null || r.institutional_pct === undefined) return false;
      if (r.institutional_pct < instMin) return false;
    }
    if (w52Raw) {
      const v = r.fiftytwo_week_change;
      if (v === null || v === undefined) return false;
      if (w52Raw === "up") {
        if (v <= 0) return false;
      } else {
        if (v > parseFloat(w52Raw)) return false;
      }
    }
    if (volMin) {
      if (r.avg_volume === null || r.avg_volume === undefined) return false;
      if (r.avg_volume < volMin) return false;
    }
    if (floatMax !== Infinity) {
      if (r.float_shares === null || r.float_shares === undefined) return false;
      if (r.float_shares > floatMax) return false;
    }
    if (earningsRaw !== "") {
      const minVal = parseFloat(earningsRaw);
      if (r.earnings_beat_pct === null || r.earnings_beat_pct === undefined) return false;
      if (r.earnings_beat_pct <= minVal) return false;
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
  document.getElementById("chEntryOnly").checked = false;
  document.getElementById("chFilter").value = "";
  document.getElementById("drawdownFilter").value = "";
  document.getElementById("peFilter").value = "";
  document.getElementById("ipoFilter").value = "";
  document.getElementById("shortFilter").value = "";
  document.getElementById("insiderFilter").value = "";
  document.getElementById("ratingFilter").value = "";
  document.getElementById("revenueFilter").value = "";
  document.getElementById("upsideFilter").value = "";
  document.getElementById("safeRunwayOnly").checked = false;
  document.getElementById("instFilter").value = "";
  document.getElementById("w52Filter").value = "";
  document.getElementById("volFilter").value = "";
  document.getElementById("floatFilter").value = "";
  document.getElementById("earningsFilter").value = "";
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
  const es = effSignal(r);
  switch(col) {
    case 'carvana':  return (r.carvana_setup && r.carvana_setup.score) || 0;
    case 'type':     return es ? es.type : 'zzz';
    case 'ticker':   return r.ticker;
    case 'tier':     return r.cap_tier;
    case 'price':    return r.current_price;
    case 'wt2':      return es && es.wt2 !== null && es.wt2 !== undefined ? es.wt2 : 999;
    case 'drawdown': return r.drawdown_from_ath_pct;
    case 'w52':      return r.fiftytwo_week_change === null || r.fiftytwo_week_change === undefined ? Infinity : r.fiftytwo_week_change;
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
  "SELL":      {cls: "badge-sell",  icon: "🔴", label: "SELL"},
  "ASH_HIGH":    {cls: "badge-ch-high", icon: "💎", label: "ASH HIGH"},
  "WT_BUY_GOLD": {cls: "badge-ch-gold", icon: "🎯", label: "WT GOLD"},
  "WT_SELL_PLUS":{cls: "badge-ch-exit", icon: "🔴", label: "WT SELL+"}
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
    const sig = effSignal(r);
    const sb = sig ? (SIG_BADGE[sig.type] || {cls:"", icon:"?", label: sig.type})
                   : {cls:"", icon:"·", label:"—"};
    const tb = TIER_BADGE[r.cap_tier] || {cls:"", label: r.cap_tier};
    const isCarvana = r.carvana_setup && r.carvana_setup.is_carvana_setup;
    const score = (r.carvana_setup && r.carvana_setup.score) || 0;
    const weekly = currentView === 'weekly';

    const ch = r.carvana_hunter;
    const chEntry = ch && ch.active_entry;
    const chExit = ch && ch.active_exit;
    let chCell = '<span class="text-neutral-700 text-xs">—</span>';
    if (chEntry) {
      const cb = CH_BADGE[chEntry] || {cls:"", icon:"?", label: chEntry};
      chCell = '<span class="badge ' + cb.cls + '">' + cb.icon + ' ' + cb.label + '</span>';
    } else if (chExit) {
      const cb = CH_BADGE["WT_SELL_PLUS"];
      chCell = '<span class="badge ' + cb.cls + '">' + cb.icon + ' ' + cb.label + '</span>';
    } else if (ch && ch.ash_buy_strong) {
      chCell = '<span class="text-neutral-500 text-xs" title="ASH BUY STRONG sin convicción MFI">🔵 buy</span>';
    }

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

    const w52 = r.fiftytwo_week_change;
    const w52Txt = w52 === null || w52 === undefined ? '—'
      : (w52 < 0 ? '<span class="text-red-400">' + w52.toFixed(0) + '%</span>'
                 : '<span class="text-green-400">+' + w52.toFixed(0) + '%</span>');

    // Columna WT2/MFI: en semanal muestra MFI; en mensual muestra wt2
    let metricVal = '—', metricCls = 'text-neutral-400';
    if (weekly) {
      const m = ch ? ch.mfi_value : null;
      if (m !== null && m !== undefined) {
        metricVal = m.toFixed(1);
        metricCls = m < 0 ? 'text-green-400' : 'text-red-400';
      }
    } else if (sig && sig.wt2 !== null && sig.wt2 !== undefined) {
      metricVal = sig.wt2.toFixed(1);
      metricCls = sig.wt2 < 0 ? 'text-green-400' : 'text-red-400';
    }

    const chCol = weekly ? ('<td class="px-2 py-2">' + chCell + '</td>') : '';

    return '<tr class="border-t border-neutral-800 row-clickable ' + (isCarvana ? 'row-carvana ' : '') + (chEntry ? 'row-ch-entry' : '') + '" onclick="openDetail(' + idx + ')">'
      + '<td class="px-2 py-2">' + carvanaCell + '</td>'
      + chCol
      + '<td class="px-2 py-2"><span class="badge ' + sb.cls + '">' + sb.icon + ' ' + sb.label + '</span></td>'
      + '<td class="px-2 py-2 font-bold">' + r.ticker + '</td>'
      + '<td class="px-2 py-2 text-neutral-400 max-w-[160px] truncate">' + escapeHtml(r.name || '') + '</td>'
      + '<td class="px-2 py-2"><span class="badge ' + tb.cls + '">' + tb.label + '</span></td>'
      + '<td class="px-2 py-2 text-neutral-400 text-xs max-w-[120px] truncate">' + escapeHtml(r.sector || '') + '</td>'
      + '<td class="px-2 py-2 text-right">' + fmtPrice(r.current_price) + '</td>'
      + '<td class="px-2 py-2 text-right ' + metricCls + '">' + metricVal + '</td>'
      + '<td class="px-2 py-2 text-right text-neutral-400">' + r.drawdown_from_ath_pct.toFixed(0) + '%</td>'
      + '<td class="px-2 py-2 text-right text-xs">' + w52Txt + '</td>'
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
  if (r) openDetailObj(r);
}

function openDetailObj(r) {
  const sig = r.active_signal;
  const sb = sig ? (SIG_BADGE[sig.type] || {cls:"", icon:"?", label: sig.type})
                 : {cls:"", icon:"·", label:"Sin señal CB"};
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

  // MEJORA 3: Empresas similares
  const similarHtml = (r.similar_tickers || []).map(s => {
    const icon = s.carvana ? '⭐' : (s.active ? '🟢' : '');
    return '<button onclick="openDetailByTicker(\'' + s.ticker + '\')" '
      + 'class="info-pill hover:bg-neutral-700 cursor-pointer" '
      + 'style="border:1px solid #404040;">'
      + '<span class="font-bold text-yellow-500">' + s.ticker + '</span> '
      + '<span class="text-neutral-400">' + escapeHtml((s.name || '').slice(0, 18)) + '</span> '
      + (icon ? '<span>' + icon + '</span>' : '')
      + '</button>';
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
  if (r.institutional_pct && r.institutional_pct > 0) {
    pills.push('<span class="info-pill">🏛️ Inst ' + r.institutional_pct.toFixed(0) + '%</span>');
  }
  if (r.earnings_beat_pct !== null && r.earnings_beat_pct !== undefined) {
    const sign = r.earnings_beat_pct >= 0 ? '+' : '';
    pills.push('<span class="info-pill">📈 Earn ' + sign + r.earnings_beat_pct.toFixed(0) + '%</span>');
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

  // NUEVO: Bloque Carvana Hunter
  const ch = r.carvana_hunter;
  let chHtml = '';
  if (ch && (ch.active_entry || ch.active_exit || ch.weekly_checked || ch.wt_buy_gold)) {
    const fmtBars = (b) => b === null || b === undefined ? '' :
      (b === 0 ? ' (esta barra)' : ' (hace ' + b + ' barra' + (b > 1 ? 's' : '') + ')');
    const rows = [];
    // Entrada destacada
    if (ch.active_entry) {
      const cb = CH_BADGE[ch.active_entry] || {icon:'?', label: ch.active_entry};
      rows.push('<div class="reason-item" style="background:rgba(168,85,247,0.12);border-left-color:#a855f7;">'
        + '🎯 <b>ENTRADA: ' + cb.icon + ' ' + cb.label + '</b></div>');
    }
    if (ch.active_exit) {
      rows.push('<div class="warning-item">🔴 <b>SALIDA: WT SELL+</b>'
        + fmtBars(ch.wt_sell_plus_bars) + ' — cerrar posición</div>');
    }
    // Detalle ASH semanal
    const ashDetail = [];
    if (ch.ash_buy_strong) {
      ashDetail.push('<div class="metric-row"><span class="metric-label">ASH BUY STRONG</span>'
        + '<span class="metric-value metric-good">✓' + fmtBars(ch.ash_buy_strong_bars) + '</span></div>');
    }
    if (ch.high_conviction) {
      ashDetail.push('<div class="metric-row"><span class="metric-label">💎 HIGH CONVICTION</span>'
        + '<span class="metric-value metric-good">✓ MFI confirmando</span></div>');
    }
    if (ch.ash_value !== null && ch.ash_value !== undefined) {
      ashDetail.push('<div class="metric-row"><span class="metric-label">Histograma ASH</span>'
        + '<span class="metric-value ' + (ch.ash_value > 0 ? 'metric-good' : 'metric-bad') + '">'
        + ch.ash_value.toFixed(3) + '</span></div>');
    }
    if (ch.mfi_value !== null && ch.mfi_value !== undefined) {
      ashDetail.push('<div class="metric-row"><span class="metric-label">MFI (centrado)</span>'
        + '<span class="metric-value ' + (ch.mfi_value < 0 ? 'metric-bad' : 'metric-good') + '">'
        + ch.mfi_value.toFixed(1) + '</span></div>');
    }
    // Detalle WT mensual
    const wtDetail = [];
    if (ch.wt_buy_gold) {
      wtDetail.push('<div class="metric-row"><span class="metric-label">WT BUY GOLD (mensual)</span>'
        + '<span class="metric-value metric-good">✓ wt2≤-60' + fmtBars(ch.wt_buy_gold_bars) + '</span></div>');
    }
    if (ch.wt_sell_plus) {
      wtDetail.push('<div class="metric-row"><span class="metric-label">WT SELL+ (mensual)</span>'
        + '<span class="metric-value metric-bad">✓ wt2≥60' + fmtBars(ch.wt_sell_plus_bars) + '</span></div>');
    }

    const weeklyNote = ch.weekly_checked
      ? ''
      : '<p class="text-xs text-neutral-600 mt-2 italic">Semanal no evaluado (drawdown por encima del gate ' + '−50%). Solo señales WaveTrend mensuales.</p>';

    chHtml = `
    <div class="card p-3 rounded mb-4" style="border-color:#a855f7;">
      <div class="flex justify-between items-center mb-2">
        <span class="text-sm font-semibold">🎯 Carvana Hunter</span>
        <span class="text-xs text-neutral-500">393 trades · PF 3.50 · 58% WR</span>
      </div>
      ${rows.join('')}
      ${ashDetail.length ? '<div class="mt-2"><div class="text-xs text-neutral-500 uppercase mb-1">Entrada semanal (ASH L21 S3)</div>' + ashDetail.join('') + '</div>' : ''}
      ${wtDetail.length ? '<div class="mt-2"><div class="text-xs text-neutral-500 uppercase mb-1">WaveTrend mensual</div>' + wtDetail.join('') + '</div>' : ''}
      ${weeklyNote}
    </div>`;
  }

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

    ${chHtml}

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
        <div class="metric-row"><span class="metric-label">Institucional %</span><span class="metric-value">${fmtPct(r.institutional_pct, 1)}</span></div>
        <div class="metric-row"><span class="metric-label">Beta</span><span class="metric-value">${fmtNum(r.beta, 2)}</span></div>
        <div class="metric-row"><span class="metric-label">Years IPO</span><span class="metric-value">${fmtNum(r.years_since_ipo)}</span></div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-4">
      <div>
        <div class="text-xs text-neutral-500 uppercase mb-2">Liquidez & Float</div>
        <div class="metric-row"><span class="metric-label">Volumen medio</span><span class="metric-value">${fmtNumInt(r.avg_volume)}</span></div>
        <div class="metric-row"><span class="metric-label">Float shares</span><span class="metric-value">${fmtNumInt(r.float_shares)}</span></div>
      </div>
      <div>
        <div class="text-xs text-neutral-500 uppercase mb-2">Momentum & Earnings</div>
        <div class="metric-row"><span class="metric-label">52w change</span><span class="metric-value ${r.fiftytwo_week_change > 0 ? 'metric-good' : 'metric-bad'}">${fmtPct(r.fiftytwo_week_change, 1)}</span></div>
        <div class="metric-row"><span class="metric-label">Earnings beat</span><span class="metric-value ${r.earnings_beat_pct > 0 ? 'metric-good' : 'metric-bad'}">${fmtPct(r.earnings_beat_pct, 1)}</span></div>
        <div class="metric-row"><span class="metric-label">Ex-dividend</span><span class="metric-value">${r.ex_dividend_date || '—'}</span></div>
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

    ${similarHtml ? `
    <div class="card p-3 rounded mb-4">
      <div class="text-xs text-neutral-500 uppercase mb-2">🔗 Empresas similares</div>
      <div class="flex flex-wrap gap-1">${similarHtml}</div>
      <p class="text-xs text-neutral-600 mt-2 italic">Mismo sector, cap y perfil de caída · ⭐ Carvana setup · 🟢 con señal activa</p>
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

// MEJORA 3: abrir detalle de un ticker por su símbolo (no por índice).
// No modifica filteredData (no rompe la tabla al cerrar el modal).
function openDetailByTicker(ticker) {
  let r = filteredData.find(x => x.ticker === ticker);
  if (!r) {
    r = getActiveSignals().find(x => x.ticker === ticker);
  }
  if (!r) {
    r = SIGNALS_DATA.results.find(x => x.ticker === ticker);
  }
  if (r) openDetailObj(r);
}

// ═══════════════════════════════════════════════════════════════════
// VISTA SECTORES — Mapa de mercado
// ═══════════════════════════════════════════════════════════════════
function sectorMomentum(e) {
  // Devuelve {label, cls, color} resumiendo el momento del ETF.
  // Prioridad: salida (techo) > entrada semanal > señal mensual > ASH estado.
  if (e.weekly_exit === 'WT_SELL_PLUS')
    return { label: '🔴 Techo / salida', cls: 'sec-red' };
  if (e.monthly_signal && (e.monthly_signal.type === 'SELL' || e.monthly_signal.type === 'SELL_PLUS'))
    return { label: '🔴 SELL mensual', cls: 'sec-red' };
  if (e.weekly_entry === 'ASH_HIGH')
    return { label: '💎 Girando (ASH HIGH)', cls: 'sec-green' };
  if (e.monthly_signal && (e.monthly_signal.type === 'BUY' || e.monthly_signal.type === 'BUY_GOLD'))
    return { label: '🟢 ' + (e.monthly_signal.type === 'BUY_GOLD' ? 'BUY GOLD' : 'BUY') + ' mensual', cls: 'sec-green' };
  if (e.ash_bullish === true)
    return { label: '🟢 ASH alcista', cls: 'sec-greenlight' };
  if (e.ash_bullish === false)
    return { label: '⚪ Neutral / bajista', cls: 'sec-gray' };
  return { label: '⚪ Sin datos', cls: 'sec-gray' };
}

function renderSectors() {
  const cont = document.getElementById('sectorsContent');
  if (!SECTORS_DATA || !SECTORS_DATA.results || SECTORS_DATA.results.length === 0) {
    cont.innerHTML = '<div class="text-center py-12 text-neutral-500">No hay datos de sectores. Ejecuta <code>python3 sectors.py</code> y regenera la web.</div>';
    return;
  }

  const groups = {};
  SECTORS_DATA.results.forEach(e => {
    const g = e.group || 'Otros';
    (groups[g] = groups[g] || []).push(e);
  });

  const order = ['Sectorial', 'Índice', 'ARK', 'Tecnología', 'Energía limpia',
                 'Cripto', 'Espacio', 'Cannabis', 'Biotech', 'Materias primas',
                 'Otros temáticos', 'Otros'];
  // Añadir cualquier grupo presente en los datos que no esté en `order`
  Object.keys(groups).forEach(g => { if (!order.includes(g)) order.push(g); });
  let html = '';
  if (SECTORS_DATA.scan_date_human) {
    html += '<p class="text-xs text-neutral-600 mb-4">Datos de sectores: ' + SECTORS_DATA.scan_date_human + '</p>';
  }

  order.forEach(g => {
    if (!groups[g]) return;
    html += '<div class="mb-6"><div class="text-sm font-semibold text-neutral-300 uppercase mb-3">' + g + '</div>';
    html += '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">';
    groups[g].forEach(e => {
      const mom = sectorMomentum(e);
      const dd = e.drawdown_from_ath_pct;
      const ddTxt = dd === null || dd === undefined ? '—' : dd.toFixed(0) + '%';
      const w52 = e.fiftytwo_week_change;
      const w52Txt = w52 === null || w52 === undefined ? '—'
        : (w52 >= 0 ? '<span class="text-green-400">+' + w52.toFixed(0) + '%</span>'
                    : '<span class="text-red-400">' + w52.toFixed(0) + '%</span>');
      const wt2 = e.monthly_wt2;
      const wt2Txt = wt2 === null || wt2 === undefined ? '—' : wt2.toFixed(0);
      const mfi = e.weekly_mfi;
      const mfiTxt = mfi === null || mfi === undefined ? '—' : mfi.toFixed(0);

      html += '<div class="sector-card ' + mom.cls + '">'
        + '<div class="flex justify-between items-start mb-2">'
        + '<div><span class="font-bold text-base">' + e.ticker + '</span>'
        + '<span class="text-xs text-neutral-400 ml-2">' + escapeHtml(e.name || '') + '</span></div>'
        + '<a href="' + fmtTV(e.ticker) + '" target="_blank" class="text-yellow-500 hover:text-yellow-300 text-sm">📊</a>'
        + '</div>'
        + '<div class="text-sm font-semibold mb-2">' + mom.label + '</div>'
        + '<div class="grid grid-cols-2 gap-1 text-xs text-neutral-400">'
        + '<div>Precio: <span class="text-neutral-200">' + fmtPrice(e.current_price) + '</span></div>'
        + '<div>52s: ' + w52Txt + '</div>'
        + '<div>ATH: ' + ddTxt + '</div>'
        + '<div>WT2/MFI: ' + wt2Txt + ' / ' + mfiTxt + '</div>'
        + '</div></div>';
    });
    html += '</div></div>';
  });

  cont.innerHTML = html;
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
    count_ch      = summary_data.get("total_carvana_hunter", 0)

    sectors = set()
    for r in signals_data["results"]:
        if r.get("sector"):
            sectors.add(r["sector"])
    sector_options = "\n".join([f'<option value="{s}">{s}</option>'
                                for s in sorted(sectors)])

    pwd_hash = hashlib.sha256(PASSWORD.encode()).hexdigest()

    # Cargar mapa de sectores (opcional: solo si existe sectors.json)
    sectors_data = {"results": [], "scan_date_human": ""}
    sectors_path = os.path.join(DATA_DIR, "sectors.json")
    if os.path.exists(sectors_path):
        try:
            with open(sectors_path) as f:
                sectors_data = json.load(f)
        except Exception:
            pass

    html = HTML_TEMPLATE
    html = html.replace("{{scan_date_human}}", signals_data["scan_date_human"])
    html = html.replace("{{total_scanned}}",   str(signals_data["total_scanned"]))
    html = html.replace("{{count_carvana}}",   str(count_carvana))
    html = html.replace("{{count_ch}}",         str(count_ch))
    html = html.replace("{{count_gold}}",      str(count_gold))
    html = html.replace("{{count_buy}}",       str(count_buy))
    html = html.replace("{{count_sellp}}",     str(count_sellp))
    html = html.replace("{{count_sell}}",      str(count_sell))
    html = html.replace("{{sector_options}}",  sector_options)
    html = html.replace("{{signals_json}}",    json.dumps(signals_data))
    html = html.replace("{{sectors_json}}",    json.dumps(sectors_data))
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
    print("  CB SCANNER — Generador HTML v5")
    print("═" * 60 + "\n")
    generate_html()
