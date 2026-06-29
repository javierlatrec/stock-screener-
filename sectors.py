"""
sectors.py
==========
Mapa de mercado por sectores: escanea ETFs sectoriales y temáticos en
semanal (ASH+MFI) y mensual (WaveTrend) con la MISMA lógica que las acciones.

Genera data/sectors.json para la tercera pestaña "Sectores" de la web.

Uso:
    python3 sectors.py          # escanea todos los ETFs
"""

import os
import json
import time
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from cb_scanner import (
    calculate_wavetrend,
    detect_signals,
    detect_ash_signals_weekly,
    detect_wt_signals_monthly,
    build_carvana_hunter,
)


# ═══════════════════════════════════════════════════════════════════
# UNIVERSO DE ETFs
# ═══════════════════════════════════════════════════════════════════

ETFS = [
    # ─── SPDR Select Sector (los 11 sectores del S&P 500) ───
    {"ticker": "XLK",  "name": "Tecnología",            "group": "Sectorial"},
    {"ticker": "XLF",  "name": "Financiero",            "group": "Sectorial"},
    {"ticker": "XLE",  "name": "Energía",               "group": "Sectorial"},
    {"ticker": "XLV",  "name": "Salud",                 "group": "Sectorial"},
    {"ticker": "XLI",  "name": "Industrial",            "group": "Sectorial"},
    {"ticker": "XLY",  "name": "Consumo discrecional",  "group": "Sectorial"},
    {"ticker": "XLP",  "name": "Consumo básico",        "group": "Sectorial"},
    {"ticker": "XLU",  "name": "Utilities",             "group": "Sectorial"},
    {"ticker": "XLB",  "name": "Materiales",            "group": "Sectorial"},
    {"ticker": "XLRE", "name": "Inmobiliario",          "group": "Sectorial"},
    {"ticker": "XLC",  "name": "Comunicaciones",        "group": "Sectorial"},
    # ─── Índices de contexto ───
    {"ticker": "SPY",  "name": "S&P 500",               "group": "Índice"},
    {"ticker": "QQQ",  "name": "Nasdaq 100",            "group": "Índice"},
    {"ticker": "IWM",  "name": "Russell 2000",          "group": "Índice"},
    # ─── Familia ARK ───
    {"ticker": "ARKK", "name": "Innovación",            "group": "ARK"},
    {"ticker": "ARKG", "name": "Genómica",              "group": "ARK"},
    {"ticker": "ARKW", "name": "Internet / Web",        "group": "ARK"},
    {"ticker": "ARKF", "name": "Fintech",               "group": "ARK"},
    {"ticker": "ARKQ", "name": "Automatización/Robótica","group": "ARK"},
    {"ticker": "ARKX", "name": "Espacio (ARK)",         "group": "ARK"},
    # ─── Espacio ───
    {"ticker": "UFO",  "name": "Espacio global",        "group": "Espacio"},
    # ─── Cannabis ───
    {"ticker": "MSOS", "name": "Cannabis US",           "group": "Cannabis"},
    {"ticker": "MJ",   "name": "Cannabis global",       "group": "Cannabis"},
    # ─── Tecnología / Innovación ───
    {"ticker": "SMH",  "name": "Semiconductores",       "group": "Tecnología"},
    {"ticker": "BOTZ", "name": "Robótica e IA",         "group": "Tecnología"},
    {"ticker": "DRIV", "name": "Coches eléctricos/auton.","group": "Tecnología"},
    {"ticker": "HACK", "name": "Ciberseguridad",        "group": "Tecnología"},
    {"ticker": "CIBR", "name": "Ciberseguridad (2)",    "group": "Tecnología"},
    {"ticker": "FINX", "name": "Fintech",               "group": "Tecnología"},
    {"ticker": "BLOK", "name": "Blockchain",            "group": "Tecnología"},
    # ─── Energía / Limpia ───
    {"ticker": "ICLN", "name": "Energía limpia",        "group": "Energía limpia"},
    {"ticker": "TAN",  "name": "Solar",                 "group": "Energía limpia"},
    {"ticker": "LIT",  "name": "Litio y baterías",      "group": "Energía limpia"},
    {"ticker": "URA",  "name": "Uranio",                "group": "Energía limpia"},
    # ─── Cripto ───
    {"ticker": "IBIT", "name": "Bitcoin (iShares)",     "group": "Cripto"},
    {"ticker": "GBTC", "name": "Bitcoin (Grayscale)",   "group": "Cripto"},
    # ─── Materias primas / Metales ───
    {"ticker": "GDX",  "name": "Mineras de oro",        "group": "Materias primas"},
    {"ticker": "REMX", "name": "Tierras raras",         "group": "Materias primas"},
    # ─── Biotech ───
    {"ticker": "XBI",  "name": "Biotech (small)",       "group": "Biotech"},
    {"ticker": "IBB",  "name": "Biotech (large)",       "group": "Biotech"},
    # ─── Otros temáticos ───
    {"ticker": "KWEB", "name": "China internet",        "group": "Otros temáticos"},
    {"ticker": "JETS", "name": "Aerolíneas",            "group": "Otros temáticos"},
    {"ticker": "TLT",  "name": "Bonos largos USA",      "group": "Otros temáticos"},
]

DATA_DIR     = "data"
SECTORS_JSON = os.path.join(DATA_DIR, "sectors.json")
SIGNAL_AGE_MAX_BARS = 3
CH_RECENT_BARS = 3


def _safe(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def analyze_etf(etf: dict) -> dict | None:
    """Escanea un ETF en mensual (WT) y semanal (ASH+MFI)."""
    import yfinance as yf
    ticker = etf["ticker"]

    out = {
        "ticker": ticker,
        "name": etf["name"],
        "group": etf["group"],
        "current_price": None,
        "drawdown_from_ath_pct": None,
        "fiftytwo_week_change": None,
        # Mensual (WaveTrend CB)
        "monthly_signal": None,     # {type, wt2, bars_ago}
        "monthly_wt2": None,
        # Semanal (Carvana Hunter)
        "weekly_entry": None,       # "ASH_HIGH" | None
        "weekly_exit": None,        # "WT_SELL_PLUS" | None
        "weekly_mfi": None,
        "ash_bullish": None,        # estado ASH actual (verde)
    }

    # ─── MENSUAL ───
    try:
        dfm = yf.download(ticker, interval="1mo", period="max",
                          progress=False, auto_adjust=True, threads=False)
        if dfm is not None and not dfm.empty and len(dfm) >= 30:
            if isinstance(dfm.columns, pd.MultiIndex):
                dfm.columns = dfm.columns.get_level_values(0)
            wt1, wt2 = calculate_wavetrend(dfm)
            signals = detect_signals(dfm, wt1, wt2)
            price = float(dfm["Close"].iloc[-1])
            ath = float(dfm["Close"].max())
            out["current_price"] = price
            out["drawdown_from_ath_pct"] = ((price - ath) / ath) * 100
            out["monthly_wt2"] = _safe(wt2.iloc[-1])
            last12 = dfm.tail(12)
            if len(last12) >= 2:
                start = float(last12["Close"].iloc[0])
                out["fiftytwo_week_change"] = ((price - start) / start) * 100
            if signals:
                last = signals[-1]
                bars = len(dfm) - 1 - last.bar_index
                if bars <= SIGNAL_AGE_MAX_BARS:
                    out["monthly_signal"] = {
                        "type": last.type,
                        "wt2": _safe(last.wt2),
                        "bars_ago": int(bars),
                    }
            del dfm
    except Exception:
        pass

    # ─── SEMANAL ───
    try:
        dfw = yf.download(ticker, interval="1wk", period="7y",
                          progress=False, auto_adjust=True, threads=False)
        if dfw is not None and not dfw.empty and len(dfw) >= 80:
            if isinstance(dfw.columns, pd.MultiIndex):
                dfw.columns = dfw.columns.get_level_values(0)
            ash_part = detect_ash_signals_weekly(dfw, recent_bars=CH_RECENT_BARS)
            wt_part = detect_wt_signals_monthly(dfw, recent_bars=CH_RECENT_BARS)
            chr_ = build_carvana_hunter(ash_part, wt_part)
            out["weekly_entry"] = chr_.active_entry
            out["weekly_exit"] = chr_.active_exit
            out["weekly_mfi"] = _safe(chr_.mfi_value)
            # estado ASH actual (verde = bullish)
            from cb_scanner import ash_signals
            sig = ash_signals(dfw)
            out["ash_bullish"] = bool(sig["ash_bullish"].iloc[-1])
            del dfw
    except Exception:
        pass

    return out


def scan_sectors() -> dict:
    print(f"🗺️  Escaneando {len(ETFS)} ETFs (sectoriales + temáticos)...\n")
    results = []
    for i, etf in enumerate(ETFS):
        print(f"   [{i+1}/{len(ETFS)}] {etf['ticker']:5s} {etf['name']}")
        r = analyze_etf(etf)
        if r:
            results.append(r)
        time.sleep(0.4)

    return {
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "scan_date_human": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(results),
        "results": results,
    }


def save(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SECTORS_JSON, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 {SECTORS_JSON}")


if __name__ == "__main__":
    print("═" * 60)
    print("  CB SCANNER — Mapa de sectores (ETFs)")
    print("═" * 60 + "\n")
    data = scan_sectors()
    save(data)
    print(f"\n✅ {data['total']} ETFs escaneados")
    print("\nSiguiente paso:")
    print("   python3 html_generator.py\n")
